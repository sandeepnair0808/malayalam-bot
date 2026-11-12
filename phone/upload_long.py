"""Upload the long-form compilations listed in long_videos.json (one command, never twice).

    cd ~/malayalam-bot && git pull && cd phone && python upload_long.py

For each entry not yet in long_uploaded.json it downloads the video and thumbnail from the reels
branch (if they are not on the phone yet), uploads the video as a normal (non-Shorts) public video,
sets the custom thumbnail, and records the video id so it is never uploaded again.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from phone_uploader import HERE, credentials, upload_one

RAW = "https://raw.githubusercontent.com/sandeepnair0808/malayalam-bot/reels/"
DONE = HERE / "long_uploaded.json"


def fetch(rel: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {rel} ...")
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(RAW + rel, tmp)
    tmp.rename(dest)
    return dest


def main() -> int:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    items = json.loads((HERE / "long_videos.json").read_text(encoding="utf-8"))
    done = json.loads(DONE.read_text()) if DONE.exists() else {}
    todo = [it for it in items if it["file"] not in done]
    if not todo:
        print("nothing new to upload")
        return 0
    youtube = build("youtube", "v3", credentials=credentials(interactive=False), cache_discovery=False)
    folder = HERE / "long"
    for it in todo:
        video = fetch(it["file"], folder / Path(it["file"]).name)
        print(f"uploading {video.name} ({video.stat().st_size // 1_000_000} MB), please keep Termux open ...")
        vid = upload_one(youtube, {**it, "file": video.name}, folder)
        done[it["file"]] = {"id": vid, "title": it["title"]}
        DONE.write_text(json.dumps(done, ensure_ascii=False, indent=1))
        print(f"OK https://youtu.be/{vid}")
        if it.get("thumbnail"):
            thumb = fetch(it["thumbnail"], folder / Path(it["thumbnail"]).name)
            try:
                youtube.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
                print("thumbnail set")
            except HttpError as err:
                print("thumbnail not set (verify the channel by SMS in YouTube Studio, then add it by hand):",
                      str(err)[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
