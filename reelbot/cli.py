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
    sub = p.add_subparsers(dest="cmd", required=True)

    mk = sub.add_parser("make", help="write, illustrate and render a new reel")
    mk.add_argument("--theme", help="story idea in English (default: pick an unused one)")
    mk.add_argument("--story", type=Path, help="use an existing story.json instead of writing a new one")

    rb = sub.add_parser("rebuild", help="re-render voice/video for an existing reel dir (no Claude calls)")
    rb.add_argument("reel_dir", type=Path)

    pb = sub.add_parser("publish", help="upload an existing reel dir to Instagram")
    pb.add_argument("reel_dir", type=Path)
    pb.add_argument("--video-url", help="public HTTPS URL of reel.mp4 instead of uploading the file")

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

    if args.cmd == "make":
        story = Story.model_validate_json(args.story.read_text(encoding="utf-8")) if args.story else None
        reel_dir = pipeline.make(settings, theme=args.theme, story=story)
        print(reel_dir)
    elif args.cmd == "rebuild":
        print(pipeline.rebuild(settings, args.reel_dir))
    elif args.cmd == "publish":
        result = pipeline.publish(settings, args.reel_dir, video_url=args.video_url)
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
