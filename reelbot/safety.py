"""Free (no-API) content checks for kids story packs.

Every kids story must pass before it is rendered or scheduled:
  * no word from the blocklist (violence, abuse, fear, adult themes, insults, brands)
  * a `moral:` line, and the last scene states the moral (starts with "ഗുണപാഠം")
  * 5-9 scenes, narration lines short enough to read on screen
  * slug, title and moral unique across every pack in stories/
"""

from __future__ import annotations

import re
from pathlib import Path

from .storypack import parse

# Substrings, matched case-insensitively against everything a viewer can see or hear.
BLOCK_ML = [
    "കൊല്ലു", "കൊല്ലും", "കൊന്നു", "കൊന്നത്", "മരിച്ച", "മരണ", "ചോര", "രക്ത", "തല്ലി", "തല്ലു", "കുത്തിക്കൊ", "കുത്തിപ്പരിക്",
    "മദ്യ", "കള്ള്", "സിഗരറ്റ", "ബീഡി", "ലോട്ടറി", "ചൂതാട്ട", "പ്രേത", "ഭൂത", "യക്ഷി", "പിശാച",
    "മണ്ടൻ", "പൊട്ടൻ", "കഴുതേ", "കഴുതക്കുട്ടി", "തെണ്ടി", "ശവ", "ആത്മഹത്യ", "തോക്ക്", "ബോംബ", "യുദ്ധ",
    "ജാതി", "പാകിസ്ഥാൻ", "പാർട്ടി", "ഹർത്താൽ", "പോലീസ് പിടി", "ജയിൽ", "കറുമ്പ", "തടിയ",
]
BLOCK_EN = [
    "kill", "dead", "death", "die", "blood", "beat", "slap", "alcohol", "beer", "drunk", "smoke",
    "cigarette", "lottery", "gamble", "ghost", "devil", "stupid", "idiot", "hate", "gun", "knife",
    "bomb", "war", "dies", "died", "caste", "religion", "politics", "political", "jail", "fat", "ugly", "sexy", "date",
]
HASHTAG_BLOCK = {"lottery", "funny", "love", "sexy", "viral"}
MAX_NARRATION = 140  # characters per scene line


def _visible_text(story) -> str:
    parts = [story.title_ml, story.title_en, story.caption_ml, story.theme, " ".join(story.hashtags)]
    for sc in story.scenes:
        parts += [sc.narration_ml, sc.dialogue_ml]
    return "\n".join(parts)


LOSS_OK = {"മരിച്ച", "മരണ", "dead", "death", "die", "dies", "died"}  # allowed in grown-up nostalgia


def check_story(slug: str, story, moral: str, kids: bool = True) -> list[str]:
    problems = []
    text = _visible_text(story) + "\n" + moral
    low = text.lower()
    for w in BLOCK_ML:
        if not kids and w in LOSS_OK:
            continue
        if w in text:
            problems.append(f"blocked word {w!r}")
    for w in BLOCK_EN:
        if not kids and w in LOSS_OK:
            continue
        if re.search(rf"\b{re.escape(w)}s?\b", low):
            problems.append(f"blocked word {w!r}")
    for tag in story.hashtags:
        if tag.lower() in HASHTAG_BLOCK:
            problems.append(f"hashtag #{tag} not suitable for kids")
    if kids and not moral:
        problems.append("missing 'moral:' line")
    if not 5 <= len(story.scenes) <= 9:
        problems.append(f"{len(story.scenes)} scenes (want 5-9)")
    if kids and story.scenes and not story.scenes[-1].narration_ml.startswith("ഗുണപാഠം"):
        problems.append("last scene must state the moral (start with ഗുണപാഠം)")
    for i, sc in enumerate(story.scenes, 1):
        if len(sc.narration_ml) > MAX_NARRATION:
            problems.append(f"scene {i} narration too long ({len(sc.narration_ml)} chars)")
        if sc.ambience not in {"rain", "night", "wind", "indoor", "none"}:
            problems.append(f"scene {i} unknown ambience {sc.ambience!r}")
        if re.match(r"\s*[a-z_]+\s*:", sc.narration_ml):
            problems.append(f"scene {i} narration looks like dialogue (move it after the second ||)")
        elif re.search(r"[A-Za-z]", sc.narration_ml + sc.dialogue_ml):
            problems.append(f"scene {i} has Latin letters in spoken Malayalam text")
        if not sc.narration_ml.strip():
            problems.append(f"scene {i} has no narration")
    if not story.title_en or story.title_en == slug:
        problems.append("missing English title")
    return problems


def morals(text: str) -> dict[str, str]:
    """slug -> moral (the storypack parser ignores unknown keys, so read them here)."""
    out, slug = {}, None
    for ln in text.splitlines():
        if ln.startswith("###"):
            slug = ln[3:].strip()
        elif slug and ln.startswith("moral:"):
            out[slug] = ln.partition(":")[2].strip()
    return out


def lint(paths: list[Path], all_packs: list[Path] | None = None, kids: bool = True) -> dict[str, list[str]]:
    """Check kids packs. `all_packs` (default: every pack beside them) is used for uniqueness."""
    report: dict[str, list[str]] = {}
    seen_slug, seen_title, seen_moral = {}, {}, {}
    pool = sorted(set(all_packs or [p for path in paths for p in path.parent.glob("*.txt")]) | set(paths))
    for pack in pool:
        text = pack.read_text(encoding="utf-8")
        ms = morals(text)
        for slug, story in parse(text):
            key = f"{pack.name}:{slug}"
            probs = check_story(slug, story, ms.get(slug, ""), kids) if pack in paths else []
            for table, value in ((seen_slug, slug), (seen_title, story.title_ml.strip()), (seen_moral, ms.get(slug))):
                if value and value in table and table[value] != key:
                    probs.append(f"duplicate of {table[value]}: {value!r}")
                elif value:
                    table[value] = key
            if probs and pack in paths:
                report[key] = probs
    return report
