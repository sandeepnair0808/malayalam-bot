# What works for this channel (living playbook)

Update this file every time new numbers come in. Newest evidence first.
Raw snapshots live in `stats/`.

## Evidence: analytics export 2026-11-10 23:24 IST (stats/videos_2026-11-10.csv)

- Publish times (IST): #1 15:35, #2 16:02, #3 16:36 -> 1,158 / 1,111 / 1,100 views.
  From the 4th upload (16:46, only 10 min later) EVERY Short is 0-15 views, nostalgia and kids alike,
  including strong themes (Amma's Earrings 0, The One Who Eats Last 1, STD Booth 3).
  => The drop is about **posting frequency**, not theme. The first 3 got YouTube's test audience;
  the flood after them did not. Strongest lesson so far: **space uploads out (max ~4/day)**.
- Like rate on the hits: 12-15 likes per 1,100 views (~1.2%), 1-2 comments each: low; ask a question
  in the caption/first comment to lift it.
- Detailed analytics (watch %, engaged views) lag 2-3 days; re-check these Shorts after Nov 13.
- The channel also holds old TABS-game and electrical-engineering videos (2020-21) that confuse
  the channel topic; consider making them Unlisted.

## Evidence so far (YouTube, Nov 10 2026, first 48 h, 3,725 views)

| Short | Views | Notes |
|---|---|---|
| ടിഫിനിലെ ഒരു ചപ്പാത്തി (One Extra Chapati) | 1,300 | **51.2% stayed to watch / 48.9% swiped away** |
| ഗൾഫിൽ നിന്നുള്ള കത്ത് (Letter from the Gulf) | 1,100 | |
| അമ്മൂമ്മയുടെ സാരിത്തുമ്പിലെ കിഴി (Ammachi's Knotted Coins) | 1,100 | |
| Every Short after those (nostalgia and kids) | 2-16 | posted every 15 min, many within a few hours |

Instagram (sdh081612, manual uploads): cartoon nostalgia reels 800-1,450 views each; kite (1,458),
rain umbrella (1,415), chechi/pookkalam (1,365) led. Realistic/AI-scenery posts did far worse.
Short captions with 1-2 hashtags (#keralam, #fatherlove #malayalamstatus) did best there.

## Rules for every new video

1. **Hook in the first 2 seconds.** Every story gets a `hook:` line: a short question (under 70
   characters) that the story answers, e.g. "അമ്മ എന്തിനാണ് എന്നും ഒരു ചപ്പാത്തി കൂടുതൽ വെച്ചത്?".
   It becomes the opening scene (voice + subtitle over the first picture). Half the audience swiped
   away from our best Short without one.
2. **Keep reels ~30-35 s:** at most 7 story scenes + the hook (lint enforces <= 8 total).
3. **Winning themes first:** Amma / Ammachi quiet sacrifice, the Gulf / pravasi family, tiffin,
   school, first job / leaving home, Achan's hidden love. Emotional twist at the end.
4. **Weak themes so far:** radio, kite, mango tree, pookkalam on YouTube (2-7 views); revisit only
   with a strong hook.
5. **Moral stories are published as "Not made for kids" family stories** (owner's decision, Nov 10): titles say "Malayalam Family Story", no kid-targeted tags, captions address parents. Keep them genuinely family-oriented so the label stays accurate. They are ranked last in the queue. "Made for Kids" Shorts reach very few people (9-16 views): no comments, no
   notifications. Keep them a minority in the queue (3 nostalgia : 1 kids) or move them to a
   separate channel.
6. **Do not flood.** Owner's current choice: 1 upload per hour (cron `0 * * * *`). Shorts posted minutes apart cannibalised each other. Current pace: every 30 min;
   if new Shorts stay under ~20 views after 14 days, drop to 4/day (7 am, 12 pm, 6 pm, 9 pm).
7. **Never delete flops early.** Judge after 14 days; set real losers to Private, not Delete
   (deleting removes their views and watch time from monetization totals).
8. **Variety protects monetization.** YouTube's "inauthentic content" review rejects channels that
   look mass-produced. Vary voices, settings, openings and lengths; add a human channel identity.
9. **Safety for kids content** (blocklist, morals, no scary/violent words): `reelbot lint`.
   Nostalgia: `reelbot lint --general --require-hook`.

10. **First comment on every Short** (posted by the phone uploader right after upload, rotating
    questions that invite memories, plus older uploads get one too). Pin the best one by hand in
    YouTube Studio (the API cannot pin).

## Weekly review loop

1. Owner sends YouTube Studio screenshots: Content tab sorted by views, plus "Stayed to watch vs
   swiped away" for the top Shorts.
2. Save numbers to `stats/`, update the tables above.
3. Re-rank `phone/uploads.json` (best first) and regenerate `phone/ranking.txt`.
4. Write the next pack around the winning themes, with hooks.

## Targets per Short
- Stayed to watch: > 70% (ours: 51% on the best one, so hooks are the priority)
- Average % viewed: > 80%
- Likes + comments: >= 3 per 100 views


## Story structure: hook + twist (2026-11-10)
- Every story needs a real twist: a reveal in the last scene that changes the meaning of what came before
  (a secret sacrifice, a hidden helper, a role reversal). "Back then vs today" endings are not twists.
- Plant the twist early (the leaf watch always shows 4 o'clock, the empty banana leaf at the end of the row),
  and make the hook ask the question the twist answers.
- The renderer now holds a 0.8 s beat before the last line and shows it big in gold (Reveal style);
  the hook scene is a close-up of the main character.
- Competitor (youthful_mediatech) look to match and beat: one warm lamp lighting a dark room, glossy
  big eyes, close-up reaction shots, floating dust, natural (non-pitch-shifted) voices.

## First new-style Short (2026-11-11)
- 97-amma-signs-name, the first upload with lamplight art, natural voice settings, close-up hook and gold twist
  reveal: 29 views in 6 min, 251 views in 17 min. That is the fastest start on the channel, even though it
  went out about 1 h after the previous Short.
- The previous Short (93-ammachi-train, old flat art, posted after an 8 h gap) got 333 views in 42 min.
  The old-style hourly uploads before the gap got 0-15 views.
- Early read: the new style and story structure beat the old style. Posting gaps may still matter, so keep
  comparing 1 h views per Short (stats/).

## Correction: it is the posting gap, not the style (2026-11-11 16:17 IST)
The full Shorts grid after uploads restarted at ~13:00 IST, one per hour:
27-school-day (old style, first after an 8 h gap) 790 views; 93-ammachi-train (old) 580;
97-amma-signs-name (new) 434; 19-fever-night (new) 0 at 15 min.
The hourly uploads before the gap got 3-8 views each.
- Each Short posted 1 h after the last gets less. The first one after a long rest does best, whatever its style.
- RULE: post at most 3 a day, at least 4-5 h apart (7:00, 13:00, 20:00 IST). Never hourly.
- The earlier "new style beats old style" note was wrong. Judge the style only between Shorts with the same gap.
