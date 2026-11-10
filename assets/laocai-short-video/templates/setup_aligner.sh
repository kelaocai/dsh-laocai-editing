#!/usr/bin/env bash
# 一次性安装 Qwen3-ForcedAligner 环境（国内源，不走代理）。用法：bash setup_aligner.sh <venv目录>
set -euo pipefail
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
V="$1"; M="$HOME/models/Qwen3-ForcedAligner-0.6B"; PIP="-i https://mirrors.aliyun.com/pypi/simple/ --proxy="
/opt/homebrew/bin/python3.12 -m venv "$V"
"$V/bin/pip" install -q $PIP --upgrade pip numpy
"$V/bin/pip" install -q $PIP torch torchaudio "transformers==4.57.6" "accelerate==1.12.0" librosa soundfile qwen-omni-utils pytz
# qwen-asr 的 nagisa（日语分词）在 3.12 上编译失败，中文用不到：免依赖安装 + 空壳模块
"$V/bin/pip" download -q --no-deps -d /tmp/qwh $PIP qwen-asr==0.0.6
"$V/bin/pip" install -q --no-deps /tmp/qwh/qwen_asr-0.0.6-py3-none-any.whl
SP=$("$V/bin/python" -c "import site; print(site.getsitepackages()[0])")
printf 'def tagging(*a, **k):\n    raise RuntimeError("nagisa stub")\n' > "$SP/nagisa.py"
mkdir -p "$SP/soynlp/tokenizer" && : > "$SP/soynlp/__init__.py"
printf 'class LTokenizer:\n    def __init__(self, *a, **k):\n        raise RuntimeError("soynlp stub")\n' > "$SP/soynlp/tokenizer/__init__.py"
# 模型 1.8GB，ModelScope 直连，支持断点续传
mkdir -p "$M"
for f in config.json configuration.json generation_config.json chat_template.json preprocessor_config.json tokenizer_config.json merges.txt vocab.json model.safetensors; do
  [ -s "$M/$f" ] && [ "$f" != model.safetensors ] && continue
  curl -sSL --noproxy "*" -C - -o "$M/$f" "https://www.modelscope.cn/models/Qwen/Qwen3-ForcedAligner-0.6B/resolve/master/$f"
done
ls -la "$M/model.safetensors"   # 应为 1835544544 字节
"$V/bin/python" -c "from qwen_asr import Qwen3ForcedAligner; print('aligner ok')"
