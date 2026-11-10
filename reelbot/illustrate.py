"""Illustration: Claude draws each scene as a flat-vector SVG, rendered to PNG.

Scene 1 is drawn first and then handed to the remaining scenes as a reference, so
characters and the background stay consistent across the reel. The shared style
guide, character sheet and reference SVG live in a cached system block, so the
per-scene calls mostly pay for their own output.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.etree import ElementTree

import cairosvg

from . import claude
from .config import Settings
from .models import Scene, Story

log = logging.getLogger(__name__)

STYLE_GUIDE = """\
You are an illustrator for a Malayalam storytelling Instagram page. You draw single frames
as hand-written SVG in a flat, minimal, warm vector style:

- Canvas: <svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">.
- Flat shapes, no outlines or thin dark outlines only, soft muted palette (sage green walls,
  brown wooden beams/rafters, red-oxide floor, cream and faded-blue clothing, warm brown skin
  tones with soft pink cheek blush). Gentle radial/linear gradients are fine; no photo realism.
- Characters are simple and rounded: big round heads, dot or curved-line eyes (closed happy
  eyes for smiles), small mouths, simple limbs, clothes as flat shapes with small dot patterns.
- Background fills the whole canvas edge to edge (the video slowly zooms/pans, so nothing
  important touches the edges). Keep faces and the main action between y=250 and y=1350.
  The bottom ~500px is floor/ground only: subtitles are drawn there later.
- Absolutely no text, letters, numbers or logos in the image.
- Pure static SVG: no <script>, no <foreignObject>, no external images/fonts/links, no CSS
  animations, no <text>. Use <defs>/<g>/<use> to stay compact. Keep it under ~400 elements.

Output ONLY the SVG document, starting with <svg and ending with </svg>. No prose, no code fences.
"""

_SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S | re.I)
_FORBIDDEN = re.compile(r"<\s*(script|foreignObject)\b.*?(</\s*\1\s*>|/>)", re.S | re.I)
_EXTERNAL_HREF = re.compile(r"""(xlink:)?href\s*=\s*["'](?!#)[^"']*["']""", re.I)


def character_sheet(story: Story) -> str:
    lines = [f"- {c.id} ({c.name_ml}): {c.look}" for c in story.characters]
    return "Setting: " + story.setting + "\n\nCharacters (draw them exactly like this every time):\n" + "\n".join(lines)


def extract_svg(raw: str) -> str:
    match = _SVG_RE.search(raw)
    if not match:
        raise ValueError("no <svg> element in response")
    svg = match.group(0)
    svg = _FORBIDDEN.sub("", svg)
    svg = _EXTERNAL_HREF.sub("", svg)
    if "xmlns=" not in svg[:300]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    ElementTree.fromstring(svg)  # raises on malformed XML
    return svg


def render_png(svg: str, out: Path, width: int, height: int) -> Path:
    # Render at 2x so the slow zoom stays crisp.
    cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        write_to=str(out),
        output_width=width * 2,
        output_height=height * 2,
        unsafe=False,
    )
    return out


def fallback_svg(width: int = 1080, height: int = 1920) -> str:
    """Plain backdrop used when a scene can't be drawn; keeps the pipeline going."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><linearGradient id="w" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#cfd8c4"/><stop offset="1" stop-color="#a9b79c"/></linearGradient></defs>
<rect width="{width}" height="{height}" fill="url(#w)"/>
<rect y="0" width="{width}" height="380" fill="#7a5233"/>
<g fill="#5e3d24">{''.join(f'<rect y="{40 + i * 48}" width="{width}" height="14"/>' for i in range(7))}</g>
<rect x="60" y="760" width="210" height="300" rx="10" fill="#4a2f1d"/><rect x="810" y="760" width="210" height="300" rx="10" fill="#4a2f1d"/>
<rect y="1300" width="{width}" height="{height - 1300}" fill="#8f4a35"/>
<rect y="1300" width="{width}" height="40" fill="#6d3626"/>
</svg>"""


def _scene_prompt(index: int, total: int, scene: Scene, has_reference: bool) -> str:
    ref = (
        "Keep the characters, colours, house and background consistent with the reference frame "
        "(reuse its shapes for the same characters and location; change poses, expressions, "
        "framing and props to fit this moment).\n\n"
        if has_reference
        else ""
    )
    return (
        f"Draw frame {index + 1} of {total}.\n\n{ref}"
        f"Characters in frame: {', '.join(scene.characters) or 'none'}\n"
        f"Moment: {scene.visual}\n"
        f"(Narration, for mood only — do not write it in the image: {scene.narration_ml})"
    )


def _system(story: Story, reference_svg: str | None):
    text = STYLE_GUIDE + "\n\n" + character_sheet(story)
    if reference_svg:
        text += "\n\nReference frame (frame 1 of this reel):\n" + reference_svg
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def draw_scene(settings: Settings, story: Story, index: int, reference_svg: str | None) -> str:
    scene = story.scenes[index]
    prompt = _scene_prompt(index, len(story.scenes), scene, reference_svg is not None)
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            raw = claude.text(settings.model, _system(story, reference_svg), prompt, settings.art_effort)
            svg = extract_svg(raw)
            # Validate that cairo can actually render it.
            cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=108, output_height=192)
            return svg
        except claude.ClaudeRefusal:
            raise
        except Exception as err:  # malformed SVG etc. -> retry once
            last_err = err
            log.warning("scene %d attempt %d failed: %s", index + 1, attempt + 1, err)
    log.error("scene %d: using fallback backdrop (%s)", index + 1, last_err)
    return fallback_svg(settings.width, settings.height)


def illustrate(settings: Settings, story: Story, workdir: Path, max_workers: int = 4) -> list[Path]:
    """Draw all scenes; returns PNG paths in scene order."""
    workdir.mkdir(parents=True, exist_ok=True)
    svgs: list[str | None] = [None] * len(story.scenes)

    log.info("drawing scene 1/%d (reference frame)", len(story.scenes))
    svgs[0] = draw_scene(settings, story, 0, None)
    reference = svgs[0]

    def work(i: int) -> tuple[int, str]:
        log.info("drawing scene %d/%d", i + 1, len(story.scenes))
        return i, draw_scene(settings, story, i, reference)

    rest = list(range(1, len(story.scenes)))
    if rest:
        # Draw one more scene on its own so the cached system prompt exists
        # before the parallel calls start.
        i, svgs[rest[0]] = work(rest[0])
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for i, svg in pool.map(work, rest[1:]):
            svgs[i] = svg

    pngs = []
    for i, svg in enumerate(svgs):
        assert svg is not None
        (workdir / f"scene_{i + 1:02d}.svg").write_text(svg, encoding="utf-8")
        pngs.append(render_png(svg, workdir / f"scene_{i + 1:02d}.png", settings.width, settings.height))
    return pngs
