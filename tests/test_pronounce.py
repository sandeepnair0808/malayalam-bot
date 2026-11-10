from reelbot.pronounce import for_speech, number_ml
from reelbot.storypack import parse
from reelbot.subtitles import Cue, build_ass


def test_numbers():
    assert number_ml(25) == "ഇരുപത്തിയഞ്ച്"
    assert number_ml(2026) == "രണ്ടായിരത്തി ഇരുപത്തിയാറ്"
    assert number_ml(100) == "നൂറ്"


def test_speech_cleanup():
    assert for_speech("എസ്.ടി.ഡി ബൂത്ത് 📞") == "എസ് ടി ഡി ബൂത്ത്."
    assert for_speech('"അമ്മേ, 50 രൂപ!" - അവൻ') == "അമ്മേ, അൻപത് രൂപ! അവൻ."
    assert "," in for_speech("രാത്രി... ഉറക്കം")


def test_hook_becomes_first_scene_and_top_text():
    text = """### x
hook: ഇത് എന്ത്?
title: a | A
- yard | still | wind | kid:happy || ഒന്ന്. ||
"""
    story = parse(text)[0][1]
    assert story.scenes[0].narration_ml == "ഇത് എന്ത്?" and story.scenes[0].emphasis
    assert len(story.scenes) == 2
    ass = build_ass([Cue(0, 2, "ഇത് എന്ത്?", "Hook")], "Manjari")
    assert "Style: Hook" in ass and ",Hook,," in ass
