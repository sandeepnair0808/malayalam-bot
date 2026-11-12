"""Runtime settings, read from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional convenience for local runs
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    # Claude
    model: str = field(default_factory=lambda: _env("REELBOT_MODEL", "claude-opus-5-5"))
    story_effort: str = field(default_factory=lambda: _env("REELBOT_STORY_EFFORT", "high"))
    art_effort: str = field(default_factory=lambda: _env("REELBOT_ART_EFFORT", "medium"))

    # Voice
    tts: str = field(default_factory=lambda: _env("REELBOT_TTS", "edge"))
    voice: str = field(default_factory=lambda: _env("REELBOT_VOICE", "ml-IN-SobhanaNeural"))

    # Visual style: "cartoon" (Claude-drawn rigged SVG, animated locally) or
    # "3d" (Gemini image model keyframes + Veo video clips; needs GEMINI_API_KEY)
    style: str = field(default_factory=lambda: _env("REELBOT_STYLE", "cartoon").lower())
    image_model: str = field(default_factory=lambda: _env("REELBOT_IMAGE_MODEL", "gemini-3.1-flash-image"))
    image_size: str = field(default_factory=lambda: _env("REELBOT_IMAGE_SIZE", "2K"))
    ai_video: bool = field(default_factory=lambda: _env("REELBOT_AI_VIDEO", "1") not in ("0", "false", "no"))
    video_model: str = field(default_factory=lambda: _env("REELBOT_VIDEO_MODEL", "veo-3.1-generate-preview"))
    video_resolution: str = field(default_factory=lambda: _env("REELBOT_VIDEO_RESOLUTION", "720p"))
    video_workers: int = field(default_factory=lambda: int(_env("REELBOT_VIDEO_WORKERS", "2")))
    video_timeout: float = field(default_factory=lambda: float(_env("REELBOT_VIDEO_TIMEOUT", "900")))

    # Video
    # REELBOT_LANDSCAPE=1 renders 16:9 (1920x1080) for long-form compilations; default is 9:16 Shorts
    width: int = field(default_factory=lambda: 1920 if os.environ.get("REELBOT_LANDSCAPE") == "1" else 1080)
    height: int = field(default_factory=lambda: 1080 if os.environ.get("REELBOT_LANDSCAPE") == "1" else 1920)
    fps: int = 30
    # Animate tagged characters frame by frame (False = still image + camera move only).
    animate: bool = field(default_factory=lambda: _env("REELBOT_ANIMATE", "1") not in ("0", "false", "no"))
    font: str = field(default_factory=lambda: _env("REELBOT_FONT", "Manjari"))
    fonts_dir: Path = field(default_factory=lambda: Path(_env("REELBOT_FONTS_DIR", "assets/fonts")))
    music_dir: Path = field(default_factory=lambda: Path(_env("REELBOT_MUSIC_DIR", "assets/music")))
    end_card: str = field(default_factory=lambda: _env("REELBOT_END_CARD", "ഇഷ്ടമായെങ്കിൽ സബ്സ്ക്രൈബ് ചെയ്യൂ"))
    music_volume: float = field(default_factory=lambda: float(_env("REELBOT_MUSIC_VOLUME", "0.12")))

    # Paths
    output_dir: Path = field(default_factory=lambda: Path(_env("REELBOT_OUTPUT_DIR", "output")))
    history_file: Path = field(default_factory=lambda: Path(_env("REELBOT_HISTORY", "data/history.json")))

    # Instagram
    ig_user_id: str = field(default_factory=lambda: _env("IG_USER_ID"))
    ig_access_token: str = field(default_factory=lambda: _env("IG_ACCESS_TOKEN"))
    ig_graph_host: str = field(default_factory=lambda: _env("IG_GRAPH_HOST", "graph.facebook.com"))
    ig_graph_version: str = field(default_factory=lambda: _env("IG_GRAPH_VERSION", "v21.0"))
