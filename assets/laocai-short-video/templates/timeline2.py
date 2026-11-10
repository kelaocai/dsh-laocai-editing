"""第二版时间轴：把字幕和镜头锚点对到强制对齐结果上。

python timeline2.py   → 生成 subs_aligned2.json，并打印每个镜头的起止时间供检查
"""
import json
from pathlib import Path

from edl2 import EDL2, FPS, SUBS2, TOTAL

HERE = Path(__file__).parent
STRIP = set("，、？。！ ")
LEAD, TAIL = 0.05, 0.25


def load_units():
    words = json.loads((HERE / "aligned2.json").read_text())["words"]
    flat, times = "", []
    for w in words:
        for _ in w["text"]:
            times.append((w["start"], w["end"]))
        flat += w["text"]
    return flat, times


FLAT, TIMES = load_units()


def find(phrase, pos):
    p = FLAT.find(phrase, pos)
    if p < 0:
        raise SystemExit(f"对齐文本里找不到：{phrase}（从第 {pos} 字起）")
    return p


def build_subs():
    out, pos = [], 0
    for text, spoken, keys in SUBS2:
        sp = "".join(c for c in (spoken or text) if c not in STRIP)
        p = find(sp, pos)
        span = TIMES[p:p + len(sp)]
        disp = [c for c in text]
        n_vis = sum(1 for c in disp if c not in STRIP)
        chars, k = [], 0
        for c in disp:
            if c in STRIP:
                chars.append(chars[-1] if chars else span[0][0] - LEAD)
                continue
            # 显示字和读法字数不同（数字、口误修正）时按比例映射
            j = min(len(span) - 1, int(k * len(span) / max(n_vis, 1)))
            chars.append(round(span[j][0] - LEAD, 3))
            k += 1
        out.append({"start": round(span[0][0] - LEAD, 3), "end": round(span[-1][1], 3),
                    "text": text, "keys": keys, "chars": chars})
        pos = p + len(sp)
    for a, b in zip(out, out[1:]):
        a["end"] = round(min(a["end"] + TAIL, b["start"]), 3)
    out[-1]["end"] = round(min(out[-1]["end"] + TAIL, TOTAL), 3)
    return out


def segments():
    """EDL2 → [(开始帧, 结束帧, 类型, 素材, 入点, 角标, 叠加)]，第一个镜头从 0 开始。"""
    starts, pos = [], 0
    for anchor, *_ in EDL2:
        p = find(anchor, pos)
        starts.append(0.0 if not starts else TIMES[p][0])
        pos = p + len(anchor)
    segs = []
    for i, (anchor, kind, src, src_t, tag, ovl) in enumerate(EDL2):
        f0 = int(round(starts[i] * FPS))
        f1 = int(round(starts[i + 1] * FPS)) if i + 1 < len(EDL2) else int(round(TOTAL * FPS))
        segs.append((f0, f1, kind, src, src_t, tag, ovl))
    return segs


if __name__ == "__main__":
    subs = build_subs()
    (HERE / "subs_aligned2.json").write_text(json.dumps(subs, ensure_ascii=False, indent=1))
    print(f"字幕 {len(subs)} 句")
    for f0, f1, kind, src, _, tag, ovl in segments():
        name = Path(ovl[0]).stem if ovl else ""
        print(f"{f0 / FPS:7.2f}-{f1 / FPS:7.2f} {(f1 - f0) / FPS:5.2f}s {kind:<2} {str(src):<34} {tag or ''} {name}")
