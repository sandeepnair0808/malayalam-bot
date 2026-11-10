import json
import shutil
import subprocess
from pathlib import Path

import pytest

from reelbot import history
from reelbot.config import Settings
from reelbot.illustrate import extract_svg, fallback_svg, render_png
from reelbot.instagram import InstagramClient, InstagramError
from reelbot.models import Story
from reelbot.story import THEMES, pick_theme
from reelbot.subtitles import Cue, build_ass, escape
from reelbot.video import scene_duration, zoompan_expr

HERE = Path(__file__).parent


def sample_story() -> Story:
    return Story.model_validate_json((HERE / "sample_story.json").read_text(encoding="utf-8"))


def test_caption_has_hashtags():
    cap = sample_story().instagram_caption()
    assert cap.startswith("ലഡ്ഡു")
    assert "#malayalam" in cap and "##" not in cap


def test_pick_theme_skips_used():
    used = THEMES[:-1]
    assert pick_theme(used) == THEMES[-1]


def test_extract_svg_strips_unsafe_parts():
    raw = (
        "Here you go:\n<svg width='10' height='10'><script>alert(1)</script>"
        "<image href='http://evil/x.png'/><rect width='10' height='10'/></svg> done"
    )
    svg = extract_svg(raw)
    assert svg.startswith("<svg") and "script" not in svg and "evil" not in svg
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


def test_extract_svg_rejects_garbage():
    with pytest.raises(ValueError):
        extract_svg("no svg here")


def test_ass_escaping_and_timing():
    assert escape("a{b}\nc") == "a(b)\\Nc"
    ass = build_ass([Cue(0, 61.257, "അമ്മ")], "Manjari")
    assert "0:00:00.00,0:01:01.26" in ass and "അമ്മ" in ass


def test_durations_and_camera():
    assert scene_duration(3.0, 2.5) == pytest.approx(3.9)
    assert scene_duration(0.0, 4.0) == 4.0
    assert "d=90" in zoompan_expr("pan_left", 90, 1080, 1920, 30)


def test_history_roundtrip(tmp_path):
    f = tmp_path / "h.json"
    history.append(f, {"dir": "a", "title_ml": "x"})
    history.update(f, "a", published=True)
    assert history.load(f)[0]["published"] is True


class FakeResp:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, json.dumps(data)

    def json(self):
        return self._data


class FakeSession:
    def __init__(self):
        self.calls = []
        self.statuses = ["IN_PROGRESS", "FINISHED"]

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("POST", url, headers))
        if url.endswith("/media"):
            assert data["media_type"] == "REELS" and data["upload_type"] == "resumable"
            return FakeResp({"id": "C1", "uri": "https://rupload.facebook.com/ig-api-upload/v21.0/C1"})
        if "rupload" in url:
            assert headers["Authorization"] == "OAuth T" and headers["offset"] == "0"
            return FakeResp({"success": True})
        if url.endswith("/media_publish"):
            assert data["creation_id"] == "C1"
            return FakeResp({"id": "M1"})
        raise AssertionError(url)

    def get(self, url, params=None, timeout=None):
        if url.endswith("/C1"):
            return FakeResp({"status_code": self.statuses.pop(0)})
        if url.endswith("/M1"):
            return FakeResp({"permalink": "https://www.instagram.com/reel/abc/"})
        raise AssertionError(url)


def test_instagram_publish_flow(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"0" * 1000)
    ig = InstagramClient("U", "T", session=FakeSession())
    res = ig.publish_reel(video, "caption")
    assert res.media_id == "M1" and res.permalink.endswith("/abc/")


def test_instagram_error_surfaces():
    class S(FakeSession):
        def post(self, url, data=None, headers=None, timeout=None):
            return FakeResp({"error": {"message": "bad token", "code": 190}}, 400)

    with pytest.raises(InstagramError, match="bad token"):
        InstagramClient("U", "T", session=S()).create_container("x")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_offline_render(tmp_path):
    """Full voice/video stage with placeholder art and no narration (no network needed)."""
    from reelbot.pipeline import render

    settings = Settings()
    settings.tts = "none"
    settings.animate = False
    settings.music_dir = tmp_path / "nomusic"
    story = sample_story()
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    images = [render_png(fallback_svg(), scenes / f"scene_{i:02d}.png", 1080, 1920) for i in range(len(story.scenes))]
    out = render(settings, story, tmp_path, images)
    assert out.exists() and out.stat().st_size > 10_000


RIGGED = """<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">
<rect width="1080" height="1920" fill="#cfd8c4"/>
<g data-anim="rain" data-speed="1000"><line x1="10" y1="10" x2="5" y2="60" stroke="#fff"/></g>
<g data-anim="move" data-dx="100"><g data-anim="breathe" data-pivot="540,1500">
  <g data-anim="swing" data-pivot="500,900" data-amp="10"><rect x="480" y="900" width="40" height="300"/></g>
  <g data-anim="blink" data-pivot="540,700"><circle cx="520" cy="700" r="8"/><circle cx="560" cy="700" r="8"/></g>
  <g data-anim="talk" data-pivot="540,760"><ellipse cx="540" cy="780" rx="20" ry="20"/></g>
  <g data-anim="swing"><rect width="1" height="1"/></g>
</g></g></svg>"""


def test_animator_moves_tagged_parts():
    from reelbot.animate import SceneAnimator, count_tags

    assert count_tags(RIGGED) == 7
    a = SceneAnimator(RIGGED, duration=2.0, camera="zoom_in", envelope=[0.0] * 30 + [1.0] * 30)
    assert len(a.parts) == 6  # the swing without a pivot is ignored
    first, mid = a.svg_at(0.0).decode(), a.svg_at(1.5).decode()
    assert first != mid
    assert "translate(100.00,0.00)" in a.svg_at(2.0).decode()  # move finished
    assert "scale(1,1.070)" in mid  # mouth open while the voice is loud
    # rain layer was tiled so it can scroll without a gap
    assert mid.count("<line") == 2


def test_voice_envelope_without_audio():
    from reelbot.animate import voice_envelope

    assert voice_envelope(None, 1.0, 30, 0.3) == [0.0] * 30


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_animated_clip_renders(tmp_path):
    from reelbot.animate import render_animated

    out = render_animated(RIGGED, 0.5, "pan_left", tmp_path / "c.mp4", fps=10, width=270, height=480, workers=2)
    assert out.stat().st_size > 1000


# ---------------------------------------------------------------- 3d style (fake Google client)
def _png_bytes(w=270, h=480, color=(120, 160, 120)):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeGenai:
    """Mimics the parts of google-genai the Studio uses."""

    def __init__(self, tmp_path, fail_video=False):
        self.tmp, self.fail_video = tmp_path, fail_video
        self.image_calls, self.video_calls = [], []
        self.vertexai = False
        outer = self
        src = tmp_path / "src.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24",
                        "-t", "4", "-pix_fmt", "yuv420p", str(src)], check=True)

        class Models:
            def generate_content(self, model, contents, config):
                outer.image_calls.append(contents)
                part = _NS(inline_data=_NS(data=_png_bytes()))
                return _NS(candidates=[_NS(content=_NS(parts=[part]), finish_reason="STOP")])

            def generate_videos(self, model, source, config):
                outer.video_calls.append((source, config))
                if outer.fail_video:
                    raise RuntimeError("person generation blocked")
                return _NS(done=False, error=None, result=None, n=0)

        class Operations:
            def get(self, op):
                src = outer.tmp / "src.mp4"

                class Video:
                    def save(self, path):
                        shutil.copy(src, path)

                return _NS(done=True, error=None, result=_NS(generated_videos=[_NS(video=Video())]))

        class Files:
            def download(self, file):
                return b""

        self.models, self.operations, self.files = Models(), Operations(), Files()


def _studio(tmp_path, monkeypatch, **kw):
    pytest.importorskip("google.genai")
    monkeypatch.setattr("time.sleep", lambda s: None)
    from reelbot.realistic import Studio

    settings = Settings()
    settings.style, settings.tts, settings.animate = "3d", "none", False
    settings.music_dir = tmp_path / "nomusic"
    fake = FakeGenai(tmp_path, **kw)
    return settings, fake, Studio(settings, client=fake)




@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_3d_studio_end_to_end(tmp_path, monkeypatch):
    from reelbot.pipeline import render

    settings, fake, studio = _studio(tmp_path, monkeypatch)
    story = Story.model_validate_json((HERE.parent / "examples" / "umbrella_story.json").read_text(encoding="utf-8"))
    durations = [5.0] * len(story.scenes)
    pairs = studio.produce(story, tmp_path, durations)

    assert len(fake.image_calls) == len(story.characters) + len(story.scenes)
    # the keyframe for scene 2 carries the two characters' sheets as references
    refs = [c for c in fake.image_calls[len(story.characters) + 1] if not isinstance(c, str)]
    assert len(refs) == 2
    source, config = fake.video_calls[0]
    assert config.aspect_ratio == "9:16" and config.duration_seconds == 6
    assert all(clip is not None and clip.exists() for _, clip in pairs)

    # second run is fully cached: no new API calls
    studio.produce(story, tmp_path, durations)
    assert len(fake.video_calls) == len(story.scenes)

    out = render(settings, story, tmp_path, [img for img, _ in pairs])
    assert out.exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_3d_falls_back_to_stills_when_video_fails(tmp_path, monkeypatch):
    settings, fake, studio = _studio(tmp_path, monkeypatch, fail_video=True)
    story = sample_story()
    pairs = studio.produce(story, tmp_path, [4.0] * len(story.scenes))
    assert all(img.exists() and clip is None for img, clip in pairs)


def test_veo_duration_and_fit():
    from reelbot.realistic import veo_duration
    from reelbot.video import fit_clip_filter

    assert [veo_duration(x) for x in (3.2, 4.0, 5.1, 7.9, 12)] == [4, 4, 6, 8, 8]
    assert "setpts" not in fit_clip_filter(6.0, 5.0, 1080, 1920)
    f = fit_clip_filter(8.0, 12.0, 1080, 1920)
    assert "setpts=1.3500*PTS" in f and "tpad=stop_mode=clone:stop_duration=1.200" in f
