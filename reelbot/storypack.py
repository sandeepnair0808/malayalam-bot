"""Story packs: many ready-to-render reels in one compact text file.

Format (one block per story):

    ### burnt-dosa
    title: അമ്മയുടെ കരിഞ്ഞ ദോശ | Amma's Burnt Dosa
    theme: A mother always eats the burnt dosa ...
    narrator: man
    caption: നല്ല ദോശ മക്കൾക്ക്...
    tags: malayalam amma dosa kerala
    - kitchen | zoom_in | indoor | amma:cook | stove || narration in Malayalam ||
    - kitchen | still | indoor | amma:hold=burnt_dosa kid:point,talk | table:burnt || ഒരു ദിവസം ഞാൻ ചോദിച്ചു. || kid: അമ്മേ, ...?

Scene line: `- <bg>[+fx][+close] | <camera> | <ambience> | <cast tokens> | <props> || <narration> || [<speaker>: <dialogue>]`
Cast tokens and props are the reelbot.scenekit vocabulary, space separated.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Character, Scene, Story
from .scenekit import ALIASES, CHARACTERS

VOICES = {
    "appooppan": "old_man", "ammachi": "old_woman", "achan": "man", "grownup": "man", "uncle": "man",
    "amma": "woman", "teacher": "woman", "chechi": "teen_girl", "kid": "boy", "friend": "boy", "girl": "girl",
}
NAMES_ML = {
    "appooppan": "അപ്പൂപ്പൻ", "ammachi": "അമ്മൂമ്മ", "achan": "അച്ഛൻ", "grownup": "ഞാൻ (ഇന്ന്)", "uncle": "മാമൻ",
    "amma": "അമ്മ", "teacher": "ടീച്ചർ", "chechi": "ചേച്ചി", "kid": "ഞാൻ (കുട്ടി)", "friend": "കൂട്ടുകാരൻ", "girl": "അനിയത്തി",
}
LOOKS = {
    "appooppan": "elderly man, white side hair, white moustache, round glasses, cream shirt, white mundu",
    "ammachi": "elderly woman, white hair bun, round glasses, cream Kerala saree with gold border",
    "achan": "father in his thirties, black hair and moustache, off-white shirt, grey trousers",
    "grownup": "the narrator grown up, black hair and moustache, sky-blue shirt, grey trousers",
    "uncle": "uncle back from the Gulf, black hair and moustache, orange shirt, grey trousers",
    "amma": "mother, black hair bun, red bindi, gold earrings, maroon nightie with white dots",
    "teacher": "school teacher, black hair bun, blue saree with gold border",
    "chechi": "teenage elder sister, long braid, green churidar",
    "kid": "8 year old boy, short black hair, yellow shirt, blue shorts",
    "friend": "8 year old boy, green shirt, brown shorts",
    "girl": "6 year old girl, two pigtails with red ribbons, pink frock",
}
CAMERAS = {"zoom_in", "zoom_out", "pan_left", "pan_right", "still"}
FX = {"rain", "night", "sunset", "festive"}


class PackError(ValueError):
    pass


def _char(name: str) -> str:
    key = ALIASES.get(name, name)
    if key not in CHARACTERS:
        raise PackError(f"unknown character {name!r}")
    return key


def parse_scene(line: str, where: str) -> Scene:
    try:
        head, narration, *rest = [part.strip() for part in line.split("||")]
    except ValueError as err:
        raise PackError(f"{where}: expected '... || narration || dialogue'") from err
    dialogue = rest[0] if rest else ""
    fields = [f.strip() for f in head.split("|")]
    if len(fields) < 4:
        raise PackError(f"{where}: expected 'bg | camera | ambience | cast | props'")
    bg_spec, camera, ambience, cast_spec = fields[:4]
    props = fields[4].split() if len(fields) > 4 and fields[4] else []
    bg, *mods = bg_spec.split("+")
    fx = [m for m in mods if m in FX]
    shot = "close" if "close" in mods else "wide"
    if camera not in CAMERAS:
        raise PackError(f"{where}: unknown camera {camera!r}")
    cast = cast_spec.split()
    ids = []
    for tok in cast:
        ids.append(_char(tok.split(":")[0]))
    speaker, dlg = None, ""
    if dialogue:
        who, _, said = dialogue.partition(":")
        speaker, dlg = _char(who.strip()), said.strip()
        if speaker not in ids:
            raise PackError(f"{where}: speaker {who!r} is not in the scene's cast")
        # make sure the speaker's mouth can move
        cast = [t if _char(t.split(":")[0]) != speaker or "talk" in t else (t + (",talk" if ":" in t else ":talk")) for t in cast]
    art = {"bg": bg, "fx": fx, "shot": shot, "cast": cast, "props": props}
    visual = f"{bg} scene" + (f" with {', '.join(ids)}" if ids else "")
    return Scene(
        narration_ml=narration, dialogue_ml=dlg, subtitle_ml="", visual=visual, characters=ids,
        action=" ".join(cast), speaker=speaker, camera=camera, ambience=ambience, art=art,
    )


def parse(text: str) -> list[tuple[str, Story]]:
    stories = []
    blocks = re.split(r"^###\s*", text, flags=re.M)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        slug = lines[0].strip()
        meta, scenes = {}, []
        for i, ln in enumerate(lines[1:], 2):
            if ln.lstrip().startswith("-"):
                scenes.append(parse_scene(ln.lstrip()[1:].strip(), f"{slug} line {i}"))
            else:
                k, _, v = ln.partition(":")
                meta[k.strip()] = v.strip()
        title_ml, _, title_en = meta.get("title", slug).partition("|")
        ids = []
        for sc in scenes:
            for c in sc.characters:
                if c not in ids:
                    ids.append(c)
        story = Story(
            title_ml=title_ml.strip(), title_en=title_en.strip() or slug, theme=meta.get("theme", ""),
            setting="Kerala village home", narrator_voice=meta.get("narrator", "man"),
            characters=[Character(id=c, name_ml=NAMES_ML[c], look=LOOKS[c], voice=VOICES[c]) for c in ids],
            scenes=scenes, caption_ml=meta.get("caption", "").replace("\\n", "\n"),
            hashtags=meta.get("tags", "malayalam kerala").split(),
        )
        stories.append((slug, story))
    return stories


def write_pack(pack: Path, out_dir: Path) -> list[Path]:
    """Expand a pack into story directories (<out_dir>/<slug>/story.json + scene SVGs)."""
    from .pipeline import compile_art, save_story

    dirs = []
    for slug, story in parse(pack.read_text(encoding="utf-8")):
        d = out_dir / slug
        (d / "scenes").mkdir(parents=True, exist_ok=True)
        save_story(story, d)
        compile_art(story, d / "scenes")
        dirs.append(d)
    return dirs
