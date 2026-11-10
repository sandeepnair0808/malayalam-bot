"""Make Malayalam text speak naturally with the neural TTS voices.

Subtitles keep the original text; only the spoken copy is normalised:
  * emoji / symbols removed, quotes dropped, dashes and "..." turned into short pauses
  * dotted abbreviations spelled out:  എസ്.ടി.ഡി -> എസ് ടി ഡി,  എസ്.എസ്.എൽ.സി -> എസ് എസ് എൽ സി
  * numbers read as Malayalam words:   25 -> ഇരുപത്തിയഞ്ച്,  1990 -> ആയിരത്തി തൊള്ളായിരത്തി തൊണ്ണൂറ്
  * a small fix-up dictionary (PRONUNCIATIONS) for words the voices get wrong; extend it whenever
    a viewer or the owner reports a mispronounced word
"""

from __future__ import annotations

import re

# word as written -> how to say it (spelled the way the voice pronounces it correctly)
PRONUNCIATIONS: dict[str, str] = {
    "ടിവി": "ടി വി",
    "ഓകെ": "ഓക്കേ",
    "സോറി": "സോറി",
}

ONES = ["പൂജ്യം", "ഒന്ന്", "രണ്ട്", "മൂന്ന്", "നാല്", "അഞ്ച്", "ആറ്", "ഏഴ്", "എട്ട്", "ഒൻപത്", "പത്ത്",
        "പതിനൊന്ന്", "പന്ത്രണ്ട്", "പതിമൂന്ന്", "പതിനാല്", "പതിനഞ്ച്", "പതിനാറ്", "പതിനേഴ്", "പതിനെട്ട്",
        "പത്തൊൻപത്"]
TENS = {2: "ഇരുപത്", 3: "മുപ്പത്", 4: "നാൽപ്പത്", 5: "അൻപത്", 6: "അറുപത്", 7: "എഴുപത്", 8: "എൺപത്",
        9: "തൊണ്ണൂറ്"}
TENS_JOIN = {2: "ഇരുപത്തി", 3: "മുപ്പത്തി", 4: "നാൽപ്പത്തി", 5: "അൻപത്തി", 6: "അറുപത്തി", 7: "എഴുപത്തി",
             8: "എൺപത്തി", 9: "തൊണ്ണൂറ്റി"}
HUNDREDS = {1: "നൂറ്", 2: "ഇരുനൂറ്", 3: "മുന്നൂറ്", 4: "നാനൂറ്", 5: "അഞ്ഞൂറ്", 6: "അറുനൂറ്", 7: "എഴുനൂറ്",
            8: "എണ്ണൂറ്", 9: "തൊള്ളായിരം"}
HUNDREDS_JOIN = {1: "നൂറ്റി", 2: "ഇരുനൂറ്റി", 3: "മുന്നൂറ്റി", 4: "നാനൂറ്റി", 5: "അഞ്ഞൂറ്റി", 6: "അറുനൂറ്റി",
                 7: "എഴുനൂറ്റി", 8: "എണ്ണൂറ്റി", 9: "തൊള്ളായിരത്തി"}


THOUSANDS = {1: "ആയിരം", 2: "രണ്ടായിരം", 3: "മൂവായിരം", 4: "നാലായിരം", 5: "അയ്യായിരം", 6: "ആറായിരം",
             7: "ഏഴായിരം", 8: "എണ്ണായിരം", 9: "ഒൻപതിനായിരം", 10: "പതിനായിരം"}


def number_ml(n: int) -> str:
    """Malayalam words for 0..99999 (falls back to digits beyond that)."""
    if n < 20:
        return ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return TENS[t] if o == 0 else TENS_JOIN[t] + ONES[o].replace("ഒന്ന്", "യൊന്ന്").replace("അഞ്ച്", "യഞ്ച്") \
            .replace("ആറ്", "യാറ്").replace("ഏഴ്", "യേഴ്").replace("എട്ട്", "യെട്ട്").replace("ഒൻപത്", "യൊൻപത്")
    if n < 1000:
        h, r = divmod(n, 100)
        return HUNDREDS[h] if r == 0 else HUNDREDS_JOIN[h] + " " + number_ml(r)
    if n < 100000:
        th, r = divmod(n, 1000)
        if th in THOUSANDS:
            head = THOUSANDS[th] if r == 0 else THOUSANDS[th][:-1] + "ത്തി"
        else:
            head = number_ml(th) + (" ആയിരം" if r == 0 else " ആയിരത്തി")
        return head if r == 0 else head + " " + number_ml(r)
    return str(n)


_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍⬀-⯿]")
_ABBR = re.compile(r"((?:[ഀ-ൿ]{1,4}\.){1,6}[ഀ-ൿ]{1,4})(?=[\s,!?]|$)")


def _spell_abbr(m: re.Match) -> str:
    parts = m.group(1).split(".")
    # only treat as an abbreviation when every piece is short (a letter name like എസ്, ടി, ഡി)
    if len(parts) >= 2 and all(len(p) <= 3 for p in parts):
        return " ".join(parts)
    return m.group(1)


def for_speech(text: str) -> str:
    t = _EMOJI.sub("", text)
    t = t.replace("\"", "").replace("“", "").replace("”", "").replace("‘", "").replace("’", "")
    t = _ABBR.sub(_spell_abbr, t)
    t = re.sub(r"\d+", lambda m: number_ml(int(m.group())), t)
    t = re.sub(r"\s*(\.\.\.|…)\s*", ", ", t)          # long dots -> short pause
    t = re.sub(r"\s+[-–—]\s+", ", ", t)               # spaced dashes -> pause
    for word, say in PRONUNCIATIONS.items():
        t = re.sub(rf"(?<![ഀ-ൿ]){re.escape(word)}(?![ഀ-ൿ])", say, t)
    t = re.sub(r"([!?.])\s*,", r"\1", t)             # "!," -> "!"
    t = re.sub(r"\s{2,}", " ", t).strip(" ,")
    if t and t[-1] not in ".!?":
        t += "."                                      # a final stop gives the sentence a natural fall
    return t
