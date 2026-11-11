#!/data/data/com.termux/files/usr/bin/bash
# Download the 9 ElevenLabs narrations to Download/el/ (links expire; ask Claude for a fresh script if they fail)
mkdir -p /sdcard/Download/el && cd /sdcard/Download/el || exit 1
get() { curl -fsSL --retry 3 -o "$1.mp3" "$2" && echo "ok $1" || echo "FAILED $1"; }
get 22-gulf-slippers "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/StkInZLzz0S6ELIMtiPk/EN2DT17KF6ZygdedtXeT/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=0WyN3YRNceXTtMNZ4I2DjTv8aWc="
get 24-failed-exam "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/0gyBKyQrrzEdFgtE2Bbp/Vuj916g9EBkasVBbrOnu/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=bzzyJtDgc86tj6qEbcKGFkVXTlA="
get 29-achan-hands "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/2qWWIrFnT6LIlCqQ1znn/cYJ5EasQLAcW0sZJrdox/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=6tAASyXwG6IV2BwSroiMK3bOG9Y="
get 31-needle-thread "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/XhoV6UZ1h5tWInfn76Ts/pQiqb3Oz5VMnDALtj6rF/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=ZJIfC_G-bjjedsmGgeEjuuBYN-c="
get 32-evening-lamp "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/0mK7Eb6emRYmAc94XumO/3rlE9HPkLkGxcYIUIlcm/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=7ClU75nBe0qSZ5wERhbZL125Uzo="
get 34-achan-torch "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/5Ox9xFtmpPJDKiZ6VEOf/9LXGrVXq6jSC19w1IhnX/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=XJ-SoKSjU2FcYC5OsuT8qOoSZXw="
get 39-ammachi-stories "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/X69QsDZUYrWRwOzf3UB5/ezSKPNwT6z6FT3hSja1J/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=bSdtBpK07Jb-5PeXxnvy2YG8GoM="
get 41-lost-toy "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/V748V88nN9yA79dj6EkA/zb5pvEpELL89633kyk0k/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=buRm0qqLhIjEWc8FmKsXW1yh9RQ="
get 44-fast-watch "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/IDFfoVhAGmk5XIoBSi0J/BHMnZvpx62XXvwsCIF0b/content.mp3?Expires=1794434400&KeyName=assets-cdn-key-1&Signature=7flV1kYV23byebCX69f3EkjnkaY="
ls -la /sdcard/Download/el
