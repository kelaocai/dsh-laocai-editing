#!/usr/bin/env bash
# 按镜号抽取镜头素材截图模板。用法：bash shots.sh <素材根目录> <输出目录>
# 照抄改 shot 后面的三列即可：编号 源文件相对路径 时间秒
set -euo pipefail
root="$1"; out="$2"; mkdir -p "$out"
# format=yuvj420p 不能省：部分手机素材色彩范围特殊，不加会抽帧失败
VF="scale=1280:-2,format=yuvj420p"
shot() {
  ffmpeg -nostdin -v error -y -ss "$3" -i "$root/$2" -frames:v 1 -vf "$VF" -q:v 3 "$out/$1.jpg"
  printf '%s\n' "$1.jpg"
}

# 示例（换成实际项目的内容）
shot 01_jing1-1_AP页面标题   "美联社报道.mov" 2
shot 02_jing1-2_采访发言人   "美联社报道.mov" 64
shot 03_jing1-3_展台全景     "法国巴黎展会现场/示例.mp4" 5

# 抽完拼成校验图自己看一遍，确认画面和镜号对得上
# cd "$out" && for f in [0-9]*.jpg; do ffmpeg -nostdin -v error -y -i "$f" \
#   -vf "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2:color=black,format=yuvj420p" \
#   -q:v 5 "_v_$f"; done && ffmpeg -nostdin -v error -y -pattern_type glob -i '_v_*.jpg' \
#   -vf "tile=6x3" -frames:v 1 -q:v 5 _sheet.jpg
