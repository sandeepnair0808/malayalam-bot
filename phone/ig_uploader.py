#!/usr/bin/env python3
"""Autonomous Instagram Reels uploader for Termux (official Instagram API with Instagram Login).

No extra packages needed (standard library only).

    python ig_uploader.py --token PASTE_TOKEN   # once: save the access token from the Meta app dashboard
    python ig_uploader.py                       # post the next reel
    python ig_uploader.py --status              # how many are left

Files next to this script:
    ig_token.json      saved token + your Instagram user id (created by --token)
    ig_queue.json      optional queue: [{"file", "video_url", "caption"}]. Without it, the script follows
                       YouTube: every Short phone_uploader.py posts after the token was saved is posted
                       here too (same video from the reels branch, Instagram caption from insta_latest.py).
    ig_posted.json     created automatically: what is already posted (never posted twice)

Instagram downloads each video from its public link (video_url), so no upload from the phone is needed.
The token lasts 60 days; this script refreshes it automatically every few days.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://graph.instagram.com/v21.0"


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(line)
    with open(HERE / "ig_uploader.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load(name: str, default):
    p = HERE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(name: str, data) -> None:
    tmp = HERE / (name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(HERE / name)


def call(method: str, url: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {err.code}: {body}") from None


def token_state() -> dict:
    st = load("ig_token.json", {})
    if not st.get("token"):
        sys.exit("No token yet. Run: python ig_uploader.py --token PASTE_TOKEN")
    # refresh if older than 5 days (long-lived tokens last 60 days)
    saved = datetime.fromisoformat(st.get("saved", "2000-01-01T00:00"))
    if datetime.now() - saved > timedelta(days=5):
        try:
            r = call("GET", "https://graph.instagram.com/refresh_access_token",
                     {"grant_type": "ig_refresh_token", "access_token": st["token"]})
            st["token"], st["saved"] = r["access_token"], datetime.now().isoformat(timespec="minutes")
            save("ig_token.json", st)
            log("token refreshed")
        except RuntimeError as err:
            log(f"token refresh failed (still using old token): {err}")
    return st


def post_reel(st: dict, item: dict) -> str:
    uid, tok = st["user_id"], st["token"]
    try:
        c = call("POST", f"{API}/{uid}/media", {
            "media_type": "REELS", "video_url": item["video_url"], "caption": item["caption"][:2200],
            "share_to_feed": "true", "access_token": tok,
        })
    except RuntimeError as err:
        raise RuntimeError(f"create failed: {err}") from None
    cid = c["id"]
    for _ in range(40):  # Instagram processes the video (usually 30-120 s)
        time.sleep(15)
        s = call("GET", f"{API}/{cid}", {"fields": "status_code,status", "access_token": tok})
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"processing failed: {s}")
    else:
        raise RuntimeError("processing timed out")
    p = call("POST", f"{API}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    return p["id"]


RAW = "https://raw.githubusercontent.com/sandeepnair0808/malayalam-bot/reels/"


def follow_youtube() -> list:
    """Shorts already on YouTube (posted after the Instagram token was saved), oldest first."""
    from insta_latest import caption

    since = load("ig_token.json", {}).get("saved", "9999")
    done = load("uploaded.json", {})
    items = {it["file"]: it for it in load("uploads.json", [])}
    out = []
    for f, v in sorted(done.items(), key=lambda kv: kv[1].get("at", "")):
        if v.get("status") == "uploaded" and v.get("at", "") >= since and f in items:
            out.append({"file": f, "video_url": RAW + f, "caption": caption(items[f])})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", help="save the access token from the Meta dashboard")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--retry", metavar="FILE", help="allow one interrupted file to be posted again")
    ap.add_argument("--skip", nargs="+", metavar="FILE", help="mark files as already posted by hand")
    args = ap.parse_args()

    if args.token:
        me = call("GET", f"{API}/me", {"fields": "user_id,username", "access_token": args.token.strip()})
        save("ig_token.json", {"token": args.token.strip(), "user_id": me["user_id"], "username": me["username"],
                               "saved": datetime.now().isoformat(timespec="minutes")})
        print(f"Saved. Connected to Instagram account @{me['username']}")
        return 0

    queue = load("ig_queue.json", []) or follow_youtube()
    posted = load("ig_posted.json", {})
    if args.skip:
        for f in args.skip:
            posted[f] = {"status": "posted-by-hand"}
        save("ig_posted.json", posted)
        print(f"Marked {len(args.skip)} as already posted")
        return 0
    if args.retry:
        posted.pop(args.retry, None)
        save("ig_posted.json", posted)
        print(f"{args.retry} will be posted again on the next run")
        return 0
    left = [it for it in queue if it["file"] not in posted]
    if args.status:
        stuck = [f for f, v in posted.items() if v.get("status") == "started"]
        print(f"{len(posted) - len(stuck)} posted, {len(left)} left")
        for it in left[:5]:
            print("  next:", it["file"])
        for f in stuck:
            print("  needs a check (posting was interrupted):", f)
        return 0

    lock = open(HERE / ".ig.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another Instagram post is still running; skipping this run")
        return 0

    st = token_state()
    for item in left[: args.count]:
        posted[item["file"]] = {"status": "started", "at": datetime.now().isoformat(timespec="minutes")}
        save("ig_posted.json", posted)
        try:
            mid = post_reel(st, item)
        except RuntimeError as err:
            msg = str(err)
            if "limit" in msg.lower() or "(#9)" in msg or "(#4)" in msg:
                del posted[item["file"]]  # nothing published; try again later
                save("ig_posted.json", posted)
                log(f"Instagram limit reached, will retry later: {msg[:200]}")
                return 0
            if msg.startswith(("create failed", "processing failed", "processing timed out")):
                del posted[item["file"]]  # container never published; safe to retry next run
                save("ig_posted.json", posted)
            log(f"ERROR {item['file']}: {msg[:300]}")
            return 0
        posted[item["file"]] = {"status": "posted", "media_id": mid, "at": datetime.now().isoformat(timespec="minutes")}
        save("ig_posted.json", posted)
        log(f"OK {item['file']} -> Instagram media {mid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
