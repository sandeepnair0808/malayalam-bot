from pathlib import Path

from reelbot.safety import lint

GOOD = """### k900-good
title: നല്ല കഥ | A Good Story
theme: test
moral: Be kind.
narrator: woman
caption: test
tags: malayalam kidsstory
- yard | zoom_in | wind | kid:happy || അപ്പു മുറ്റത്ത് കളിച്ചു. ||
- yard | still | wind | kid:talk || അപ്പു പറഞ്ഞു. || kid: നമുക്ക് കളിക്കാം.
- yard | zoom_in | wind | kid:happy || അവൻ ചിരിച്ചു. ||
- yard | still | wind | kid:happy || എല്ലാവരും വന്നു. ||
- yard | zoom_out | wind | kid:wave || ഗുണപാഠം: ദയ കാണിക്കണം. ||
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_clean_story_passes(tmp_path):
    assert lint([_write(tmp_path, "a.txt", GOOD)]) == {}


def test_catches_unsafe_and_malformed(tmp_path):
    bad = (GOOD.replace("k900-good", "k901-bad").replace("നല്ല കഥ", "മോശം കഥ").replace("Be kind.", "x")
           .replace("അവൻ ചിരിച്ചു.", "അവൻ പ്രേതത്തെ കണ്ടു.")
           .replace("|| എല്ലാവരും വന്നു. ||", "|| kid: hello ||")
           .replace("ഗുണപാഠം: ദയ കാണിക്കണം.", "അവസാനം.")
           .replace("tags: malayalam kidsstory", "tags: malayalam lottery"))
    report = lint([_write(tmp_path, "b.txt", bad)])
    probs = " ".join(report["b.txt:k901-bad"])
    assert "പ്രേത" in probs
    assert "#lottery" in probs
    assert "looks like dialogue" in probs
    assert "ഗുണപാഠം" in probs


def test_catches_duplicates_across_packs(tmp_path):
    a = _write(tmp_path, "a.txt", GOOD)
    b = _write(tmp_path, "b.txt", GOOD.replace("k900-good", "k902-copy"))
    report = lint([b], all_packs=[a, b])
    assert any("duplicate" in p for p in report["b.txt:k902-copy"])


def test_english_words_do_not_false_positive(tmp_path):
    text = GOOD.replace("A Good Story", "Father's Warm Diet Update")
    assert lint([_write(tmp_path, "c.txt", text)]) == {}
