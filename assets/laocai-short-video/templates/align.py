"""Qwen3-ForcedAligner 强制对齐：已知文字 + 音频 → 每个字的起止时间。

用法：python align.py <音频> <文字稿.txt> <输出.json>
文字稿必须和实际说的话一致（多说、漏说、改词都要先改进文字稿），否则对齐会漂。
"""
import json
import sys
from pathlib import Path

import torch
from qwen_asr import Qwen3ForcedAligner

MODEL = str(Path.home() / "models/Qwen3-ForcedAligner-0.6B")


def main():
    audio, text_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    text = Path(text_path).read_text(encoding="utf-8").strip()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Qwen3ForcedAligner.from_pretrained(MODEL, dtype=torch.float32, device_map=device)
    res = model.align(audio=audio, text=text, language="Chinese")
    items = res[0] if isinstance(res, list) else res
    words = [{"text": w.text, "start": round(w.start_time, 3), "end": round(w.end_time, 3)} for w in items]
    Path(out).write_text(json.dumps({"words": words}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(words)} 个单元，首 {words[0]}，尾 {words[-1]}")


if __name__ == "__main__":
    main()
