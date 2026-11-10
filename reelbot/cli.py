"""Command line: `reelbot make | rebuild | publish | run`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import pipeline
from .config import Settings
from .models import Story


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="reelbot", description="Malayalam story reel creator + Instagram publisher")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--style", choices=["cartoon", "3d"], help="visual style (default: REELBOT_STYLE or cartoon)")
    sub = p.add_subparsers(dest="cmd", required=True)

    mk = sub.add_parser("make", help="write, illustrate and render a new reel")
    mk.add_argument("--theme", help="story idea in English (default: pick an unused one)")
    mk.add_argument("--story", type=Path, help="use an existing story.json instead of writing a new one")

    rb = sub.add_parser("rebuild", help="re-render voice/video for an existing reel dir (no Claude calls)")
    rb.add_argument("reel_dir", type=Path)
    rb.add_argument("--retry-ai", action="store_true", help="3d style: retry scenes whose AI video clip failed")

    pb = sub.add_parser("publish", help="upload an existing reel dir to Instagram")
    pb.add_argument("reel_dir", type=Path)
    pb.add_argument("--video-url", help="public HTTPS URL of reel.mp4 instead of uploading the file")

    pk = sub.add_parser("pack", help="expand story pack(s) into ready story folders (and optionally render them)")
    pk.add_argument("packs", nargs="+", type=Path)
    pk.add_argument("--out", type=Path, default=Path("queue"))
    pk.add_argument("--render", action="store_true", help="also render each reel.mp4")

    ln = sub.add_parser("lint", help="safety-check kids story packs (no API calls)")
    ln.add_argument("packs", nargs="+", type=Path)
    ln.add_argument("--general", action="store_true", help="grown-up nostalgia packs: no moral line required")

    pl = sub.add_parser("payloads", help="write Metricool post payloads (YouTube + Instagram) for rendered kids reels")
    pl.add_argument("packs", nargs="+", type=Path)
    pl.add_argument("--queue", type=Path, default=Path("queue"))
    pl.add_argument("--url-base", required=True, help="public URL folder holding <slug>.mp4")
    pl.add_argument("--start", required=True, help="first post time, IST, e.g. 2026-11-11T16:30")
    pl.add_argument("--every", type=int, default=30, help="minutes between posts")
    pl.add_argument("--out", type=Path, default=Path("payloads"))
    pl.add_argument("--post-style", choices=["kids", "nostalgia"], default="kids")

    nx = sub.add_parser("next", help="render (and optionally publish) the next unpublished reel from the queue")
    nx.add_argument("--queue", type=Path, default=Path("queue"))
    nx.add_argument("--publish", action="store_true")

    rn = sub.add_parser("run", help="make a reel and publish it")
    rn.add_argument("--theme")
    rn.add_argument("--no-publish", action="store_true", help="only make the reel")

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for noisy in ("httpx", "httpcore", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    settings = Settings()
    if args.style:
        settings.style = args.style

    if args.cmd == "make":
        story = Story.model_validate_json(args.story.read_text(encoding="utf-8")) if args.story else None
        reel_dir = pipeline.make(settings, theme=args.theme, story=story)
        print(reel_dir)
    elif args.cmd == "rebuild":
        print(pipeline.rebuild(settings, args.reel_dir, retry_ai=args.retry_ai))
    elif args.cmd == "publish":
        result = pipeline.publish(settings, args.reel_dir, video_url=args.video_url)
        print(result.permalink or result.media_id)
    elif args.cmd == "pack":
        from .storypack import write_pack

        for pack in args.packs:
            for d in write_pack(pack, args.out):
                print(d)
                if args.render:
                    pipeline.rebuild(settings, d)
    elif args.cmd == "lint":
        from .safety import lint

        report = lint(args.packs, kids=not args.general)
        for key, probs in report.items():
            for prob in probs:
                print(f"{key}: {prob}")
        print("OK" if not report else f"{len(report)} stories need fixes")
        return 1 if report else 0
    elif args.cmd == "payloads":
        from datetime import datetime

        from .metricool import write_payloads

        files = write_payloads(args.packs, args.queue, args.url_base, datetime.fromisoformat(args.start),
                               args.every, args.out, style=args.post_style)
        print(f"{len(files)} payloads in {args.out}")
    elif args.cmd == "next":
        d = pipeline.next_in_queue(settings, args.queue)
        if d is None:
            print("queue is empty")
            return 0
        pipeline.rebuild(settings, d)
        print(d)
        if args.publish:
            result = pipeline.publish(settings, d)
            print(result.permalink or result.media_id)
    elif args.cmd == "run":
        reel_dir = pipeline.make(settings, theme=args.theme)
        print(reel_dir)
        if not args.no_publish:
            result = pipeline.publish(settings, reel_dir)
            print(result.permalink or result.media_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
