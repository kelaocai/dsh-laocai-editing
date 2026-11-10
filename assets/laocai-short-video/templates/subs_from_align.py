"""把强制对齐结果套回字幕：每句的起止取对齐时间，并给出每个字的出现时间。

用法：python subs_from_align.py aligned.json   → 生成 subs_aligned.json，render.py 自动读取
句子切分沿用 edl.SUBS 的人工分句（文字也以它为准），只替换时间。
"""
import json
import sys
from pathlib import Path

from edl import SUBS

PUNCT = set("，。？！、 ")
LEAD = 0.05   # 字幕比声音提前 50ms 出现，观感更跟手
TAIL = 0.25   # 句末停留


def main():
    words = json.loads(Path(sys.argv[1]).read_text())["words"]
    # 展开成单字序列（英文词作为一个整体）
    units = [(w["text"], w["start"], w["end"]) for w in words]
    flat = "".join(u[0] for u in units)
    starts = []
    for u in units:
        starts += [u] * len(u[0])
    out, pos = [], 0
    for _, _, text, keys in SUBS:
        clean = "".join(c for c in text if c not in PUNCT)
        p = flat.find(clean, pos)
        if p < 0:
            raise SystemExit(f"对不上：{text}")
        span = starts[p:p + len(clean)]
        char_t, k = [], p
        for c in text:  # 标点跟随前一个字
            if c in PUNCT:
                char_t.append(char_t[-1] if char_t else span[0][1])
            else:
                char_t.append(round(starts[k][1] - LEAD, 3))
                k += 1
        out.append({"start": round(span[0][1] - LEAD, 3), "end": round(span[-1][2], 3),
                    "text": text, "keys": keys, "chars": char_t})
        pos = p + len(clean)
    # 句尾延长到下一句开始前，但不超过 TAIL，避免闪烁
    for a, b in zip(out, out[1:]):
        a["end"] = round(min(a["end"] + TAIL, b["start"]), 3)
    out[-1]["end"] = round(out[-1]["end"] + TAIL, 3)
    Path("subs_aligned.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{len(out)} 句已对齐")


if __name__ == "__main__":
    main()
