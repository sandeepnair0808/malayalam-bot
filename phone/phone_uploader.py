#!/usr/bin/env python3
"""Autonomous YouTube uploader for an Android phone (Termux) or a Raspberry Pi.

Every run uploads the next video(s) from uploads.json that are not in uploaded.json yet.
Run it from cron a few times a day (see SETUP.md).

    python phone_uploader.py --auth          # once: sign in to Google
    python phone_uploader.py                 # upload the next video
    python phone_uploader.py --count 2       # upload the next two
    python phone_uploader.py --status        # how many are left

Files next to this script:
    client_secret.json   OAuth "Desktop app" credentials from Google Cloud (you download it)
    token.json           created by --auth
    uploads.json         the queue: [{"file", "title", "description", "tags", "made_for_kids", "category"}]
    uploaded.json        created automatically: which files are done, with their video ids
    videos/              folder that holds the .mp4 files (paths in uploads.json are relative to it)
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CATEGORIES = {"FILM_ANIMATION": "1", "EDUCATION": "27", "ENTERTAINMENT": "24", "PEOPLE_BLOGS": "22"}


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(line)
    with open(HERE / "uploader.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def credentials(interactive: bool):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token = HERE / "token.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            sys.exit("Not signed in. Run: python phone_uploader.py --auth")
        flow = InstalledAppFlow.from_client_secrets_file(str(HERE / "client_secret.json"), SCOPES)
        # open_browser=False: copy the printed link into the phone browser
        creds = flow.run_local_server(port=8085, open_browser=False,
                                      authorization_prompt_message="Open this link in your browser:\n{url}\n")
    token.write_text(creds.to_json())
    return creds


def load(name: str, default):
    p = HERE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(done: dict) -> None:
    tmp = HERE / "uploaded.json.tmp"
    tmp.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(HERE / "uploaded.json")  # atomic: a crash never leaves a half-written file


def upload_one(youtube, item: dict, videos_dir: Path) -> str:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": item["title"][:100],
            "description": item["description"][:4900],
            "tags": item.get("tags", [])[:15],
            "categoryId": CATEGORIES.get(item.get("category", "FILM_ANIMATION"), "1"),
            "defaultLanguage": "ml",
            "defaultAudioLanguage": "ml",
        },
        "status": {
            "privacyStatus": item.get("privacy", "public"),
            "selfDeclaredMadeForKids": bool(item.get("made_for_kids", False)),
            "embeddable": True,
        },
    }
    media = MediaFileUpload(str(videos_dir / item["file"]), mimetype="video/mp4", chunksize=4 * 1024 * 1024,
                            resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth", action="store_true", help="sign in to Google (once)")
    ap.add_argument("--count", type=int, default=1, help="videos to upload this run")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--retry", metavar="FILE", help="allow one interrupted file to be uploaded again")
    ap.add_argument("--videos", default=str(HERE / "videos"), help="folder with the mp4 files")
    args = ap.parse_args()

    queue = load("uploads.json", [])
    done = load("uploaded.json", {})
    done_titles = {v.get("title") for v in done.values() if isinstance(v, dict) and v.get("title")}
    done_titles |= {it["title"] for it in queue if it["file"] in done}  # older entries saved without a title
    # never re-upload: skip files already done (or started), and any queue entry whose title was already used
    left = [it for it in queue if it["file"] not in done and it["title"] not in done_titles]
    if args.retry:
        done.pop(args.retry, None)
        save(done)
        print(f"{args.retry} will be uploaded again on the next run")
        return 0
    if args.status:
        stuck = [f for f, v in done.items() if isinstance(v, dict) and v.get("status") == "started"]
        print(f"{len(done) - len(stuck)} uploaded, {len(left)} left")
        for f in stuck:
            print("  needs a check (upload was interrupted):", f)
        for it in left[:5]:
            print("  next:", it["file"])
        return 0

    # only one uploader at a time (a slow upload must not overlap the next 15-minute run)
    lock = open(HERE / ".uploader.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another upload is still running; skipping this run")
        return 0

    creds = credentials(interactive=args.auth)
    if args.auth:
        print("Signed in. Now run without --auth to upload.")
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    videos_dir = Path(args.videos)
    uploaded_now = 0
    for item in left:
        if uploaded_now >= args.count:
            break
        if item["title"] in done_titles:
            continue  # same video already uploaded under another file name
        if not (videos_dir / item["file"]).exists():
            log(f"MISSING {item['file']} (skipped for now)")
            continue
        done_titles.add(item["title"])
        # mark as started BEFORE uploading: if the phone dies mid-way it is never retried automatically
        done[item["file"]] = {"id": None, "status": "started", "title": item["title"],
                              "at": datetime.now().isoformat(timespec="minutes")}
        save(done)
        for attempt in range(3):
            try:
                vid = upload_one(youtube, item, videos_dir)
                done[item["file"]] = {"id": vid, "status": "uploaded", "title": item["title"],
                                      "at": datetime.now().isoformat(timespec="minutes")}
                save(done)
                log(f"OK {item['file']} -> https://youtube.com/shorts/{vid}")
                uploaded_now += 1
                break
            except HttpError as err:
                if "quotaExceeded" in str(err) or "uploadLimitExceeded" in str(err):
                    del done[item["file"]]  # nothing was uploaded; try this one again tomorrow
                    save(done)
                    log("YouTube daily limit reached; will continue next run")
                    return 0
                log(f"ERROR {item['file']}: {err} (attempt {attempt + 1})")
                time.sleep(30)
            except OSError as err:  # network drop
                log(f"NETWORK {item['file']}: {err} (attempt {attempt + 1})")
                time.sleep(60)
        else:
            log(f"GAVE UP {item['file']}: check YouTube Studio; run --retry {item['file']} if it is not there")
    return 0


if __name__ == "__main__":
    sys.exit(main())
