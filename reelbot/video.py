"""Assemble scenes + narration + music + subtitles into a 1080x1920 H.264 reel with ffmpeg."""

from __future__ import annotations

import logging
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .animate import render_animated, voice_envelope
from .config import Settings
from .subtitles import Cue, write_ass

log = logging.getLogger(__name__)

LEAD_IN = 0.12  # silence before each narration line
TAIL = 0.28  # breathing room after it
FADE = 0.15  # dip between scenes


@dataclass
class SceneClip:
    image: Path
    audio: Path | None
    duration: float
    camera: str
    subtitle: str
    svg: str | None = None  # when set, the scene is animated frame by frame
    talk_audio: Path | None = None  # speech that drives the on-screen speaker's mouth
    talk_offset: float = 0.0  # seconds into the scene's speech where talk_audio starts
    ambience: str = "none"
    video: Path | None = None  # AI-generated clip for this scene (3d style)


def scene_duration(spoken: float, reading: float) -> float:
    return round(max(spoken + LEAD_IN + TAIL, reading), 2)


def zoompan_expr(camera: str, frames: int, w: int, h: int, fps: int) -> str:
    n = max(frames - 1, 1)
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    if camera == "zoom_out":
        z, x, y = f"1.15-0.15*on/{n}", center_x, center_y
    elif camera == "pan_left":
        z, x, y = "1.12", f"(iw-iw/zoom)*(1-on/{n})", center_y
    elif camera == "pan_right":
        z, x, y = "1.12", f"(iw-iw/zoom)*on/{n}", center_y
    elif camera == "still":
        z, x, y = f"1.02+0.02*on/{n}", center_x, center_y
    else:  # zoom_in
        z, x, y = f"1+0.15*on/{n}", center_x, center_y
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps}"


def run(cmd: list[str]) -> None:
    log.debug("ffmpeg: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{proc.stderr[-3000:]}")


def _fades(clip: SceneClip, first: bool, last: bool) -> list[str]:
    vf = []
    if not first:
        vf.append(f"fade=t=in:st=0:d={FADE}")
    if not last:
        vf.append(f"fade=t=out:st={clip.duration - FADE:.3f}:d={FADE}")
    return vf


def fit_clip_filter(src_seconds: float, target: float, w: int, h: int) -> str:
    """Scale/crop an AI clip to the reel frame and fit it to the scene length.

    Slightly long scenes are slowed down (up to 1.35x); anything longer holds the last frame.
    """
    vf = [f"scale={w}:{h}:force_original_aspect_ratio=increase", f"crop={w}:{h}", "setsar=1"]
    if target > src_seconds + 0.01:
        stretch = min(target / src_seconds, 1.35)
        if stretch > 1.001:
            vf.append(f"setpts={stretch:.4f}*PTS")
        hold = target - src_seconds * stretch
        if hold > 0.01:
            vf.append(f"tpad=stop_mode=clone:stop_duration={hold:.3f}")
    return ",".join(vf)


def render_scene(settings: Settings, clip: SceneClip, out: Path, first: bool, last: bool) -> Path:
    if clip.video:
        from .voice import probe_duration

        vf = [fit_clip_filter(probe_duration(clip.video), clip.duration, settings.width, settings.height),
              f"fps={settings.fps}", *_fades(clip, first, last), "format=yuv420p"]
        run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(clip.video), "-vf", ",".join(vf),
            "-t", f"{clip.duration:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-an", str(out),
        ])
        return out
    if clip.svg and settings.animate:
        env = voice_envelope(clip.talk_audio, clip.duration, settings.fps, LEAD_IN + clip.talk_offset)
        return render_animated(clip.svg, clip.duration, clip.camera, out, fps=settings.fps, width=settings.width,
                               height=settings.height, envelope=env, vf_extra=_fades(clip, first, last))
    frames = max(int(round(clip.duration * settings.fps)), 1)
    vf = [zoompan_expr(clip.camera, frames, settings.width, settings.height, settings.fps)]
    vf += _fades(clip, first, last)
    vf.append("format=yuv420p")
    run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(clip.image),
        "-vf", ",".join(vf), "-frames:v", str(frames), "-r", str(settings.fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-an", str(out),
    ])
    return out


# Synthesised background beds (lavfi sources), mixed quietly under the voice.
AMBIENCE = {
    # pink noise band-passed like rain on leaves + low brown-noise rumble
    "rain": ("anoisesrc=color=pink:r=44100:a=0.5,highpass=f=400,lowpass=f=6500,"
             "volume=0.35[ra];anoisesrc=color=brown:r=44100:a=0.5,lowpass=f=300,volume=0.25[rb];"
             "[ra][rb]amix=inputs=2:normalize=0"),
    # crickets: high tone chopped into chirps, plus faint night air
    "night": ("sine=f=4700:r=44100,tremolo=f=38:d=1,tremolo=f=1.6:d=0.9,volume=0.05[ca];"
              "anoisesrc=color=brown:r=44100:a=0.3,lowpass=f=500,volume=0.12[cb];[ca][cb]amix=inputs=2:normalize=0"),
    "wind": "anoisesrc=color=brown:r=44100:a=0.6,lowpass=f=900,tremolo=f=0.15:d=0.7,volume=0.35",
    "indoor": "anoisesrc=color=brown:r=44100:a=0.3,lowpass=f=250,volume=0.15",
}
AMBIENCE_GAIN = 0.55


def _ambience_chain(kind: str, dur: float, label: str, n: int) -> str | None:
    src = AMBIENCE.get(kind)
    if not src:
        return None
    # rename internal labels so several beds can coexist in one graph
    for tag in ("ra", "rb", "ca", "cb"):
        src = src.replace(f"[{tag}]", f"[{tag}{n}]")
    fade = min(0.4, dur / 4)
    return (f"{src},aformat=channel_layouts=stereo,atrim=0:{dur:.3f},asetpts=N/SR/TB,"
            f"afade=t=in:d={fade:.2f},afade=t=out:st={dur - fade:.3f}:d={fade:.2f},volume={AMBIENCE_GAIN}[{label}]")


def ambience_runs(clips: list[SceneClip]) -> list[tuple[str, float, float]]:
    """(kind, start, duration) for each run of consecutive scenes with the same ambience."""
    runs: list[list] = []
    t = 0.0
    for c in clips:
        if runs and runs[-1][0] == c.ambience:
            runs[-1][2] += c.duration
        else:
            runs.append([c.ambience, t, c.duration])
        t += c.duration
    return [(k, s, d) for k, s, d in runs if k in AMBIENCE]


def build_audio(settings: Settings, clips: list[SceneClip], out: Path) -> Path:
    inputs: list[str] = []
    parts: list[str] = []
    labels: list[str] = []
    idx = 0
    delay_ms = int(LEAD_IN * 1000)
    for i, clip in enumerate(clips):
        if clip.audio:
            inputs += ["-i", str(clip.audio)]
            parts.append(
                f"[{idx}:a]aresample=44100,aformat=channel_layouts=stereo,"
                f"adelay={delay_ms}|{delay_ms},apad,atrim=0:{clip.duration:.3f}[s{i}]"
            )
            idx += 1
        else:
            parts.append(
                f"anullsrc=r=44100:cl=stereo,atrim=0:{clip.duration:.3f}[s{i}]"
            )
        labels.append(f"[s{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(clips)}:v=0:a=1[speech]")

    # one continuous bed per run of consecutive scenes sharing an ambience
    beds, t = [], 0.0
    for kind, start, dur in ambience_runs(clips):
        chain = _ambience_chain(kind, dur, f"bed{len(beds)}", len(beds))
        if chain:
            ms = int(start * 1000)
            parts.append(chain.replace(f"[bed{len(beds)}]", f",adelay={ms}|{ms}[bed{len(beds)}]"))
            beds.append(f"[bed{len(beds)}]")
    if beds:
        parts.append(f"[speech]{''.join(beds)}amix=inputs={len(beds) + 1}:duration=first:normalize=0[voice]")
    else:
        parts.append("[speech]anull[voice]")

    music = pick_music(settings.music_dir)
    total = sum(c.duration for c in clips)
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        parts.append(
            f"[{idx}:a]aresample=44100,aformat=channel_layouts=stereo,volume={settings.music_volume},"
            f"atrim=0:{total:.3f},afade=t=out:st={max(total - 1.5, 0):.3f}:d=1.5[bg]"
        )
        parts.append("[voice][bg]amix=inputs=2:duration=first:normalize=0[mix]")
        final = "[mix]"
    else:
        final = "[voice]"
    # Normalise to ~-14 LUFS, the loudness Instagram/YouTube target.
    parts.append(f"{final}loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[out]")
    final = "[out]"
    run([
        "ffmpeg", "-y", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(parts), "-map", final,
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", str(out),
    ])
    return out


def pick_music(music_dir: Path) -> Path | None:
    if not music_dir.is_dir():
        return None
    tracks = [p for p in music_dir.iterdir() if p.suffix.lower() in {".mp3", ".m4a", ".wav", ".ogg"}]
    return random.choice(tracks) if tracks else None


def _filter_path(path: Path) -> str:
    # Escape for use inside an ffmpeg filter argument.
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def assemble(settings: Settings, clips: list[SceneClip], workdir: Path, out: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, clip in enumerate(clips):
        log.info("rendering clip %d/%d (%.1fs, %s)", i + 1, len(clips), clip.duration, clip.camera)
        parts.append(render_scene(settings, clip, workdir / f"clip_{i + 1:02d}.mp4", i == 0, i == len(clips) - 1))

    concat_list = workdir / "clips.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    silent = workdir / "video_nosubs.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(silent)])

    audio = build_audio(settings, clips, workdir / "audio.m4a")

    cues, t = [], 0.0
    for clip in clips:
        cues.append(Cue(t + 0.1, t + clip.duration - 0.1, clip.subtitle))
        t += clip.duration
    ass = write_ass(cues, settings.font, workdir / "subs.ass", settings.width, settings.height)

    sub_filter = f"ass='{_filter_path(ass)}'"
    if settings.fonts_dir.is_dir():
        sub_filter = f"ass='{_filter_path(ass)}':fontsdir='{_filter_path(settings.fonts_dir)}'"
    out.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio),
        "-vf", sub_filter, "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", "-shortest", str(out),
    ])
    return out
