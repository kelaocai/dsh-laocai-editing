"""第 1 步：按 EDL 生成竖屏底片分段并拼接为 base.mp4（无音频）。"""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from edl import TOTAL, AP_CROP, FPS, H, HLG, HOST, PAGE_H, PAGE_Y, SRC, W, segments

OUT = Path(__file__).parent / "seg"
OUT.mkdir(exist_ok=True)
BG = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
      "gblur=sigma=40,eq=brightness=-0.18:saturation=0.8")
CARD_W, CARD_HH = 1000, 562
CARD_TOP = 560


def vf_for(kind, src, dur, idx):
    grade = ",eq=contrast=1.08:saturation=1.15:gamma=0.95" if src in HLG else ""
    pre = f"{AP_CROP}," if src == "ap:crop" else ""
    zoom = f"(1+0.06*t/{dur:.3f})"
    if kind == "H":
        z = 1.0 if idx % 2 == 0 else 1.14  # 正常 / 推近交替，制造节奏
        return (f"fps={FPS},scale={int(W * z)}:{int(H * z)},"
                f"crop={W}:{H}:(iw-{W})/2:(ih-{H})*0.25,setsar=1")
    if kind == "G":
        return f"fps={FPS},{BG},setsar=1"
    if kind == "P":
        return (f"fps={FPS}{grade},scale=w='{W}*{zoom}':h='{H}*{zoom}':eval=frame,"
                f"crop={W}:{H},setsar=1")
    if kind == "BP":
        fg = (f"scale=w='{W}*{zoom}':h='{PAGE_H}*{zoom}':eval=frame,crop={W}:{PAGE_H}:(iw-{W})/2:(ih-{PAGE_H})*0.7")
        return (f"fps={FPS},split[a][b];[a]{BG}[bg];[b]{fg}[fg];"
                f"[bg][fg]overlay=0:{PAGE_Y},setsar=1")
    # B：横屏卡片 + 同源模糊背景
    fg = (f"{pre}scale=w='{CARD_W}*{zoom}':h='{CARD_HH}*{zoom}':eval=frame,"
          f"crop={CARD_W}:{CARD_HH}{grade}")
    return (f"fps={FPS},{pre}split[a][b];[a]{BG}[bg];[b]{fg.replace(pre, '', 1)}[fg];"
            f"[bg][fg]overlay={(W - CARD_W) // 2}:{CARD_TOP},setsar=1")


def build(i, seg):
    f0, f1, kind, src, src_t, _ = seg
    dur = (f1 - f0) / FPS
    path = HOST if kind in ("H", "G") else SRC[src.split(":")[0]]
    start = f0 / FPS if kind in ("H", "G") else src_t
    out = OUT / f"{i:03d}.mp4"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", path,
           "-t", f"{dur:.4f}", "-an", "-filter_complex", vf_for(kind, src, dur, i),
           "-frames:v", str(f1 - f0), "-c:v", "libx264", "-preset", "fast", "-crf", "16",
           "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
                       capture_output=True, text=True).stdout.strip()
    return i, kind, src, f1 - f0, n, r.stderr.strip()[-300:]


def main():
    segs = segments()
    with ThreadPoolExecutor(4) as ex:
        for i, kind, src, want, got, err in ex.map(lambda a: build(*a), enumerate(segs)):
            flag = "" if str(want) == got else "  <<帧数不符"
            print(f"{i:03d} {kind:<2} {str(src):<10} 需要 {want} 实得 {got}{flag} {err}", flush=True)
    lst = OUT / "list.txt"
    lst.write_text("".join(f"file '{OUT / f'{i:03d}.mp4'}'\n" for i in range(len(segs))))
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-vf", f"tpad=stop_mode=clone:stop=30,fade=t=out:st={TOTAL - 0.35:.2f}:d=0.35", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", str(Path(__file__).parent / "base.mp4")], check=True)
    print("base.mp4 完成")


if __name__ == "__main__":
    sys.exit(main())
