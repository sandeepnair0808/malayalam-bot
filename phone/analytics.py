#!/usr/bin/env python3
"""Collect YouTube analytics for the whole channel into CSV files (Termux / Raspberry Pi).

    python analytics.py --auth     # once: sign in (read-only access to stats)
    python analytics.py            # collect everything now

Writes (and copies to /sdcard/Download so you can share them):
    stats/videos_<date>.csv   one row per video: title, published, views, likes, comments, shares,
                              watch minutes, avg view seconds, avg % viewed, subscribers gained,
                              engaged views + engaged % (NOT Studio's "stayed to watch"; the API does not
                              expose swipe-aways, so check that number in YouTube Studio),
                              and which queue file it came from
    stats/daily_<date>.csv    channel totals per day: views, watch minutes, subscribers gained/lost, likes
Uses its own login (analytics_token.json), separate from the uploader's.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]
TOKEN = HERE / "analytics_token.json"
OUT = HERE / "stats"
SHARE = Path("/sdcard/Download")


def credentials(interactive: bool):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            sys.exit("Not signed in for analytics. Run: python analytics.py --auth")
        flow = InstalledAppFlow.from_client_secrets_file(str(HERE / "client_secret.json"), SCOPES)
        creds = flow.run_local_server(port=8086, open_browser=False,
                                      authorization_prompt_message="Open this link in your browser:\n{url}\n")
    TOKEN.write_text(creds.to_json())
    return creds


def all_videos(yt) -> list[dict]:
    ch = yt.channels().list(part="contentDetails,statistics,snippet", mine=True).execute()["items"][0]
    print(f"Channel: {ch['snippet']['title']} | subscribers {ch['statistics'].get('subscriberCount')} | "
          f"views {ch['statistics'].get('viewCount')} | videos {ch['statistics'].get('videoCount')}")
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        token = r.get("nextPageToken")
        if not token:
            break
    vids = []
    for k in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[k:k + 50])).execute()
        for v in r["items"]:
            s = v["statistics"]
            vids.append({
                "video_id": v["id"], "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"][:16].replace("T", " "),
                "duration": v["contentDetails"]["duration"],
                "views_total": int(s.get("viewCount", 0)), "likes_total": int(s.get("likeCount", 0)),
                "comments_total": int(s.get("commentCount", 0)),
            })
    return vids


def report(ya, start: str, end: str, metrics: str, dims: str, **kw) -> list[dict]:
    r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, metrics=metrics,
                           dimensions=dims, **kw).execute()
    heads = [h["name"] for h in r.get("columnHeaders", [])]
    return [dict(zip(heads, row)) for row in r.get("rows", [])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth", action="store_true", help="sign in once (read-only)")
    ap.add_argument("--since", default="2020-01-01", help="start date for analytics (YYYY-MM-DD)")
    args = ap.parse_args()

    creds = credentials(interactive=args.auth)
    if args.auth:
        print("Signed in for analytics. Now run: python analytics.py")
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    today = date.today().isoformat()

    vids = all_videos(yt)
    by_id = {v["video_id"]: v for v in vids}

    # per-video analytics (data lags 1-2 days behind the live counters)
    base = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained"
    try:
        rows = report(ya, args.since, today, base, "video", sort="-views", maxResults=200)
    except HttpError as err:
        print("Analytics API error (is 'YouTube Analytics API' enabled in Google Cloud?):", err)
        rows = []
    for r in rows:
        v = by_id.setdefault(r["video"], {"video_id": r["video"]})
        v.update({k: r[k] for k in r if k != "video"})
        v["avg_pct"] = round(float(r.get("averageViewPercentage", 0) or 0), 1)
    try:  # Shorts: engaged views = views that were not swiped away in the first seconds
        for r in report(ya, args.since, today, "views,engagedViews", "video", sort="-views", maxResults=200):
            v = by_id.setdefault(r["video"], {"video_id": r["video"]})
            v["engagedViews"] = r["engagedViews"]
            if r["views"]:
                v["engaged_pct"] = round(100 * r["engagedViews"] / r["views"], 1)
    except HttpError:
        print("(engagedViews not available for this channel yet; 'engaged %' left empty)")

    # which queue file each upload came from (phone uploader log)
    done = json.loads((HERE / "uploaded.json").read_text()) if (HERE / "uploaded.json").exists() else {}
    for f, info in done.items():
        if isinstance(info, dict) and info.get("id") in by_id:
            by_id[info["id"]]["queue_file"] = f

    OUT.mkdir(exist_ok=True)
    cols = ["published", "title", "views_total", "views", "engagedViews", "engaged_pct", "averageViewPercentage",
            "averageViewDuration", "estimatedMinutesWatched", "likes_total", "comments_total", "shares",
            "subscribersGained", "duration", "queue_file", "video_id"]
    vfile = OUT / f"videos_{today}.csv"
    with open(vfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for v in sorted(by_id.values(), key=lambda x: -int(x.get("views_total", 0) or 0)):
            w.writerow(v)

    try:
        daily = report(ya, args.since, today, "views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes",
                       "day", sort="day")
    except HttpError:
        daily = []
    dfile = OUT / f"daily_{today}.csv"
    with open(dfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["day", "views", "estimatedMinutesWatched", "subscribersGained",
                                          "subscribersLost", "likes"])
        w.writeheader()
        w.writerows(daily)

    print(f"\nTop 10 by views ({len(by_id)} videos):")
    for v in sorted(by_id.values(), key=lambda x: -int(x.get("views_total", 0) or 0))[:10]:
        stay = f"{v['avg_pct']}% watched" if v.get("avg_pct") else ""
        print(f"  {v.get('views_total', 0):>6} views  {stay:<12} {v.get('title', '')[:50]}")
    for p in (vfile, dfile):
        try:
            shutil.copy(p, SHARE / p.name)
        except OSError:
            pass
    print(f"\nSaved {vfile.name} and {dfile.name} (also in your phone's Download folder). "
          f"Send them to Claude for analysis. [{datetime.now():%H:%M}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
