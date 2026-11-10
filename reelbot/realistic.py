"""3D animated-film scenes with Google's Gemini image model + Veo video.

Pipeline (every step is cached on disk, so a re-run only redoes what is missing):
  1. Character sheets: one full-body reference image per character (consistent design).
  2. Keyframes: one 9:16 still per scene, generated with the sheets of the characters in
     that scene as reference images, so faces and clothes stay the same.
  3. Clips: Veo turns each keyframe into a short video (image-to-video) using the
     scene's action as the motion prompt. If Veo refuses or fails, that scene falls back
     to the keyframe with a camera move, so the reel still renders.

Auth: the google-genai SDK reads GEMINI_API_KEY / GOOGLE_API_KEY (Gemini Developer API),
or GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION (Vertex AI,
needs application-default credentials).
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import Settings
from .models import Scene, Story

log = logging.getLogger(__name__)

STYLE = (
    "Style: high-quality 3D animated feature film still (Pixar/Disney-like CGI), soft global "
    "illumination, warm cinematic colour grading, expressive but natural faces, detailed "
    "textures (cotton clothes, wet mud, wooden pillars, red-oxide floor), shallow depth of field. "
    "Setting: a village in Kerala, India."
)
NO_TEXT = "No text, letters, subtitles, captions, logos or watermarks anywhere in the image."
NEGATIVE = (
    "text, subtitles, captions, watermark, logo, distorted faces, extra fingers, extra limbs, "
    "morphing, flicker, sudden camera cuts, photorealistic live-action people"
)
VEO_DURATIONS = (4, 6, 8)


class GenerationError(RuntimeError):
    pass


def _client():
    try:
        from google import genai
    except ImportError as err:  # pragma: no cover
        raise GenerationError("pip install 'google-genai>=2.30,<3' to use REELBOT_STYLE=3d") from err
    return genai.Client()


def _types():
    from google.genai import types

    return types


def veo_duration(seconds: float) -> int:
    """Shortest clip length Veo offers that covers the scene (longer scenes get slowed/held)."""
    for d in VEO_DURATIONS:
        if d >= seconds:
            return d
    return VEO_DURATIONS[-1]


def character_prompt(story: Story, char) -> str:
    return (
        f"{STYLE}\nCharacter reference sheet for an animated short film: a single full-body view of "
        f"{char.look}, standing in a relaxed neutral pose, facing the camera, gentle expression, "
        f"plain light-grey studio background, even lighting. Only this one character. {NO_TEXT}"
    )


def keyframe_prompt(story: Story, scene: Scene, names: dict[str, str]) -> str:
    cast = "; ".join(f"{names.get(c, c)} (see the reference image labelled {c})" for c in scene.characters)
    cast_line = f"Characters in the shot: {cast}. Keep their faces, hair, age, body and clothes exactly as in the reference images.\n" if cast else "No people in this shot.\n"
    return (
        f"{STYLE}\nRecurring location: {story.setting}\n"
        f"{cast_line}"
        f"Shot: {scene.visual}\n"
        f"Mood: {scene.narration_ml} {scene.dialogue_ml}".strip() + "\n"
        "Vertical 9:16 frame for a phone; keep faces and the main action in the upper and middle part "
        f"of the frame, the bottom fifth is calm floor/ground (subtitles go there). {NO_TEXT}"
    )


def motion_prompt(scene: Scene, names: dict[str, str]) -> str:
    speaking = ""
    if scene.speaker and scene.dialogue_ml:
        speaking = f" {names.get(scene.speaker, scene.speaker)} talks softly with natural lip movement; everyone else keeps their mouth closed."
    else:
        speaking = " Nobody speaks; mouths stay closed or smiling."
    return (
        f"Gentle, natural animation of this 3D animated film shot. {scene.action or 'Subtle idle motion: breathing, blinking, small head turns.'}"
        f"{speaking} Smooth slow camera, no cuts, consistent characters, nothing new enters the frame. "
        f"Context: {scene.visual}"
    )


def _image_bytes(response) -> bytes:
    for cand in getattr(response, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            data = getattr(getattr(part, "inline_data", None), "data", None)
            if data:
                return data
    reason = ""
    try:
        reason = str(response.candidates[0].finish_reason)
    except Exception:
        reason = str(getattr(response, "prompt_feedback", ""))
    raise GenerationError(f"image model returned no image ({reason})")


class Studio:
    def __init__(self, settings: Settings, client=None):
        self.s = settings
        self.client = client or _client()
        self.types = _types()

    # -- images ------------------------------------------------------------
    def _image(self, prompt: str, refs: list[tuple[str, Path]], aspect: str) -> bytes:
        t = self.types
        contents: list = []
        for label, path in refs:
            contents.append(f"Reference image labelled {label}:")
            contents.append(t.Part.from_bytes(data=path.read_bytes(), mime_type="image/png"))
        contents.append(prompt)
        config = t.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=t.ImageConfig(aspect_ratio=aspect, image_size=self.s.image_size),
        )
        last: Exception | None = None
        for attempt in range(3):
            try:
                resp = self.client.models.generate_content(model=self.s.image_model, contents=contents, config=config)
                return _image_bytes(resp)
            except Exception as err:  # transient errors / empty responses
                last = err
                log.warning("image generation attempt %d failed: %s", attempt + 1, err)
                time.sleep(4 * (attempt + 1))
        raise GenerationError(f"image generation failed: {last}")

    def character_sheets(self, story: Story, outdir: Path) -> dict[str, Path]:
        outdir.mkdir(parents=True, exist_ok=True)
        sheets = {}
        for char in story.characters:
            path = outdir / f"{char.id}.png"
            if not path.exists():
                log.info("character sheet: %s", char.id)
                path.write_bytes(self._image(character_prompt(story, char), [], "3:4"))
            sheets[char.id] = path
        return sheets

    def keyframe(self, story: Story, index: int, sheets: dict[str, Path], out: Path) -> Path:
        if out.exists():
            return out
        scene = story.scenes[index]
        names = {c.id: c.name_ml for c in story.characters}
        refs = [(c, sheets[c]) for c in scene.characters if c in sheets]
        log.info("keyframe %d/%d", index + 1, len(story.scenes))
        out.write_bytes(self._image(keyframe_prompt(story, scene, names), refs, "9:16"))
        return out

    # -- video -------------------------------------------------------------
    def clip(self, story: Story, index: int, keyframe: Path, seconds: float, out: Path) -> Path | None:
        """Animate one keyframe with Veo. Returns None (caller falls back to the still) on failure."""
        if out.exists():
            return out
        t = self.types
        scene = story.scenes[index]
        names = {c.id: c.name_ml for c in story.characters}
        cfg = dict(
            aspect_ratio="9:16",
            duration_seconds=veo_duration(seconds),
            resolution=self.s.video_resolution,
            negative_prompt=NEGATIVE,
            number_of_videos=1,
        )
        if getattr(self.client, "vertexai", False):
            cfg["generate_audio"] = False  # we add our own Malayalam voice + ambience
        try:
            op = self.client.models.generate_videos(
                model=self.s.video_model,
                source=t.GenerateVideosSource(
                    prompt=motion_prompt(scene, names),
                    image=t.Image(image_bytes=keyframe.read_bytes(), mime_type="image/png"),
                ),
                config=t.GenerateVideosConfig(**cfg),
            )
            deadline = time.monotonic() + self.s.video_timeout
            while not op.done:
                if time.monotonic() > deadline:
                    raise GenerationError("Veo timed out")
                time.sleep(10)
                op = self.client.operations.get(op)
            if getattr(op, "error", None):
                raise GenerationError(f"Veo error: {op.error}")
            videos = getattr(op.result, "generated_videos", None) or []
            if not videos:
                filtered = getattr(op.result, "rai_media_filtered_reasons", None)
                raise GenerationError(f"Veo returned no video (filtered: {filtered})")
            video = videos[0].video
            self.client.files.download(file=video)
            partial = out.with_suffix(".part.mp4")
            video.save(str(partial))
            from .voice import probe_duration

            probe_duration(partial)  # raises if the download is not a playable video
            partial.replace(out)
            log.info("clip %d/%d ready (%ss)", index + 1, len(story.scenes), cfg["duration_seconds"])
            return out
        except Exception as err:
            log.warning("scene %d: Veo failed (%s); using the still keyframe instead", index + 1, err)
            return None

    # -- all ---------------------------------------------------------------
    def produce(self, story: Story, reel_dir: Path, durations: list[float]) -> list[tuple[Path, Path | None]]:
        scenes_dir = reel_dir / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        sheets = self.character_sheets(story, reel_dir / "characters")
        keyframes = [self.keyframe(story, i, sheets, scenes_dir / f"scene_{i + 1:02d}.png") for i in range(len(story.scenes))]
        if not self.s.ai_video:
            return [(k, None) for k in keyframes]
        with ThreadPoolExecutor(max_workers=self.s.video_workers) as pool:
            clips = list(pool.map(
                lambda i: self.clip(story, i, keyframes[i], durations[i], scenes_dir / f"scene_{i + 1:02d}.mp4"),
                range(len(story.scenes)),
            ))
        return list(zip(keyframes, clips))
