"""End-to-end orchestration: story -> art -> voice -> video -> (optional) Instagram."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from . import history
from .config import Settings
from .illustrate import illustrate, render_png
from .instagram import InstagramClient, PublishResult
from .models import Story
from .story import pick_theme, write_story
from .video import SceneClip, assemble, scene_duration
from .voice import SceneVoice, narrate_story, reading_time

log = logging.getLogger(__name__)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "reel"


def new_reel_dir(settings: Settings, story: Story) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    d = settings.output_dir / f"{stamp}-{_slug(story.title_en)}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_story(story: Story, reel_dir: Path) -> None:
    (reel_dir / "story.json").write_text(story.model_dump_json(indent=2), encoding="utf-8")
    (reel_dir / "caption.txt").write_text(story.instagram_caption() + "\n", encoding="utf-8")


def load_story(reel_dir: Path) -> Story:
    return Story.model_validate_json((reel_dir / "story.json").read_text(encoding="utf-8"))


def _scene_svg(image: Path) -> str | None:
    svg = image.with_suffix(".svg")
    return svg.read_text(encoding="utf-8") if svg.exists() else None


def scene_durations(story: Story, voices: list[SceneVoice]) -> list[float]:
    return [scene_duration(v.duration, reading_time(s.subtitle_ml)) for s, v in zip(story.scenes, voices)]


def _scene_video(image: Path) -> Path | None:
    clip = image.with_suffix(".mp4")
    return clip if clip.exists() else None


def render(settings: Settings, story: Story, reel_dir: Path, images: list[Path],
           voices: list[SceneVoice] | None = None) -> Path:
    """Voice-over + video assembly from already-made scene images (and AI clips next to them, if any)."""
    work = reel_dir / "work"
    voices = voices or narrate_story(settings, story, work)
    clips = [
        SceneClip(
            image=img,
            audio=v.audio,
            duration=dur,
            camera=scene.camera,
            subtitle=scene.subtitle_ml,
            svg=_scene_svg(img),
            talk_audio=v.talk_audio,
            talk_offset=v.talk_offset,
            ambience=scene.ambience,
            video=_scene_video(img),
        )
        for scene, img, v, dur in zip(story.scenes, images, voices, scene_durations(story, voices))
    ]
    out = assemble(settings, clips, work, reel_dir / "reel.mp4")
    log.info("reel ready: %s (%.1fs)", out, sum(c.duration for c in clips))
    return out


def make(settings: Settings, theme: str | None = None, story: Story | None = None) -> Path:
    """Create a new reel. Returns the reel directory (contains reel.mp4, story.json, caption.txt)."""
    past = history.recent(settings.history_file)
    if story is None:
        theme = theme or pick_theme([p.get("theme_seed", "") for p in past])
        log.info("writing story: %s", theme)
        story = write_story(settings, theme, [p.get("title_ml", "") for p in past])
    reel_dir = new_reel_dir(settings, story)
    save_story(story, reel_dir)
    log.info("story '%s' (%d scenes) -> %s", story.title_ml, len(story.scenes), reel_dir)

    if settings.style == "3d":
        from .realistic import Studio

        voices = narrate_story(settings, story, reel_dir / "work")
        pairs = Studio(settings).produce(story, reel_dir, scene_durations(story, voices))
        render(settings, story, reel_dir, [img for img, _ in pairs], voices)
    else:
        images = illustrate(settings, story, reel_dir / "scenes")
        render(settings, story, reel_dir, images)
    history.append(settings.history_file, {
        "dir": reel_dir.name,
        "title_ml": story.title_ml,
        "title_en": story.title_en,
        "theme_seed": theme or "",
        "published": False,
    })
    return reel_dir


def rebuild(settings: Settings, reel_dir: Path, retry_ai: bool = False) -> Path:
    """Re-render voice/video from an existing reel dir without calling Claude again.

    With the 3d style, missing keyframes are always generated; `retry_ai` also retries
    scenes whose Veo clip failed earlier.
    """
    story = load_story(reel_dir)
    for svg in sorted((reel_dir / "scenes").glob("scene_*.svg")):  # e.g. examples/ ship only the SVGs
        png = svg.with_suffix(".png")
        if not png.exists():
            render_png(svg.read_text(encoding="utf-8"), png, settings.width, settings.height)
    if not (reel_dir / "caption.txt").exists():
        save_story(story, reel_dir)
    images = sorted((reel_dir / "scenes").glob("scene_*.png"))
    if settings.style == "3d" and (retry_ai or len(images) != len(story.scenes)):
        # finish (or retry) the missing 3D keyframes / clips; finished ones are reused from disk
        from .realistic import Studio

        voices = narrate_story(settings, story, reel_dir / "work")
        pairs = Studio(settings).produce(story, reel_dir, scene_durations(story, voices))
        return render(settings, story, reel_dir, [img for img, _ in pairs], voices)
    if len(images) != len(story.scenes):
        raise SystemExit(f"expected {len(story.scenes)} scene images in {reel_dir / 'scenes'}, found {len(images)}")
    return render(settings, story, reel_dir, images)


def publish(settings: Settings, reel_dir: Path, video_url: str | None = None) -> PublishResult:
    marker = reel_dir / "published.json"
    if marker.exists():
        raise SystemExit(f"{reel_dir} was already published: {marker.read_text(encoding='utf-8')}")
    caption = (reel_dir / "caption.txt").read_text(encoding="utf-8").strip()
    result = InstagramClient.from_settings(settings).publish_reel(reel_dir / "reel.mp4", caption, video_url=video_url)
    marker.write_text(json.dumps({"media_id": result.media_id, "permalink": result.permalink}) + "\n", encoding="utf-8")
    history.update(settings.history_file, reel_dir.name, published=True, media_id=result.media_id,
                   permalink=result.permalink)
    return result
