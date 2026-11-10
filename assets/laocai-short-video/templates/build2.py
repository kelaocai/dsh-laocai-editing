"""第二版底片：按 timeline2 的镜头表逐段生成（含叠加动画），再拼接为 base2.mp4（无音频）。"""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from edl2 import ANIM, AP_CROP, FPS, H, HLG, HOST, PAGE_H, PAGE_Y, SRC, TOTAL, W
from timeline2 import segments

HERE = Path(__file__).parent
OUT = HERE / "seg2"
OUT.mkdir(exist_ok=True)
BG = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
      "gblur=sigma=40,eq=brightness=-0.18:saturation=0.8")
CARD_W, CARD_HH, CARD_TOP = 1000, 562, 560


def base_filter(kind, src, dur, idx):
    """返回作用于输入 0 的滤镜链，输出标签 [v0]。"""
    grade = ",eq=contrast=1.08:saturation=1.15:gamma=0.95" if src in HLG else ""
    pre = f"{AP_CROP}," if src == "ap:crop" else ""
    zoom = f"(1+0.06*t/{dur:.3f})"
    if kind == "H":
        z = 1.0 if idx % 2 == 0 else 1.08  # 新机位更近，推近幅度比上一版小
        return (f"[0:v]fps={FPS},scale={int(W * z)}:{int(H * z)},"
                f"crop={W}:{H}:(iw-{W})/2:(ih-{H})*0.3,setsar=1[v0]")
    if kind == "A":  # 全屏动画：底层用主播模糊画面，动画在 [1:v]
        return (f"[0:v]fps={FPS},{BG},setsar=1[bg];"
                f"[1:v]fps={FPS},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=30[an];"
                f"[bg][an]overlay=0:0:shortest=0[v0]")
    if kind == "P":
        return (f"[0:v]fps={FPS}{grade},scale=w='{W}*{zoom}':h='{H}*{zoom}':eval=frame,"
                f"crop={W}:{H},setsar=1[v0]")
    if kind == "BP":
        fg = f"scale=w='{W}*{zoom}':h='{PAGE_H}*{zoom}':eval=frame,crop={W}:{PAGE_H}:(iw-{W})/2:(ih-{PAGE_H})*0.7"
        return f"[0:v]fps={FPS},split[a][b];[a]{BG}[bg];[b]{fg}[fg];[bg][fg]overlay=0:{PAGE_Y},setsar=1[v0]"
    fg = f"scale=w='{CARD_W}*{zoom}':h='{CARD_HH}*{zoom}':eval=frame,crop={CARD_W}:{CARD_HH}{grade}"
    return (f"[0:v]fps={FPS},{pre}split[a][b];[a]{BG}[bg];[b]{fg}[fg];"
            f"[bg][fg]overlay={(W - CARD_W) // 2}:{CARD_TOP},setsar=1[v0]")


def build(i, seg):
    f0, f1, kind, src, src_t, _, ovl = seg
    n = f1 - f0
    dur = n / FPS
    inputs = []
    if kind in ("H", "A"):
        inputs += ["-ss", f"{f0 / FPS:.3f}", "-i", HOST]
    else:
        inputs += ["-ss", f"{src_t:.3f}", "-i", SRC[src.split(':')[0]]]
    if kind == "A":
        inputs += ["-i", f"{ANIM}/{src}.mov"]
    fc = base_filter(kind, src, dur, i)
    last = "[v0]"
    if ovl:
        path, a_start, speed, dx, dy, delay = ovl
        k = len([x for x in inputs if x == "-i"])
        inputs += ["-ss", f"{a_start:.3f}", "-i", path]
        fc += (f";[{k}:v]fps={FPS},setpts=(PTS-STARTPTS)/{speed}+{delay}/TB,"
               f"tpad=stop_mode=clone:stop_duration=30[ov];"
               f"{last}[ov]overlay={dx}:{dy}:shortest=0:eof_action=repeat[v1]")
        last = "[v1]"
    fc += f";{last}format=yuv420p[out]"
    out = OUT / f"{i:03d}.mp4"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[out]",
           "-an", "-frames:v", str(n), "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-r", str(FPS), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    got = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                          "stream=nb_read_frames", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    return i, kind, src, n, got, r.stderr.strip()[-400:]


def main():
    segs = segments()
    only = {int(x) for x in sys.argv[1:]}
    todo = [(i, s) for i, s in enumerate(segs) if not only or i in only]
    bad = 0
    with ThreadPoolExecutor(4) as ex:
        for i, kind, src, want, got, err in ex.map(lambda a: build(*a), todo):
            ok = str(want) == got.split(",")[0]
            bad += not ok
            print(f"{i:03d} {kind:<2} {str(src)[:24]:<24} 需要 {want} 实得 {got}{'' if ok else '  <<帧数不符'} {err}", flush=True)
    lst = OUT / "list.txt"
    lst.write_text("".join(f"file '{OUT / f'{i:03d}.mp4'}'\n" for i in range(len(segs))))
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"tpad=stop_mode=clone:stop_duration=1,fade=t=out:st={TOTAL - 0.35:.2f}:d=0.35",
                    "-frames:v", str(int(round(TOTAL * FPS))), "-c:v", "libx264", "-preset", "fast", "-crf", "14",
                    "-pix_fmt", "yuv420p", str(HERE / "base2.mp4")], check=True)
    print("base2.mp4 完成，帧数不符的段：", bad)


if __name__ == "__main__":
    main()
