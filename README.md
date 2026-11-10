# reelbot: Malayalam story reels → Instagram

Turns a one-line idea into a finished, captioned, narrated **9:16 Instagram Reel** in the
style of nostalgic Kerala "kutti kaalam" animations (flat vector characters, warm palette,
Malayalam subtitles) and publishes it to your Instagram account. It can run daily on GitHub Actions.

```
idea ─► Claude writes story (Malayalam, 6–9 scenes, caption, hashtags)
     ─► Claude draws each scene as flat-vector SVG ─► PNG (cairosvg)
     ─► Malayalam voice-over per scene (edge-tts / gTTS)
     ─► character animation: every frame re-rendered from the rigged SVG (walk, blink,
        lip-sync to the voice, breathing, swinging arms, falling rain) + camera move
     ─► ffmpeg: fades + music + burned-in Malayalam subtitles (libass)
     ─► Instagram Graph API: resumable upload ─► wait for processing ─► publish
```

## Setup

```bash
# system deps
sudo apt-get install ffmpeg libcairo2 fonts-smc-manjari   # macOS: brew install ffmpeg cairo
pip install -e '.[dev]'
cp .env.example .env    # fill in keys
```

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key (story + illustrations). |
| `REELBOT_TTS` | `edge` (default, natural `ml-IN` neural voices), `gtts`, or `none` (subtitles + music only). |
| `REELBOT_VOICE` | `ml-IN-SobhanaNeural` (female) or `ml-IN-MidhunNeural` (male). |
| `REELBOT_FONT` | Malayalam font family for subtitles (default `Manjari`). Drop a `.ttf` in `assets/fonts/` to use a custom one. |
| `IG_USER_ID`, `IG_ACCESS_TOKEN` | Instagram professional account id and a long-lived token. |
| `IG_GRAPH_HOST` | `graph.facebook.com` (Facebook Login token) or `graph.instagram.com` (Instagram Login token). |

Background music: put royalty-free `.mp3`/`.m4a` files in `assets/music/`; one is picked at
random and mixed under the voice. Only use tracks you have the rights to.

## Usage

```bash
reelbot make                                  # pick an unused theme, produce output/<date>-<slug>/
reelbot make --theme "grandfather teaching me to swim in the temple pond"
reelbot make --story examples/umbrella_story.json  # skip story writing, draw + render this story
reelbot rebuild output/<dir>                  # re-render voice/video only (no Claude calls)
reelbot publish output/<dir>                  # upload reel.mp4 with caption.txt
reelbot run                                   # make + publish
```

Each reel directory holds `story.json`, `caption.txt`, `scenes/scene_NN.{svg,png}`, and
`reel.mp4`. You can edit `story.json` or the SVGs, then `rebuild` before publishing.

## Character animation

Claude draws every scene as a *rigged* SVG: arms, legs, heads, eyes, mouths, rain and so on
are separate groups tagged with `data-anim` (`swing`, `blink`, `talk`, `breathe`, `bob`, `move`,
`rain`, `drift`, `float`) and a joint `data-pivot`. `reelbot/animate.py` moves those parts
frame by frame (30 fps), adds the camera move, renders the frames with cairosvg in parallel and
pipes them into ffmpeg. The speaking character's mouth opens with the loudness of the voice-over.
The full tag reference is in the module docstring.

A 45 s reel takes about 2 minutes to render on 4 cores. Set `REELBOT_ANIMATE=0` to fall back to
still images with a camera move.

## Instagram access

1. Switch the Instagram account to **Professional** (Creator or Business).
2. Create a Meta app at developers.facebook.com and add **Instagram** (either *API setup with
   Instagram login* or *with Facebook login*, where the IG account must be linked to a Facebook Page).
3. Grant `instagram_business_basic` + `instagram_business_content_publish` (Instagram login) or
   `instagram_basic` + `instagram_content_publish` + `pages_show_list` (Facebook login).
4. Generate a **long-lived token** (60 days; refresh it before it expires) and get the IG user id
   (`GET /me?fields=user_id` on graph.instagram.com, or `GET /{page-id}?fields=instagram_business_account`).

Publishing uses the resumable upload (`upload_type=resumable` → `rupload.facebook.com`), so the
video doesn't need to be publicly hosted. The API allows up to 50 published posts per 24 hours.

## Daily automation (GitHub Actions)

`.github/workflows/daily-reel.yml` runs every day at 18:37 IST and on manual dispatch:

1. Add repository **secrets** `ANTHROPIC_API_KEY`, `IG_USER_ID`, and `IG_ACCESS_TOKEN`.
2. Each run uploads the reel as a build artifact so you can review it.
3. Scheduled runs **publish only when the repo variable `AUTO_PUBLISH` is `true`**. Until then they
   only produce artifacts. Manual runs have a "Publish" checkbox.
4. `data/history.json` is committed after each run, so future stories avoid repeating themes.

## Cost & quality notes

- One story call plus one call per scene (6–9) on `claude-opus-5-5`. The style guide, character
  sheet and frame-1 reference are prompt-cached across the scene calls, which keeps characters
  consistent and cuts input cost. Change the model with `REELBOT_MODEL`, and effort with
  `REELBOT_STORY_EFFORT` / `REELBOT_ART_EFFORT`.
- Server-side refusal fallback is enabled (`fallbacks: "default"`).
- A scene whose SVG fails to render twice falls back to a plain backdrop, so the reel still
  renders. Check `scenes/` before publishing if you post without reviewing.

## Tests

```bash
pytest -q     # offline: no API calls; includes a full ffmpeg render with placeholder art
```
