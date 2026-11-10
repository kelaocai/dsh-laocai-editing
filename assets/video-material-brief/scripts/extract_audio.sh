#!/usr/bin/env bash
# 提取视频音轨为 16kHz 单声道 48kbps mp3，输出到 <素材目录>/_audio/。
# 用法：extract_audio.sh <素材目录> [最小体积MB，默认 5]
set -euo pipefail
dir="$1"; min="${2:-5}"
out="$dir/_audio"; mkdir -p "$out"
n=0
find "$dir" -path "$dir/_*" -prune -o \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.m4v' \) -size +"${min}"M -print | sort |
while IFS= read -r f; do
  n=$((n + 1))
  name=$(basename "${f%.*}" | tr ' ' '_')
  o=$(printf "%s/%02d_%s.mp3" "$out" "$n" "$name")
  # 无音轨的视频会失败，跳过即可
  if ffmpeg -nostdin -v error -y -i "$f" -vn -ac 1 -ar 16000 -b:a 48k "$o" 2>/dev/null; then
    echo "$(basename "$o") <- ${f#$dir/}"
  else
    echo "跳过（无音轨）: ${f#$dir/}"
  fi
done
