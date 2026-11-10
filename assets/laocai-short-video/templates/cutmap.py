"""剪气口：检测主播原片里的长停顿，只保留 KEEP 秒，生成新的主播底片和映射后的时间数据。

python cutmap.py → host3.mp4（画面+人声）、aligned2.json（时间已映射）、hostcuts.json（主播画面上的跳切点）、cutmap.json
"""
import os
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
ROOT = os.environ["VIDEO_PROJECT_DIR"]
SRC = f"{ROOT}/土豆巴士-第二版.mp4"
FPS = 30
MIN_PAUSE, KEEP = 0.45, 0.30  # 超过 0.45 秒的停顿压到 0.30 秒
SRC_TOTAL = 135.333


def snap(t):
    return round(t * FPS) / FPS


def silences():
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", SRC, "-vn", "-af", "silencedetect=n=-38dB:d=0.35",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    ends = [(float(e), float(d)) for e, d in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", r)]
    return [(e - d, e) for e, d in ends if d >= MIN_PAUSE]


def host_cuts():
    """原片里本来就有的跳切（录制时的拼接点）。"""
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", SRC, "-vf", "scale=192:-2,select='gt(scene,0.08)',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", r) if float(x) > 1.0]


def main():
    removed = []
    hc = host_cuts()
    for s, e in silences():
        a, b = snap(s + KEEP / 2), snap(e - KEEP / 2)
        if b - a < 2 / FPS:
            continue
        # 原片跳切离删除点很近时，把删除区间扩到跳切点，避免留下几帧的碎片（闪帧）
        for c in hc:
            if b < c <= b + 0.25 and c < e + 0.05:
                b = snap(c)
            if a - 0.25 <= c < a and c > s - 0.05:
                a = snap(c)
        removed.append((a, b))
    keep, t = [], 0.0
    for a, b in removed:
        keep.append((t, a))
        t = b
    keep.append((t, SRC_TOTAL))

    def mp(x):
        """原片时间 → 新时间。落在被删区间里的点贴到删除点。"""
        off = 0.0
        for a, b in removed:
            if x >= b:
                off += b - a
            elif x > a:
                return round(a - off, 4)
        return round(x - off, 4)

    total = round(mp(SRC_TOTAL) * FPS) / FPS
    # 新跳切 = 原片跳切 + 每个剪气口的点
    raw = sorted({round(mp(c), 3) for c in hc} | {round(mp(a), 3) for a, _ in removed})
    cuts = []
    for c in raw:  # 相距不到 0.3 秒的跳切合并成一个
        if cuts and c - cuts[-1] < 0.3:
            cuts[-1] = c
        else:
            cuts.append(c)
    words = json.loads((HERE.parent / "aligned2.json").read_text())
    for w in words["words"]:
        w["start"], w["end"] = mp(w["start"]), mp(w["end"])
    (HERE / "aligned2.json").write_text(json.dumps(words, ensure_ascii=False))
    (HERE / "hostcuts.json").write_text(json.dumps(cuts))
    (HERE / "cutmap.json").write_text(json.dumps({"removed": removed, "total": total}))

    # 画面按帧裁切拼接；人声每段两端 8 毫秒淡入淡出，防止爆音
    fc, cat = [], ""
    for i, (a, b) in enumerate(keep):
        d = b - a
        fc.append(f"[0:v]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[0:a]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.008,afade=t=out:st={max(d - 0.008, 0):.4f}:d=0.008[a{i}]")
        cat += f"[v{i}][a{i}]"
    fc.append(f"{cat}concat=n={len(keep)}:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", SRC, "-filter_complex", ";".join(fc),
                    "-map", "[v]", "-map", "[a]", "-r", str(FPS), "-c:v", "libx264", "-preset", "fast", "-crf", "12",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(HERE / "host3.mov")], check=True)
    print(f"剪掉 {len(removed)} 处停顿，共 {SRC_TOTAL - total:.2f} 秒；新时长 {total:.3f}")
    for a, b in removed:
        print(f"  原 {a:7.2f}-{b:7.2f}  删 {b - a:.2f}s  → 新 {mp(a):7.2f}")
    print("主播画面跳切点：", cuts)


if __name__ == "__main__":
    main()
