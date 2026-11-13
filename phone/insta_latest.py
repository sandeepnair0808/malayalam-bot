"""Get the Short you just posted on YouTube ready for Instagram (manual posting).

    cd ~/malayalam-bot/phone && python insta_latest.py        # the latest YouTube upload
    python insta_latest.py 2                                  # the one before that, etc.
    python insta_latest.py 45-postman-tea                     # any story by name (even before YouTube)

Copies the video to Download/insta/ (pick it in the Instagram app) and puts an Instagram caption
on the clipboard (Termux:API) and on screen. Long-press the caption box in Instagram -> Paste.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("/sdcard/Download/insta")
TAGS = "#malayalam #malayalamreels #kerala #nostalgia #malayalamstory #reels #reelsinstagram #keralagram #mallu #ormakal"


def caption(item: dict) -> str:
    title = re.sub(r"\s*#shorts\b", "", item["title"]).split(" | ")[0].strip()
    desc = item.get("description", "")
    story = desc.split("\n\n")[0].strip()  # the Malayalam hook line
    tags = " ".join(t for t in re.findall(r"#\w+", desc) if t.lower() not in ("#shorts", "#malayalamshorts"))
    extra = " ".join(t for t in TAGS.split() if t.lower() not in tags.lower())
    return (f"{title}\n\n{story}\n\nനിങ്ങളുടെ ഓർമ്മ കമന്റ് ചെയ്യൂ 👇\n"
            f"ഇതുപോലുള്ള കഥകൾക്ക് ഫോളോ ചെയ്യൂ ❤️\n\n{tags} {extra}").strip()


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else "1"
    queue = json.loads((HERE / "uploads.json").read_text(encoding="utf-8"))
    if arg.isdigit():
        done_file = HERE / "uploaded.json"
        done = json.loads(done_file.read_text(encoding="utf-8")) if done_file.exists() else {}
        posted = sorted((v.get("at", ""), f) for f, v in done.items() if v.get("status") == "uploaded")
        if len(posted) < int(arg):
            print("no uploaded Shorts found")
            return 1
        file = posted[-int(arg)][1]
        item = next((i for i in queue if i["file"] == file), {"title": done[file]["title"]})
    else:
        item = next((i for i in queue if Path(i["file"]).stem == arg), None)
        if not item:
            print(f"no story called {arg} in uploads.json")
            return 1
        file = item["file"]
    src = HERE / "videos" / file
    if not src.exists():
        print(f"video not on the phone: {src}  (run: bash ~/get_updates.sh)")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / Path(file).name
    shutil.copy2(src, dest)
    text = caption(item)
    try:
        subprocess.run(["termux-clipboard-set"], input=text.encode(), check=True, timeout=10)
        clip = "Caption copied to the clipboard."
    except (OSError, subprocess.SubprocessError):
        clip = "Copy the caption below (long-press the text)."
    print(f"Video ready: Download/insta/{dest.name}\n{clip}\n\n{text}\n")
    print("Instagram: + -> Reel -> pick the video -> Next -> paste caption -> Share.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
