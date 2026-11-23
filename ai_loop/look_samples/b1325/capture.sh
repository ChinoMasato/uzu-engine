#!/bin/bash
# B-1325 captures: stills for the four new art screens + the reel.
# Usage: capture.sh stills|reel
set -u
BIN=~/workspace/godot-b1325/bin/godot.linuxbsd.editor.x86_64
PROJ=~/workspace/godot-b1325/ai_loop/look_samples/b1315/project
OUT=~/workspace/godot-b1325/ai_loop/look_samples/b1325
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
mkdir -p "$OUT" ~/workspace/b1325cap

cap() { # name screen focus frames
  local name=$1 screen=$2 focus=$3 frames=$4
  rm -rf ~/workspace/b1325cap/$name; mkdir -p ~/workspace/b1325cap/$name
  local envs=(UZU_B1315_WORLD=persona UZU_B1315_SCREEN=$screen)
  [ "$focus" = "1" ] && envs+=(UZU_B1315_FOCUS=1)
  env "${envs[@]}" xvfb-run -a -s "-screen 0 1152x648x24" "$BIN" --path "$PROJ" \
    --rendering-driver vulkan --write-movie ~/workspace/b1325cap/$name/frame.png \
    --fixed-fps 30 --quit-after "$frames" > ~/workspace/b1325cap/$name.log 2>&1
  local last
  last=$(ls ~/workspace/b1325cap/$name/frame*.png | tail -1)
  cp "$last" "$OUT/$name.png"
  echo "$name <- $last"
}

if [ "${1:-}" = "stills" ]; then
  cap menu_art artmenu 1 150
  cap settings_art artsettings 1 150
  cap talk_art arttalk 0 150
  cap hud_art arthud 0 150
elif [ "${1:-}" = "reel" ]; then
  rm -rf ~/workspace/b1325cap/reel; mkdir -p ~/workspace/b1325cap/reel
  env UZU_B1315_WORLD=persona UZU_B1315_SCREEN=arttitle UZU_B1315_FLOW=1 \
    xvfb-run -a -s "-screen 0 1152x648x24" "$BIN" --path "$PROJ" \
    --rendering-driver vulkan --write-movie ~/workspace/b1325cap/reel/frame.png \
    --fixed-fps 30 --quit-after 840 > ~/workspace/b1325cap/reel.log 2>&1
  ls ~/workspace/b1325cap/reel/frame*.png | wc -l
  ffmpeg -y -loglevel error -framerate 30 -i ~/workspace/b1325cap/reel/frame%08d.png \
    -c:v libx264 -pix_fmt yuv420p -crf 20 "$OUT/motion_art.mp4"
  ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/motion_art.mp4"
fi
