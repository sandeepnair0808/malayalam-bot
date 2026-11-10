"""Frame-by-frame character animation for scene SVGs.

The illustrator tags parts of the drawing with `data-anim` attributes; this module
turns one static SVG into a sequence of frames by rewriting those parts' transforms
over time, adds the camera move, renders every frame with cairosvg, and pipes the
frames into ffmpeg.

Supported tags (all attributes optional except data-anim). data-pivot is "x,y" in the
coordinate system of the element's parent (canvas pixels for top-level elements):

  data-anim="blink"    eyes. Squash shut for ~0.12s every 2.5-4.5s.         data-pivot
  data-anim="talk"     open mouth (dark ellipse). Opens with the voice volume. data-pivot
  data-anim="breathe"  whole body. Slow vertical stretch.        data-pivot (feet) data-amp (%; 1.2)
  data-anim="swing"    arm / leg / head / umbrella. Rotates back and forth.
                       data-pivot (joint) data-amp (degrees; 8) data-period (s; 1.0) data-phase (0-1)
  data-anim="bob"      walking bounce. data-amp (px; 10) data-period (s; 0.5)
  data-anim="float"    gentle up/down. data-amp (px; 8) data-period (s; 3)
  data-anim="move"     slides across the scene over its duration. data-dx, data-dy (px)
  data-anim="rain"     falling rain layer, scrolled and tiled vertically. data-speed (px/s; 1400)
  data-anim="drift"    clouds etc., scrolled and tiled horizontally. data-speed (px/s; 25)

Several animations can be nested (e.g. `move` on the character, `bob` inside it,
`swing` on each leg).
"""

from __future__ import annotations

import copy
import logging
import math
import os
import random
import subprocess
from array import array
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import cairosvg

log = logging.getLogger(__name__)

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

ANIMS = {"blink", "talk", "breathe", "swing", "bob", "float", "move", "rain", "drift"}


@dataclass
class Part:
    anim: str
    node: ET.Element
    base_transform: str
    pivot: tuple[float, float]
    amp: float | None
    period: float | None
    phase: float
    speed: float | None
    dx: float
    dy: float
    seed: int


def _f(node: ET.Element, name: str) -> float | None:
    v = node.get(name)
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _pivot(node: ET.Element) -> tuple[float, float] | None:
    raw = node.get("data-pivot")
    if not raw:
        return None
    try:
        x, y = (float(v) for v in raw.replace(" ", ",").split(",") if v != "")
        return x, y
    except ValueError:
        return None


def count_tags(svg: str) -> int:
    return sum(1 for n in ET.fromstring(svg).iter() if n.get("data-anim") in ANIMS)


class SceneAnimator:
    """Holds a parsed scene and produces the SVG for any time t."""

    def __init__(self, svg: str, duration: float, camera: str, envelope: list[float] | None = None,
                 fps: int = 30, width: int = 1080, height: int = 1920):
        self.root = ET.fromstring(svg)
        self.duration = max(duration, 0.01)
        self.camera = camera
        self.envelope = envelope or []
        self.fps = fps
        self.w, self.h = width, height
        self.parts: list[Part] = []
        tagged = [n for n in self.root.iter() if n.get("data-anim") in ANIMS]
        for i, node in enumerate(tagged):
            anim = node.get("data-anim")
            pivot = _pivot(node)
            if anim in {"blink", "talk", "breathe", "swing"} and pivot is None:
                log.debug("skipping %s without data-pivot", anim)
                continue
            if anim in {"rain", "drift"}:
                self._tile(node, anim)
            self.parts.append(Part(
                anim=anim, node=node, base_transform=node.get("transform", ""),
                pivot=pivot or (0.0, 0.0), amp=_f(node, "data-amp"), period=_f(node, "data-period"),
                phase=_f(node, "data-phase") or 0.0, speed=_f(node, "data-speed"),
                dx=_f(node, "data-dx") or 0.0, dy=_f(node, "data-dy") or 0.0, seed=i,
            ))
        self._wrap_camera()

    # -- setup -------------------------------------------------------------
    def _tile(self, node: ET.Element, anim: str) -> None:
        """Duplicate the children shifted one screen up/left so scrolling wraps seamlessly."""
        children = list(node)
        if not children:
            return
        a = ET.SubElement(node, f"{{{SVG_NS}}}g")
        b = ET.SubElement(node, f"{{{SVG_NS}}}g")
        b.set("transform", f"translate(0,{-self.h})" if anim == "rain" else f"translate({-self.w},0)")
        for c in children:
            node.remove(c)
            a.append(c)
            b.append(copy.deepcopy(c))

    def _wrap_camera(self) -> None:
        self.camera_node = ET.Element(f"{{{SVG_NS}}}g")
        for child in list(self.root):
            if child.tag.endswith("defs"):
                continue
            self.root.remove(child)
            self.camera_node.append(child)
        self.root.append(self.camera_node)
        self.root.set("width", str(self.w))
        self.root.set("height", str(self.h))

    # -- motion ------------------------------------------------------------
    def _voice(self, t: float) -> float:
        if not self.envelope:
            return 0.0
        i = min(int(t * self.fps), len(self.envelope) - 1)
        return self.envelope[i]

    def _blink(self, t: float, seed: int) -> float:
        rng = random.Random(seed)
        start = rng.uniform(0.4, 2.0)
        while start < t + 1:
            if start <= t < start + 0.13:
                return 0.1
            start += rng.uniform(2.5, 4.5)
        return 1.0

    def _transform(self, p: Part, t: float) -> str:
        px, py = p.pivot
        about = lambda inner: f"translate({px:.2f},{py:.2f}) {inner} translate({-px:.2f},{-py:.2f})"  # noqa: E731
        if p.anim == "blink":
            return about(f"scale(1,{self._blink(t, p.seed):.3f})")
        if p.anim == "talk":
            open_ = 0.12 + 0.95 * min(1.0, self._voice(t))
            return about(f"scale(1,{open_:.3f})")
        if p.anim == "breathe":
            amp = (p.amp or 1.2) / 100
            return about(f"scale(1,{1 + amp * math.sin(2 * math.pi * t / 3.2 + p.phase * 6.283):.4f})")
        if p.anim == "swing":
            amp, period = p.amp if p.amp is not None else 8, p.period or 1.0
            return about(f"rotate({amp * math.sin(2 * math.pi * (t / period + p.phase)):.3f})")
        if p.anim == "bob":
            amp, period = p.amp if p.amp is not None else 10, p.period or 0.5
            return f"translate(0,{-amp * abs(math.sin(math.pi * (t / period + p.phase))):.2f})"
        if p.anim == "float":
            amp, period = p.amp if p.amp is not None else 8, p.period or 3.0
            return f"translate(0,{amp * math.sin(2 * math.pi * (t / period + p.phase)):.2f})"
        if p.anim == "move":
            k = t / self.duration
            k = k * k * (3 - 2 * k)  # ease in/out
            return f"translate({p.dx * k:.2f},{p.dy * k:.2f})"
        if p.anim == "rain":
            return f"translate(0,{(t * (p.speed or 1400)) % self.h:.1f})"
        if p.anim == "drift":
            return f"translate({(t * (p.speed or 25)) % self.w:.1f},0)"
        return ""

    def _camera(self, t: float) -> str:
        k = t / self.duration
        w, h = self.w, self.h
        if self.camera == "zoom_out":
            s = 1.12 - 0.12 * k
        elif self.camera in ("pan_left", "pan_right"):
            s = 1.1
        elif self.camera == "still":
            s = 1.02 + 0.02 * k
        else:
            s = 1.0 + 0.12 * k
        tx, ty = -(s - 1) * w / 2, -(s - 1) * h / 2
        if self.camera == "pan_left":
            tx = -(s - 1) * w * (1 - k)
        elif self.camera == "pan_right":
            tx = -(s - 1) * w * k
        return f"translate({tx:.2f},{ty:.2f}) scale({s:.4f})"

    def svg_at(self, t: float) -> bytes:
        for p in self.parts:
            extra = self._transform(p, t)
            # Motion goes before the element's own transform, so it acts in the parent's coordinates.
            p.node.set("transform", f"{extra} {p.base_transform}".strip())
        self.camera_node.set("transform", self._camera(t))
        return ET.tostring(self.root, encoding="utf-8")


# -- voice envelope ----------------------------------------------------------
def voice_envelope(audio: Path | None, duration: float, fps: int, lead_in: float) -> list[float]:
    """Per-frame mouth-openness (0..1) from the narration's loudness."""
    n = max(int(round(duration * fps)), 1)
    if audio is None:
        return [0.0] * n
    rate = 8000
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    pcm = array("h")
    pcm.frombytes(raw[: len(raw) - len(raw) % 2])
    hop = rate // fps
    levels = []
    for i in range(0, len(pcm), hop):
        chunk = pcm[i:i + hop]
        levels.append(math.sqrt(sum(s * s for s in chunk) / len(chunk)) if chunk else 0.0)
    peak = max(levels) if levels else 0.0
    if peak <= 0:
        return [0.0] * n
    # normalise, gate quiet parts, and smooth a little so the mouth doesn't flicker
    norm = [min(1.0, max(0.0, (v / peak - 0.12) / 0.6)) for v in levels]
    smooth, prev = [], 0.0
    for v in norm:
        prev = prev * 0.35 + v * 0.65
        smooth.append(prev)
    pad = int(round(lead_in * fps))
    env = [0.0] * pad + smooth
    return (env + [0.0] * n)[:n]


# -- rendering ---------------------------------------------------------------
_worker: SceneAnimator | None = None


def _init_worker(args: tuple) -> None:
    global _worker
    _worker = SceneAnimator(*args)


def _render_frame(i: int) -> bytes:
    assert _worker is not None
    t = i / _worker.fps
    return cairosvg.svg2png(bytestring=_worker.svg_at(t), output_width=_worker.w, output_height=_worker.h)


def render_animated(svg: str, duration: float, camera: str, out: Path, *, fps: int = 30, width: int = 1080,
                    height: int = 1920, envelope: list[float] | None = None, vf_extra: list[str] | None = None,
                    workers: int | None = None) -> Path:
    frames = max(int(round(duration * fps)), 1)
    vf = ",".join([*(vf_extra or []), "format=yuv420p"])
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "png", "-i", "-",
         "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-an", str(out)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    args = (svg, duration, camera, envelope, fps, width, height)
    try:
        with ProcessPoolExecutor(max_workers=workers or os.cpu_count() or 2,
                                 initializer=_init_worker, initargs=(args,)) as pool:
            for png in pool.map(_render_frame, range(frames), chunksize=8):
                ff.stdin.write(png)
    finally:
        ff.stdin.close()
        err = ff.stderr.read().decode(errors="replace")
        ff.wait()
    if ff.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({ff.returncode}):\n{err[-3000:]}")
    return out
