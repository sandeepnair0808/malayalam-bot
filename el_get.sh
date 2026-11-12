#!/data/data/com.termux/files/usr/bin/bash
# Download the 9 ElevenLabs narrations to Download/el/ (links expire; ask Claude for a fresh script if they fail)
mkdir -p /sdcard/Download/el && cd /sdcard/Download/el || exit 1
get() { curl -fsSL --retry 3 -o "$1.mp3" "$2" && echo "ok $1" || echo "FAILED $1"; }
get 22-gulf-slippers "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/StkInZLzz0S6ELIMtiPk/EN2DT17KF6ZygdedtXeT/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=B0jjJ2MiwNtyaW2eQhfd-xpb_YI="
get 24-failed-exam "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/0gyBKyQrrzEdFgtE2Bbp/Vuj916g9EBkasVBbrOnu/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=zvuCn9EuVXtKh9_ZnWJqS3tVIQM="
get 29-achan-hands "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/2qWWIrFnT6LIlCqQ1znn/cYJ5EasQLAcW0sZJrdox/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=7_EH9I6YaFF94RKSizgMsCgpsgQ="
get 31-needle-thread "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/XhoV6UZ1h5tWInfn76Ts/pQiqb3Oz5VMnDALtj6rF/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=cb2KNloakFrsp4n3ZPc_FDGhWd0="
get 32-evening-lamp "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/0mK7Eb6emRYmAc94XumO/3rlE9HPkLkGxcYIUIlcm/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=65wZrJYTtUFKjunU3qJSd0-0Ifw="
get 34-achan-torch "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/5Ox9xFtmpPJDKiZ6VEOf/9LXGrVXq6jSC19w1IhnX/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=Iow-SX-DvG3Ro8rwJeJqPUkX_iw="
get 39-ammachi-stories "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/X69QsDZUYrWRwOzf3UB5/ezSKPNwT6z6FT3hSja1J/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=OsoNsi1Q5xjDw_KXAWWA2QIRuWo="
get 41-lost-toy "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/V748V88nN9yA79dj6EkA/zb5pvEpELL89633kyk0k/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=f5Kzgit6FxN3_yRBiB4Z8T9izbA="
get 44-fast-watch "https://elevenlabsusercontent.com/database/workspace/2736916b0d00450c9fc8ab8a96523659/content_generation/IDFfoVhAGmk5XIoBSi0J/BHMnZvpx62XXvwsCIF0b/content.mp3?Expires=1794488400&KeyName=assets-cdn-key-1&Signature=9iiWSyI1G_DO-FNdi5zqgZNpXY0="
ls -la /sdcard/Download/el
