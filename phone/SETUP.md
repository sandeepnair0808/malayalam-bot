# Auto-upload to YouTube from your Android phone

Your phone tries to upload one video every 15 minutes, on its own.
It is free, needs no card and no laptop. One-time setup takes about 30 minutes.

> Two things to know first
> 1. **Videos stay "Private" until Google approves your app.** Fill in the free audit form (step 8).
>    Until then, open YouTube Studio and switch each new video to Public (one tap).
> 2. Keep the phone **charged and on Wi-Fi/mobile data**. It uploads in the background.

---

## Step 1: Install Termux (Linux on your phone)
1. Install **F-Droid** from https://f-droid.org (the Play Store version of Termux is outdated).
2. In F-Droid, install **Termux** and **Termux:Boot**.
3. Open Termux and copy-paste these lines (one at a time, press Enter after each):

```
pkg update -y && pkg upgrade -y
pkg install -y python git unzip cronie termux-services
pip install google-api-python-client google-auth-oauthlib
termux-setup-storage
```
(Tap **Allow** when it asks for storage permission.)

## Step 2: Get the uploader and the videos
```
cd ~
git clone https://github.com/sandeepnair0808/malayalam-bot.git -b ccr-86fad844-hhsetp
curl -L -o reels.zip https://github.com/sandeepnair0808/malayalam-bot/archive/refs/heads/reels.zip
unzip -q reels.zip
ln -s ~/malayalam-bot-reels ~/malayalam-bot/phone/videos
```
(The videos are about 1 GB; use Wi-Fi.)

## Step 3: Create your free Google API key (in Chrome on the phone)
1. Open https://console.cloud.google.com and sign in with **the Google account that owns your YouTube channel**.
2. Top bar → **Select a project** → **New project** → name it `reel-uploader` → **Create**.
3. Search bar → **YouTube Data API v3** → **Enable**.
4. Menu → **APIs & Services → OAuth consent screen** (may be called "Google Auth Platform")
   - User type: **External** → app name `reel-uploader` → your email → **Save**.
   - **Audience / Test users** → add your own Gmail.
   - **Publish app** → **In production** (this stops the login from expiring every 7 days; ignore the "verification" notice).
5. **Credentials → Create credentials → OAuth client ID → Application type: Desktop app** → **Create** → **Download JSON**.

## Step 4: Put the key next to the uploader
```
cp /sdcard/Download/client_secret*.json ~/malayalam-bot/phone/client_secret.json
```

## Step 5: Sign in once
```
cd ~/malayalam-bot/phone
python phone_uploader.py --auth
```
- It prints a long link. Long-press → **Copy**, open it in Chrome.
- Choose your channel's Google account → "Google hasn't verified this app" → **Advanced** → **Go to reel-uploader** → **Allow**.
- Chrome shows "The authentication flow has completed". Go back to Termux: it says **Signed in**.

## Step 6: Test one upload
```
python phone_uploader.py
python phone_uploader.py --status
```
You should see `OK 07-radio-seven.mp4 -> https://youtube.com/shorts/...`.

## Step 7: Make it automatic (every 15 minutes)
```
sv-enable crond
(crontab -l 2>/dev/null; echo '*/15 * * * * cd ~/malayalam-bot/phone && python phone_uploader.py >> cron.log 2>&1') | crontab -
mkdir -p ~/.termux/boot && printf '#!/data/data/com.termux/files/usr/bin/sh\ntermux-wake-lock\nsv-enable crond\n' > ~/.termux/boot/start && chmod +x ~/.termux/boot/start
termux-wake-lock
```
Then in Android **Settings → Apps → Termux → Battery → Unrestricted** (and the same for Termux:Boot).
Open Termux:Boot once so it starts Termux after a phone restart.

> **YouTube's free API limit is about 6 uploads per day** (10,000 quota units, 1,600 per upload).
> After the 6th upload the script sees `quotaExceeded`, waits, and continues automatically the next day,
> so nothing breaks. To really get 96 a day, ask for more quota in the same audit form (step 8):
> request **160,000 units/day** for "about 96 uploads/day to my own channel".

## Step 8: Ask Google to allow public uploads (free, one time)
Fill in the **YouTube API Services audit form**: https://support.google.com/youtube/contact/yt_api_form
- Purpose: "Uploading my own Malayalam story videos to my own channel from a personal script."
- In the same form, request a **quota increase to 160,000 units/day** (for one upload every 15 minutes).
- After approval, uploads go public automatically and the 15-minute schedule runs at full speed.

---

### Everyday commands
| What | Command |
|---|---|
| How many are left | `python phone_uploader.py --status` |
| Upload one now | `python phone_uploader.py` |
| See the log | `cat uploader.log` |
| Get newly made videos | `cd ~/malayalam-bot && git pull` and download the zip again |

## Upload spacing (built in)
The uploader waits at least 4 hours after the last upload and only posts between 7:00 and 21:59
(see docs/LEARNINGS.md: a Short posted 1 h after the previous one gets ~0 views). It is safe to keep cron hourly.
- Post right now anyway: `python phone_uploader.py --now`
- Change the gap or hours: `MIN_GAP_HOURS=5 UPLOAD_HOURS=8-21 python phone_uploader.py`
