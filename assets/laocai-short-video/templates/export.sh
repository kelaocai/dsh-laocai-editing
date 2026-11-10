#!/usr/bin/env bash
# 合成音频并导出上传版（视频号 / 抖音通用）。用法：bash export.sh <final_noaudio.mp4> <主播原片> <输出.mp4> <总时长秒>
# 画面直接 copy，不二次编码；码率和色彩参数在 render.py 的单次编码里设置。
set -euo pipefail
V="$1"; A="$2"; OUT="$3"; T="$4"
FADE=$(python3 -c "print(round($T - 0.4, 2))")
ffmpeg -nostdin -v error -y -i "$V" -i "$A" -map 0:v -map 1:a -c:v copy \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st=$FADE:d=0.4,aresample=48000" \
  -c:a aac -b:a 256k -ar 48000 -t "$T" -movflags +faststart "$OUT"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt,color_primaries,bit_rate,sample_rate:format=duration,size -of compact "$OUT"
