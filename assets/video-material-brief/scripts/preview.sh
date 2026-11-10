#!/usr/bin/env bash
# 为素材目录里的视频各生成一张 3x2 缩略拼图（6 帧，宽 600 像素），省 Token 预览用。
# 用法：preview.sh <素材目录> [最小体积MB，默认 0]
set -euo pipefail
dir="$1"; min="${2:-0}"
out="$dir/_preview"; mkdir -p "$out"
i=0
find "$dir" -path "$dir/_*" -prune -o \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.m4v' \) -size +"${min}"M -print |
while IFS= read -r f; do
  i=$((i + 1))
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  ffmpeg -nostdin -v error -y -i "$f" -vf "fps=6/$d,scale=200:-2,tile=3x2" -frames:v 1 -q:v 6 "$out/$i.jpg"
  echo "$i|${f#$dir/}|${d%.*}s"
done
