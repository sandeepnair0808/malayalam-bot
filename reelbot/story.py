"""Story writing: Claude writes a short Malayalam story split into reel scenes."""

from __future__ import annotations

import random
from typing import Iterable

from . import claude
from .config import Settings
from .models import Story

THEMES = [
    "grandmother secretly saving the best sweets for her grandchild",
    "first day of school in a Kerala village, rain and a new umbrella",
    "father coming home late with a parcel of hot parippu vada",
    "summer vacation at the ancestral tharavad with cousins",
    "mother waking up early to make breakfast before everyone",
    "grandfather teaching how to fly a kite from the paddy field bund",
    "Onam pookkalam competition among siblings",
    "monsoon power cut, the whole family around a kerosene lamp telling stories",
    "elder sister sharing her pocket money for a school trip",
    "waiting at the bus stop for an uncle returning from the Gulf",
    "a child's fear of the dark and grandmother's lullaby",
    "Vishu kaineettam from grandparents",
    "a broken slate pencil and a best friend at the village school",
    "old couple's quiet love: grandfather combing grandmother's hair",
    "the family's first television and the Sunday afternoon movie",
    "mother always says she likes the burnt dosa at the bottom of the pile",
    "father's old bicycle that he never replaced, and the new one the child got",
    "the extra plate grandmother always set at lunch, and who it was for",
    "the letter from abroad that the child read aloud to an illiterate grandmother",
    "the night bus father took every week so he could be home on Sunday",
]

SYSTEM = """\
You write short, emotional Malayalam stories for Instagram Reels in the style of nostalgic
Kerala "kutti kaalam" (childhood) animations: warm, gentle, often bittersweet family moments,
told by a narrator remembering their childhood. Language is natural, spoken Malayalam
(not overly literary), easy to follow when read as subtitles.

What makes a story worth sharing (the craft):
- Build it around ONE small, concrete object or habit (an umbrella always tilted one way,
  a tiffin box with one extra dosa, a radio only switched on at 7) that is planted early and
  pays off at the end. No abstract statements about love or sacrifice.
- Plant a small mystery or "complaint" in the first two scenes that the viewer only
  understands at the end. The child narrator misreads it; the grown-up narrator understands.
- The turn comes in the last 2-3 scenes, often by a time jump ("years later...") where the
  narrator repeats the same act for someone else and finally understands.
- Show, don't tell: the final line names the realisation in a few plain words, and never
  explains the moral.
- One short line of dialogue in the middle (in quotes) makes the characters feel real.
- Avoid clichés: death-bed scenes, hospital beds, crying faces, villains, sermons.

Rules:
- 6 to 9 scenes. The whole reel should run 30-60 seconds when narrated.
- Each narration_ml is 1-2 short sentences. subtitle_ml is a tight version of it that fits
  on a phone screen (at most 2 lines of ~32 characters).
- The first scene must hook in the first 2 seconds; the last scene lands the emotion
  (a twist, a realisation, or a quiet line that makes people tag their family).
- Keep a small, fixed cast (1-4 characters) with very specific, consistent visual designs,
  because an illustrator will draw every scene from your descriptions.
- Visual descriptions are concrete and drawable as flat vector art: one clear moment per
  scene, simple poses, Kerala village setting (tiled-roof house, wooden pillars, coconut
  trees, red-oxide floor, paddy fields, etc.).
- Original story. Do not reuse lines, characters or names from existing films or creators.
- Hashtags: no '#' prefix, no spaces.
"""


def build_prompt(theme: str, recent_titles: Iterable[str]) -> str:
    recent = "\n".join(f"- {t}" for t in recent_titles) or "- (none yet)"
    return (
        f"Write today's reel story.\n\nTheme: {theme}\n\n"
        f"Recently posted titles (do not repeat these ideas):\n{recent}\n"
    )


def pick_theme(recent_themes: Iterable[str], rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    used = {t.lower() for t in recent_themes}
    fresh = [t for t in THEMES if t.lower() not in used]
    return rng.choice(fresh or THEMES)


def write_story(settings: Settings, theme: str, recent_titles: Iterable[str] = ()) -> Story:
    return claude.parse(
        model=settings.model,
        system=SYSTEM,
        prompt=build_prompt(theme, recent_titles),
        schema=Story,
        effort=settings.story_effort,
    )
