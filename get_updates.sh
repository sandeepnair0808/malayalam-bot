#!/data/data/com.termux/files/usr/bin/bash
# Download only the re-rendered videos listed in updated.txt (small files, retries, never leaves half files).
cd ~/malayalam-bot-reels || exit 1
BASE=https://raw.githubusercontent.com/sandeepnair0808/malayalam-bot/reels
curl -fsSL --retry 5 -o updated.txt "$BASE/updated.txt" || { echo "could not get the list"; exit 1; }
n=0; fail=0; total=$(wc -l < updated.txt)
while read -r f; do
  [ -z "$f" ] && continue
  n=$((n+1)); mkdir -p "$(dirname "$f")"
  if curl -fsSL --retry 5 --retry-all-errors -o "$f.part" "$BASE/$f"; then mv -f "$f.part" "$f"; echo "[$n/$total] ok $f"
  else rm -f "$f.part"; fail=$((fail+1)); echo "[$n/$total] FAILED $f (run again later)"; fi
done < updated.txt
echo "done: $((n-fail)) updated, $fail failed"
