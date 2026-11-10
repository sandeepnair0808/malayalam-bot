"""Publish a local MP4 as an Instagram Reel through the Instagram Graph API.

Flow (resumable upload, no public video hosting needed):
  1. POST /{ig-user-id}/media  media_type=REELS, upload_type=resumable, caption  -> container id + upload uri
  2. POST https://rupload.facebook.com/ig-api-upload/{version}/{container-id}   (raw bytes)
  3. GET  /{container-id}?fields=status_code     until FINISHED
  4. POST /{ig-user-id}/media_publish  creation_id={container-id}   -> media id
  5. GET  /{media-id}?fields=permalink

Alternatively pass `video_url=` (a public HTTPS URL) and steps 2 is skipped.

Requirements: an Instagram Professional (Business/Creator) account, and an access token
with instagram_basic + instagram_content_publish (Facebook Login) or
instagram_business_basic + instagram_business_content_publish (Instagram Login).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import Settings

log = logging.getLogger(__name__)

RUPLOAD = "https://rupload.facebook.com/ig-api-upload"


class InstagramError(RuntimeError):
    pass


@dataclass
class PublishResult:
    media_id: str
    permalink: str | None


class InstagramClient:
    def __init__(self, user_id: str, token: str, host: str = "graph.facebook.com", version: str = "v21.0",
                 session: requests.Session | None = None):
        if not user_id or not token:
            raise InstagramError("IG_USER_ID and IG_ACCESS_TOKEN must be set to publish")
        self.user_id = user_id
        self.token = token
        self.version = version
        self.base = f"https://{host}/{version}"
        self.http = session or requests.Session()

    @classmethod
    def from_settings(cls, s: Settings) -> "InstagramClient":
        return cls(s.ig_user_id, s.ig_access_token, s.ig_graph_host, s.ig_graph_version)

    # -- helpers -----------------------------------------------------------
    def _check(self, resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise InstagramError(
                f"HTTP {resp.status_code}: {err.get('message') or resp.text[:500]} "
                f"(code={err.get('code')}, subcode={err.get('error_subcode')})"
            )
        return data

    def _post(self, path: str, **params) -> dict:
        params["access_token"] = self.token
        return self._check(self.http.post(f"{self.base}/{path}", data=params, timeout=60))

    def _get(self, path: str, **params) -> dict:
        params["access_token"] = self.token
        return self._check(self.http.get(f"{self.base}/{path}", params=params, timeout=60))

    # -- steps -------------------------------------------------------------
    def create_container(self, caption: str, video_url: str | None = None, thumb_offset_ms: int | None = None,
                         share_to_feed: bool = True) -> dict:
        params = {"media_type": "REELS", "caption": caption, "share_to_feed": str(share_to_feed).lower()}
        if video_url:
            params["video_url"] = video_url
        else:
            params["upload_type"] = "resumable"
        if thumb_offset_ms is not None:
            params["thumb_offset"] = str(thumb_offset_ms)
        return self._post(f"{self.user_id}/media", **params)

    def upload_file(self, container: dict, video: Path) -> None:
        url = container.get("uri") or f"{RUPLOAD}/{self.version}/{container['id']}"
        size = video.stat().st_size
        headers = {"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(size)}
        with video.open("rb") as fh:
            resp = self.http.post(url, headers=headers, data=fh, timeout=600)
        data = self._check(resp)
        if data and data.get("success") is False:
            raise InstagramError(f"upload rejected: {data}")

    def wait_until_ready(self, container_id: str, timeout: float = 600, interval: float = 10) -> None:
        deadline = time.monotonic() + timeout
        while True:
            data = self._get(container_id, fields="status_code,status")
            code = data.get("status_code")
            log.info("container %s status: %s", container_id, code)
            if code == "FINISHED":
                return
            if code in {"ERROR", "EXPIRED"}:
                raise InstagramError(f"container {container_id} {code}: {data.get('status')}")
            if time.monotonic() > deadline:
                raise InstagramError(f"container {container_id} not ready after {timeout}s (last: {code})")
            time.sleep(interval)

    def publish(self, container_id: str) -> str:
        return self._post(f"{self.user_id}/media_publish", creation_id=container_id)["id"]

    def permalink(self, media_id: str) -> str | None:
        try:
            return self._get(media_id, fields="permalink").get("permalink")
        except InstagramError as err:
            log.warning("could not fetch permalink: %s", err)
            return None

    # -- all together ------------------------------------------------------
    def publish_reel(self, video: Path | None, caption: str, video_url: str | None = None,
                     thumb_offset_ms: int | None = 1500) -> PublishResult:
        container = self.create_container(caption, video_url=video_url, thumb_offset_ms=thumb_offset_ms)
        cid = container["id"]
        log.info("created container %s", cid)
        if not video_url:
            if video is None:
                raise InstagramError("either a local video or video_url is required")
            self.upload_file(container, video)
            log.info("uploaded %s (%.1f MB)", video.name, video.stat().st_size / 1e6)
        self.wait_until_ready(cid)
        media_id = self.publish(cid)
        link = self.permalink(media_id)
        log.info("published reel %s %s", media_id, link or "")
        return PublishResult(media_id, link)
