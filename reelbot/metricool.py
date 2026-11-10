"""Build Metricool scheduled-post payloads (one post = YouTube Short + Instagram Reel).

The posts themselves are created through the Metricool connector (createScheduledPost),
so this module only prepares `{"date": ..., "info": "<json>"}` files, keeping each
scheduling call small and identical in shape.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .models import Story
from .safety import morals

TZ = "Asia/Calcutta"
BASE_TAGS = ["shorts", "malayalam", "kidsstory", "moralstory", "malayalamkidsstory"]
TAIL_TAGS = ["kerala", "kidsvideos", "storytime", "reels"]
YT_TAGS = ["malayalam kids story", "malayalam moral story", "kids moral stories", "malayalam cartoon",
           "malayalam animation", "bedtime story malayalam", "kerala kids", "shorts"]


def _title(story: Story) -> str:
    title = f"{story.title_ml} | {story.title_en} | Malayalam Moral Story for Kids #shorts"
    if len(title) > 100:
        title = f"{story.title_ml} | {story.title_en} #shorts"
    return title[:100]


def kids_post(story: Story, moral_en: str, video_url: str, when: datetime) -> dict:
    topical = [t for t in story.hashtags if t not in BASE_TAGS + TAIL_TAGS + ["malayalam"]]
    tags = BASE_TAGS + topical + TAIL_TAGS
    moral_ml = story.scenes[-1].narration_ml if story.scenes else ""
    text = "\n\n".join(filter(None, [
        story.caption_ml,
        moral_ml,
        f"Moral: {moral_en}" if moral_en else "",
        "🔔 ദിവസവും പുതിയ ഗുണപാഠ കഥകൾക്ക് ഫോളോ ചെയ്യൂ / സബ്സ്ക്രൈബ് ചെയ്യൂ",
        " ".join(f"#{t}" for t in dict.fromkeys(tags)),
    ]))
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False, "media": [video_url], "mediaAltText": [],
        "providers": [{"network": "youtube"}, {"network": "instagram"}],
        "publicationDate": {"dateTime": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": TZ},
        "shortener": False, "smartLinkData": {"ids": []}, "text": text,
        "youtubeData": {
            "title": _title(story), "type": "short", "privacy": "public", "madeForKids": True,
            "category": "EDUCATION", "isAiGeneratedContent": False,
            "tags": list(dict.fromkeys(topical + YT_TAGS))[:15],
        },
        "instagramData": {"type": "REEL", "showReelOnFeed": True},
    }
    return {"date": when.strftime("%Y-%m-%dT%H:%M:%S+05:30"), "info": json.dumps(info, ensure_ascii=False)}


def write_payloads(packs: list[Path], queue: Path, url_base: str, start: datetime, every_min: int,
                   out: Path) -> list[Path]:
    """One payload per rendered story in `queue`, in pack order, `every_min` apart from `start`."""
    from .storypack import parse

    out.mkdir(parents=True, exist_ok=True)
    files, when = [], start
    for pack in packs:
        text = pack.read_text(encoding="utf-8")
        ms = morals(text)
        for slug, _ in parse(text):
            d = queue / slug
            if not (d / "reel.mp4").exists():
                continue
            story = Story.model_validate_json((d / "story.json").read_text(encoding="utf-8"))
            payload = kids_post(story, ms.get(slug, ""), f"{url_base.rstrip('/')}/{slug}.mp4", when)
            f = out / f"{slug}.json"
            f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            files.append(f)
            when += timedelta(minutes=every_min)
    return files
