#!/usr/bin/env bash
# 本地预判音频有无人声。首次运行自动建虚拟环境（阿里云 pip 镜像，不走代理）。
# 用法：voice_check.sh <音频目录或文件...>
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
VENV="$S/.venv"
NOPROXY=(env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy)
if [ ! -x "$VENV/bin/python" ]; then
  "${NOPROXY[@]}" python3 -m venv "$VENV"
  "${NOPROXY[@]}" "$VENV/bin/pip" install -q -i https://mirrors.aliyun.com/pypi/simple/ --proxy "" faster-whisper
fi
"${NOPROXY[@]}" HF_HUB_OFFLINE=1 "$VENV/bin/python" -I "$S/voice_check.py" "$@" 2>&1 | grep -v Warning
