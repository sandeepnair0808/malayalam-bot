"""Build Metricool scheduled-post payloads (YouTube Short, optionally also an Instagram Reel).

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
BASE_TAGS = ["shorts", "malayalam", "moralstory", "familystory"]
TAIL_TAGS = ["kerala", "storytime"]
YT_TAGS = ["malayalam moral story", "malayalam family story", "malayalam cartoon", "malayalam animation",
           "malayalam story", "kerala", "shorts"]


def _title(story: Story) -> str:
    title = f"{story.title_ml} | {story.title_en} | Malayalam Family Story #shorts"
    if len(title) > 100:
        title = f"{story.title_ml} | {story.title_en} #shorts"
    return title[:100]


def kids_post(story: Story, moral_en: str, video_url: str, when: datetime,
              networks: tuple[str, ...] = ("youtube",)) -> dict:
    topical = [t for t in story.hashtags if t not in BASE_TAGS + TAIL_TAGS + ["malayalam"]]
    tags = BASE_TAGS + topical + TAIL_TAGS
    moral_ml = story.scenes[-1].narration_ml if story.scenes else ""
    text = "\n\n".join(filter(None, [
        story.caption_ml,
        moral_ml,
        f"Moral: {moral_en}" if moral_en else "",
        "🔔 ദിവസവും പുതിയ ഗുണപാഠ കഥകൾക്ക് സബ്സ്ക്രൈബ് ചെയ്യൂ",
        " ".join(f"#{t}" for t in dict.fromkeys(tags)),
    ]))
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False, "media": [video_url], "mediaAltText": [],
        "providers": [{"network": n} for n in networks],
        "publicationDate": {"dateTime": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": TZ},
        "shortener": False, "smartLinkData": {"ids": []}, "text": text,
        "youtubeData": {
            "title": _title(story), "type": "short", "privacy": "public", "madeForKids": False,  # owner decision: family audience, not made for kids
            "category": "EDUCATION", "isAiGeneratedContent": False,
            "tags": list(dict.fromkeys(topical + YT_TAGS))[:15],
        },
    }
    if "instagram" in networks:
        info["instagramData"] = {"type": "REEL", "showReelOnFeed": True}
    return {"date": when.strftime("%Y-%m-%dT%H:%M:%S+05:30"), "info": json.dumps(info, ensure_ascii=False)}


def write_payloads(packs: list[Path], queue: Path, url_base: str, start: datetime, every_min: int,
                   out: Path, style: str = "kids") -> list[Path]:
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
            url = f"{url_base.rstrip('/')}/{slug}.mp4"
            payload = (nostalgia_post(story, url, when) if style == "nostalgia"
                       else kids_post(story, ms.get(slug, ""), url, when))
            f = out / f"{slug}.json"
            f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            files.append(f)
            when += timedelta(minutes=every_min)
    return files


NOSTALGIA_YT_TAGS = ["malayalam story", "malayalam emotional story", "malayalam shorts", "malayalam short story",
                     "kerala", "malayalam animation", "family story", "nostalgia", "heart touching story", "shorts"]
FIRST_COMMENT = "ഈ കഥ നിങ്ങളെ ആരെയെങ്കിലും ഓർമ്മിപ്പിച്ചോ? 👇 കമന്റിൽ പറയൂ ❤️\nദിവസവും പുതിയ കഥകൾക്ക് സബ്സ്ക്രൈബ് ചെയ്യൂ 🔔"


def nostalgia_post(story: Story, video_url: str, when: datetime) -> dict:
    """Grown-up nostalgia Short: comments on, not made for kids, first comment to start conversation."""
    skip = {"malayalam", "malayalamstory", "kerala", "mallureels", "malayalamreels", "nostalgia"}
    topical = [t for t in story.hashtags if t not in skip][:4]
    tags = ["shorts", "malayalam", "malayalamstory"] + topical + ["kerala", "malayalamshorts", "nostalgia"]
    title = f"{story.title_ml} | {story.title_en} | Malayalam Story #shorts"
    if len(title) > 100:
        title = f"{story.title_ml} | {story.title_en} #shorts"
    text = "\n\n".join(filter(None, [
        story.caption_ml, story.theme + ".",
        "🔔 ദിവസവും പുതിയ മലയാളം കഥകൾക്ക് സബ്സ്ക്രൈബ് ചെയ്യൂ\nSubscribe for a new heart-touching Malayalam story every day.",
        " ".join(f"#{t}" for t in dict.fromkeys(tags)),
    ]))
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": FIRST_COMMENT,
        "hasNotReadNotes": False, "media": [video_url], "mediaAltText": [],
        "providers": [{"network": "youtube"}],
        "publicationDate": {"dateTime": when.strftime("%Y-%m-%dT%H:%M:%S"), "timezone": TZ},
        "shortener": False, "smartLinkData": {"ids": []}, "text": text,
        "youtubeData": {"title": title[:100], "type": "short", "privacy": "public", "madeForKids": False,
                        "category": "FILM_ANIMATION", "isAiGeneratedContent": False,
                        "tags": list(dict.fromkeys(topical + NOSTALGIA_YT_TAGS))[:15]},
    }
    return {"date": when.strftime("%Y-%m-%dT%H:%M:%S+05:30"), "info": json.dumps(info, ensure_ascii=False)}
