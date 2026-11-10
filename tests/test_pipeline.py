import json
import shutil
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
    settings.music_dir = tmp_path / "nomusic"
    story = sample_story()
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    images = [render_png(fallback_svg(), scenes / f"scene_{i:02d}.png", 1080, 1920) for i in range(len(story.scenes))]
    out = render(settings, story, tmp_path, images)
    assert out.exists() and out.stat().st_size > 10_000
