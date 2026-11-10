"""把成片时间轴导出为 Final Cut Pro 工程（FCPXML 1.10），按轨道分开方便二次剪辑。

用法（工作目录里，与本文件的 edl2 / timeline2 / build2 同目录）：
    python3 export_fcpxml.py             生成工程 + SRT 字幕
    python3 export_fcpxml.py --overlay   强制重渲字幕包装层（ProRes 4444 透明）

轨道：
    主轨      主播实拍（仅画面），按剪辑表切段，推近段带缩放
    连接 1    B-roll（仅画面），卡片位置/大小/入点/倍速与成片一致
    连接 2    动画（ProRes 4444 透明）
    连接 3    字幕包装层（字幕、角标、水印、进度条，透明，可整层关闭）
    音频 -1   人声（独立音轨）

注意：
- 成片里 B-roll / 动画下面垫的是模糊主播画面，FCP 里是清晰主播画面，需要手动加模糊。
- 包装层里的字幕是渲染好的像素，改字要改 SUBS2 后重渲包装层，或改用 SRT。
"""
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from edl2 import FPS, H, HOST, SRC, TOTAL, VOICE, W
from timeline2 import build_subs, segments

try:                                       # 第二版模板
    from build2 import CARD_HH as CARD_H, CARD_TOP, CARD_W, PAGE_H, PAGE_Y
    VW, VH, VTOP = CARD_W, round(CARD_W * H / W), CARD_TOP
except ImportError:                        # 第一版模板（build_base）
    from build_base import CARD_H, CARD_TOP, CARD_W
    PAGE_H, PAGE_Y = CARD_H, CARD_TOP
    VW, VH, VTOP = 640, 1138, 330

ZOOM = 1.08           # 主播推近段倍率（新机位 1.08，旧机位 1.14）
HOST_KINDS = {"H"}
ANIM_KINDS = {"G", "A"}
CARD_KINDS = {"B"}
PAGE_KINDS = {"BP"}
FULL_KINDS = {"P"}
VERT_KINDS = {"V"}
PROJECT = "成片_v1_分轨"
OUT_DIR = Path(HOST).parent / "FCP工程"
OVERLAY = OUT_DIR / "字幕包装层.mov"

# 可选：素材段需要慢放/定格时复用底片脚本里的 fit_source
try:
    from build_r1 import fit_source, parse_src_t   # 录音豆版（支持 (入点, 倍速)）
except ImportError:
    def parse_src_t(v):
        return (float(v[0]), float(v[1])) if isinstance(v, (tuple, list)) else (float(v or 0), 1.0)

    def fit_source(src, t, dur, speed):
        return t, speed, 0.0


def probe(path):
    import json
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,r_frame_rate,sample_rate,channels:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    return v, a, float(j["format"]["duration"])


def t(sec, den=FPS):
    """秒 → FCPXML 有理数时间，对齐到帧。"""
    f = Fraction(round(Fraction(sec) * den), den)
    return f"{f.numerator}/{f.denominator}s" if f.denominator != 1 else f"{f.numerator}s"


class Assets:
    def __init__(self):
        self.items, self.ids = [], {}

    def ref(self, path, name=None):
        path = str(path)
        if path in self.ids:
            return self.ids[path]
        v, a, dur = probe(path)
        rid = f"r{len(self.ids) + 10}"
        self.ids[path] = rid
        fmt = ""
        if v:
            fps = Fraction(v["r_frame_rate"])
            self.items.append(f'<format id="{rid}f" frameDuration="{t(1/fps, fps.numerator)}" '
                              f'width="{v["width"]}" height="{v["height"]}"/>')
            fmt = f' format="{rid}f"'
        audio = (f' hasAudio="1" audioSources="1" audioChannels="{a.get("channels", 2)}" '
                 f'audioRate="{a["sample_rate"]}"') if a else ""
        self.items.append(
            f'<asset id="{rid}" name="{escape(name or Path(path).stem)}" start="0s" '
            f'duration="{t(dur, 600)}" hasVideo="{1 if v else 0}"{fmt}{audio}>'
            f'<media-rep kind="original-media" src="file://{quote(path)}"/></asset>')
        return rid


def clip(rid, name, lane, offset, dur, start, role, speed=1.0, scale=1.0, pos_y_px=0.0,
         src_enable=None, inner="", freeze=0.0):
    """生成 asset-clip。speed≠1 或 freeze 时用 timeMap；freeze 即末段时间点取值不变（定格）。"""
    attrs = [f'ref="{rid}"', f'name="{escape(name)}"', f'offset="{t(offset)}"',
             f'duration="{t(dur)}"']
    if lane is not None:
        attrs.append(f'lane="{lane}"')
    attrs.append(f'audioRole="{role}"' if role.startswith(("dialogue", "music"))
                 else f'videoRole="{role}"')
    if src_enable:
        attrs.append(f'srcEnable="{src_enable}"')
    body = ""
    if speed != 1.0 or freeze:
        attrs.append('start="0s"')
        play = dur - freeze
        pts = [(0, start), (play, start + play * speed)]
        if freeze:
            pts.append((dur, start + play * speed))
        body += "<timeMap>" + "".join(
            f'<timept time="{t(a)}" value="{t(b, 600)}" interp="linear"/>' for a, b in pts) + "</timeMap>"
    else:
        attrs.append(f'start="{t(start)}"')
    if scale != 1.0 or pos_y_px:
        # position 单位是画面高度的百分比，y 向上为正
        body += (f'<adjust-transform position="0 {-pos_y_px / H * 100:.4f}" '
                 f'scale="{scale:.4f} {scale:.4f}"/>')
    return f'<asset-clip {" ".join(attrs)}>{body}{inner}</asset-clip>'


def render_overlay():
    """把 render2 的透明层直接编码成 ProRes 4444，不叠底片。"""
    from render2 import render_frame
    total = int(round(TOTAL * FPS))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-frames:v", str(total),
         "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
         "-vendor", "apl0", str(OVERLAY)], stdin=subprocess.PIPE)
    for n in range(total):
        p.stdin.write(render_frame(n).tobytes())
        if n % 900 == 0:
            print(f"包装层 {n}/{total}", flush=True)
    p.stdin.close()
    if p.wait():
        raise SystemExit("包装层渲染失败")


def write_srt():
    def ts(s):
        ms = int(round(max(s, 0) * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    lines = []
    for i, s in enumerate(build_subs(), 1):
        lines += [str(i), f"{ts(s['start'])} --> {ts(s['end'])}", s["text"], ""]
    (OUT_DIR / "字幕.srt").write_text("\n".join(lines), encoding="utf-8")


def main():
    if "--overlay" in sys.argv or not OVERLAY.exists():
        render_overlay()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assets = Assets()
    host = assets.ref(HOST, "主播实拍")
    voice = assets.ref(VOICE, "人声")
    ovl = assets.ref(OVERLAY, "字幕包装层")

    spine, report = [], []
    for i, (f0, f1, kind, src, src_t, tag, _) in enumerate(segments()):
        off, dur = f0 / FPS, (f1 - f0) / FPS
        z = ZOOM if (kind in HOST_KINDS and i % 2) else 1.0
        # 推近以上方 30% 为锚（与底片脚本 crop 的 (ih-H)*0.3 一致），补偿位移让脸不跳
        dy = -(H * z - H) * (0.3 - 0.5) if z != 1.0 else 0.0
        label = {"H": "主播", "G": "主播(动画底)", "A": "主播(动画底)", "B": "主播(B-roll底)",
                 "V": "主播(B-roll底)", "BP": "主播(网页底)", "P": "主播(素材底)"}[kind]
        conn = []
        if kind in CARD_KINDS | PAGE_KINDS | FULL_KINDS | VERT_KINDS:
            key = src.split(":")[0] if isinstance(src, str) else src
            st, spd = parse_src_t(src_t)
            st, spd, freeze = fit_source(key, st, dur, spd)
            rid = assets.ref(SRC[key])
            if kind in CARD_KINDS:
                scale, cy = CARD_W / W, CARD_TOP + CARD_H / 2
            elif kind in VERT_KINDS:
                scale, cy = VH / H, VTOP + VH / 2
            elif kind in PAGE_KINDS:
                scale, cy = 1.0, PAGE_Y + PAGE_H / 2
            else:
                scale, cy = 1.0, H / 2
            conn.append(clip(rid, f"B-roll {tag or key}", 1, off, dur, st, "B-roll", spd,
                             scale, cy - H / 2, src_enable="video", freeze=freeze))
            report.append(f"{off:7.2f} B-roll {Path(SRC[key]).name} 入点 {st:.2f} 倍速 {spd}"
                          + (f" 定格 {freeze}s" if freeze else ""))
        elif kind in ANIM_KINDS:
            rid = assets.ref(src)
            _, _, adur = probe(src)
            spd = 1.0 if adur >= dur else round(adur / dur - 0.001, 4)
            conn.append(clip(rid, Path(src).stem, 2, off, dur, 0, "动画", spd))
            report.append(f"{off:7.2f} 动画 {Path(src).name}" + (f" 倍速 {spd}" if spd != 1 else ""))
        spine.append(clip(host, f"{label} {i:02d}", None, off, dur, off, "主播", 1.0, z, dy,
                          src_enable="video", inner="".join(conn)))

    # 整条人声和包装层挂在第一段主播片段上（lane 片段的 offset 相对父片段）
    tail = "</asset-clip>"
    spine[0] = (spine[0][:-len(tail)]
                + clip(voice, "人声", -1, 0, TOTAL, 0, "dialogue.人声")
                + clip(ovl, "字幕包装层", 3, 0, TOTAL, 0, "字幕包装")
                + tail)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.10">
<resources>
<format id="r1" name="FFVideoFormat1080x1920p30" frameDuration="1/30s" width="{W}" height="{H}" colorSpace="1-1-1 (Rec. 709)"/>
{chr(10).join(assets.items)}
</resources>
<library>
<event name="{Path(HOST).parent.name}">
<project name="{escape(PROJECT)}">
<sequence format="r1" duration="{t(TOTAL)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
<spine>
{chr(10).join(spine)}
</spine>
</sequence>
</project>
</event>
</library>
</fcpxml>
"""
    out = OUT_DIR / f"{PROJECT}.fcpxml"
    out.write_text(xml, encoding="utf-8")
    write_srt()
    print("\n".join(report))
    print("写出", out)


if __name__ == "__main__":
    main()
