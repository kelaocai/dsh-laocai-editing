"""第 2 步：逐帧渲染动态字幕、角标、动画层（RGBA），管道送给 ffmpeg 叠加到 base.mp4。"""
import os
import json
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from edl import EDL, FPS, H, HOST, SUBS, TOTAL, W, segments

HERE = Path(__file__).parent
FONT_BOLD = os.environ["VIDEO_FONT_BOLD"]
FONT_BLACK = os.environ["VIDEO_FONT_BLACK"]
FONT_MED = os.environ["VIDEO_FONT_MED"]
CYAN = (0, 229, 255)
YELLOW = (255, 226, 0)
WHITE = (255, 255, 255)
RED = (255, 59, 48)


@lru_cache(maxsize=64)
def font(path, size):
    return ImageFont.truetype(path, size)


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = max(0.0, min(1.0, x))
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def lerp(a, b, x):
    return a + (b - a) * x


def seg_kind_at(t):
    kind = "H"
    for st, k, src, _, _ in EDL:
        if t >= st:
            kind = k
    return kind


# ---------- 动态字幕 ----------

def split_runs(text, keys):
    """把一句话切成 [(片段, 是否关键词)]。"""
    marks = [False] * len(text)
    for k in keys:
        i = text.find(k)
        if i >= 0:
            for j in range(i, i + len(k)):
                marks[j] = True
    runs, buf, cur = [], "", None
    for ch, m in zip(text, marks):
        if cur is None or m == cur:
            buf += ch
        else:
            runs.append((buf, cur))
            buf = ch
        cur = m
    if buf:
        runs.append((buf, cur))
    return runs


@lru_cache(maxsize=4096)
def glyph(ch, size, key):
    f = font(FONT_BOLD if key else FONT_BLACK, size)
    box = f.getbbox(ch)
    w = max(box[2] - box[0], int(size * 0.32)) + 16
    h = int(size * 1.35) + 16
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    color = YELLOW if key else WHITE
    d.text((8 - box[0], 8 + int(size * 0.12)), ch, font=f, fill=color,
           stroke_width=7, stroke_fill=(10, 10, 20))
    adv = f.getlength(ch)
    return im, adv


def load_subs():
    """有强制对齐结果就用逐字时间，否则退回 edl.SUBS 的句级时间 + 固定错开。"""
    p = HERE / "subs_aligned.json"
    if p.exists():
        return [(s["start"], s["end"], s["text"], s["keys"], s["chars"])
                for s in json.loads(p.read_text())]
    return [(st, en, text, keys, None) for st, en, text, keys in SUBS]


ALIGNED_SUBS = load_subs()


def draw_sub(canvas, t, y_center):
    for st, en, text, keys, char_t in ALIGNED_SUBS:
        if st <= t < en:
            break
    else:
        return
    age = t - st
    left = en - t
    size = 72 if len(text) <= 12 else max(54, int(72 * 12 / len(text)))
    runs = split_runs(text, keys)
    chars = []
    for seg, key in runs:
        for ch in seg:
            chars.append((ch, key))
    widths = [glyph(ch, int(size * (1.12 if key else 1)), key)[1] for ch, key in chars]
    total_w = sum(widths)
    x = (W - total_w) / 2
    n = len(chars)
    stagger = min(0.035, 0.32 / max(n, 1))
    out_fade = ease_out(min(1, left / 0.12)) if left < 0.12 else 1.0
    # 关键词底条
    kx = x
    for (ch, key), wch in zip(chars, widths):
        kx += wch
    kx = x
    for idx, ((ch, key), wch) in enumerate(zip(chars, widths)):
        # 逐字时间：这个字被说出来的那一刻弹出；无对齐数据时按固定间隔错开
        local = (t - char_t[idx]) if char_t else (age - idx * stagger)
        p = ease_back(local / 0.22)
        if local <= 0:
            kx += wch
            continue
        sz = int(size * (1.12 if key else 1))
        im, _ = glyph(ch, sz, key)
        scale = lerp(1.6, 1.0, p) if local < 0.22 else 1.0
        if key and 0.22 < local < 0.6:  # 关键词二次弹跳（跟随该字自己的出现时间）
            scale *= 1 + 0.08 * math.sin((local - 0.22) / 0.38 * math.pi)
        if scale != 1.0:
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
        alpha = min(1.0, local / 0.12) * out_fade
        if alpha < 1:
            a = im.getchannel("A").point(lambda v: int(v * alpha))
            im = im.copy()
            im.putalpha(a)
        dy = int((1 - ease_out(local / 0.22)) * 30)
        cx = kx + wch / 2
        canvas.alpha_composite(im, (int(cx - im.width / 2), int(y_center - im.height / 2 + dy)))
        kx += wch


# ---------- 角标 / 包装 ----------

def draw_tag(canvas, d, text, age, y=430):
    if not text:
        return
    p = ease_out(age / 0.35)
    f = font(FONT_BOLD, 40)
    tw = f.getlength(text)
    x0 = int(lerp(-tw - 80, 40, p))
    d.rectangle([x0, y, x0 + 10, y + 64], fill=CYAN + (255,))
    d.rectangle([x0 + 14, y, x0 + 14 + tw + 36, y + 64], fill=(8, 14, 28, 220))
    d.text((x0 + 32, y + 9), text, font=f, fill=WHITE)


def draw_breaking(d, t):
    if t > 3.76:
        return
    blink = (int(t * 3) % 2 == 0)
    f = font(FONT_BLACK, 46)
    d.rectangle([40, 240, 300, 312], fill=RED + (255 if blink else 200,))
    d.text((58, 249), "BREAKING", font=f, fill=WHITE)
    f2 = font(FONT_BOLD, 78)
    p = ease_out(t / 0.5)
    txt = "美联社报道了一台中国车"
    tw = f2.getlength(txt)
    x = int(lerp(W, (W - tw) / 2, p))
    d.text((x, 330), txt, font=f2, fill=WHITE, stroke_width=6, stroke_fill=(0, 0, 0))


def draw_corner_brackets(d, box, color, age):
    x0, y0, x1, y1 = box
    L = int(60 * ease_out(age / 0.4))
    for (x, y, sx, sy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line([(x, y), (x + sx * L, y)], fill=color, width=6)
        d.line([(x, y), (x, y + sy * L)], fill=color, width=6)


def draw_progress(d, t):
    d.rectangle([0, H - 10, int(W * t / TOTAL), H], fill=CYAN + (230,))


def draw_brand(d, t):
    f = font(FONT_BOLD, 34)
    d.text((W - 250, 70), "老财科技观察", font=f, fill=(255, 255, 255, 170))


# ---------- 全屏动画：分体式结构 ----------

def tech_bg(canvas, d, age, dim=200):
    over = Image.new("RGBA", (W, H), (4, 10, 22, dim))
    canvas.alpha_composite(over)
    off = int(age * 40) % 80
    for x in range(-80, W + 80, 80):
        d.line([(x + off, 0), (x + off, H)], fill=(0, 229, 255, 22), width=1)
    for y in range(0, H, 80):
        d.line([(0, y + off), (W, y + off)], fill=(0, 229, 255, 22), width=1)


def glow_layer(draw_fn):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    blur = layer.filter(ImageFilter.GaussianBlur(14))
    return blur, layer


def anim_split(canvas, age):
    d = ImageDraw.Draw(canvas)
    tech_bg(canvas, d, age)
    cx = W // 2
    base_y = 1150
    lift = ease_out((age - 0.6) / 1.0) * 260  # 上舱抬起
    swap_t = age - 3.1  # 3.1s 后开始切换上舱用途

    def draw(dd):
        # 底盘：滑板
        dd.rounded_rectangle([cx - 400, base_y, cx + 400, base_y + 70], 30, outline=CYAN, width=6)
        for i in range(-3, 4):
            dd.line([(cx + i * 100, base_y + 12), (cx + i * 100 + 40, base_y + 58)], fill=CYAN + (120,), width=3)
        for wx in (cx - 290, cx + 290):
            dd.ellipse([wx - 85, base_y + 20, wx + 85, base_y + 190], outline=CYAN, width=7)
            dd.ellipse([wx - 35, base_y + 70, wx + 35, base_y + 140], outline=CYAN + (160,), width=4)
        # 上舱
        top = base_y - 330 - lift
        col = YELLOW if lift > 200 else WHITE
        dd.rounded_rectangle([cx - 380, top, cx + 380, top + 320], 90, outline=col, width=7)
        dd.rounded_rectangle([cx - 300, top + 50, cx + 300, top + 190], 40, outline=col + (150,), width=4)
        if lift > 30:  # 分离箭头
            ay = int(top + 320 + (base_y - top - 320) / 2)
            dd.line([(cx, ay - 50), (cx, ay + 50)], fill=WHITE, width=4)
            dd.polygon([(cx - 18, ay - 40), (cx + 18, ay - 40), (cx, ay - 70)], fill=WHITE)
            dd.polygon([(cx - 18, ay + 40), (cx + 18, ay + 40), (cx, ay + 70)], fill=WHITE)
        return top

    blur, layer = glow_layer(draw)
    canvas.alpha_composite(blur)
    canvas.alpha_composite(blur)
    canvas.alpha_composite(layer)
    d = ImageDraw.Draw(canvas)
    top = base_y - 330 - lift
    # 标签
    f = font(FONT_BOLD, 50)
    fs = font(FONT_MED, 34)
    if age > 1.2:
        a = int(255 * ease_out((age - 1.2) / 0.4))
        d.text((cx - 400, base_y + 220), "下层 · 滑板式智能底盘", font=f, fill=CYAN + (a,))
        d.text((cx - 400, base_y + 290), "线控驱动 · 转向 · 制动 · 自动驾驶", font=fs, fill=(200, 230, 255, a))
    if age > 2.2:
        a = int(255 * ease_out((age - 2.2) / 0.4))
        d.text((cx - 400, top - 140), "上层 · 空间自由定制", font=f, fill=YELLOW + (a,))
        d.text((cx - 400, top - 72), "不需要司机，也不需要驾驶位", font=fs, fill=(255, 245, 200, a))
    # 上舱内的场景切换
    labels = ["咖啡馆", "KTV", "办公室", "化妆间"]
    if swap_t > 0:
        k = int(swap_t / 0.7) % len(labels)
        local = (swap_t % 0.7) / 0.7
        fz = font(FONT_BLACK, int(lerp(110, 90, ease_out(local * 3))))
        txt = labels[k]
        tw = fz.getlength(txt)
        d.text((cx - tw / 2, top + 80), txt, font=fz, fill=WHITE, stroke_width=4, stroke_fill=(0, 0, 0))
    hd = font(FONT_BLACK, 64)
    title = "分体式设计"
    p = ease_out(age / 0.4)
    d.text((int(lerp(-500, 60, p)), 300), title, font=hd, fill=WHITE)
    d.rectangle([int(lerp(-500, 60, p)), 385, int(lerp(-500, 60, p)) + 200, 393], fill=CYAN)


# ---------- 全屏动画：营收数据卡 ----------

def anim_revenue(canvas, age):
    d = ImageDraw.Draw(canvas)
    tech_bg(canvas, d, age, 215)
    f = font(FONT_BOLD, 54)
    d.text((80, 360), "贵阳 · 实际运营数据", font=f, fill=CYAN)
    d.text((80, 440), "改造成移动 KTV 后", font=font(FONT_MED, 44), fill=(220, 235, 255))
    # 数字滚动：从 1.2s 开始（对应"达到2400多块钱"）
    p = ease_out((age - 1.2) / 1.4)
    val = 2400 if p > 0.995 else int(2400 * p)
    num = f"¥{val:,}"
    fn = font(FONT_BLACK, 210)
    tw = fn.getlength(num + "+")
    blur, layer = glow_layer(lambda dd: dd.text(((W - tw) / 2, 560), num + ("+" if p > 0.98 else ""),
                                                font=fn, fill=YELLOW))
    canvas.alpha_composite(blur)
    canvas.alpha_composite(layer)
    d.text((W / 2 - 110, 820), "单日营收", font=font(FONT_BOLD, 56), fill=WHITE)
    # 柱状对比
    base = 1420
    bw = 220
    h1 = 160 * ease_out((age - 0.3) / 0.8)
    h2 = 480 * ease_out((age - 1.2) / 1.4)
    x1, x2 = 220, 640
    d.rectangle([x1, base - h1, x1 + bw, base], fill=(120, 140, 170, 255))
    d.rectangle([x2, base - h2, x2 + bw, base], fill=YELLOW + (255,))
    d.line([(120, base), (W - 120, base)], fill=(200, 200, 220, 200), width=4)
    fl = font(FONT_BOLD, 42)
    d.text((x1 - 10, base + 20), "普通载客", font=fl, fill=WHITE)
    d.text((x2 - 10, base + 20), "移动 KTV", font=fl, fill=YELLOW)
    if age > 3.84:  # "翻了三倍"
        q = ease_back((age - 3.84) / 0.3)
        fb = font(FONT_BLACK, int(150 * max(q, 0.01)))
        txt = "×3"
        d.ellipse([W - 380, base - 760, W - 120, base - 500], fill=RED + (255,))
        tw = fb.getlength(txt)
        d.text((W - 250 - tw / 2, base - 730), txt, font=fb, fill=WHITE)


# ---------- 全屏动画：对比 ----------

def car_icon(d, cx, cy, s, color, kind):
    if kind == "taxi":
        d.polygon([(cx - 160 * s, cy + 40 * s), (cx - 120 * s, cy - 10 * s), (cx - 40 * s, cy - 60 * s),
                   (cx + 70 * s, cy - 60 * s), (cx + 160 * s, cy), (cx + 170 * s, cy + 40 * s)],
                  outline=color, width=6)
    else:
        d.rounded_rectangle([cx - 150 * s, cy - 110 * s, cx + 150 * s, cy + 40 * s], 50 * s, outline=color, width=6)
        d.rounded_rectangle([cx - 110 * s, cy - 80 * s, cx + 110 * s, cy - 10 * s], 20 * s, outline=color, width=4)
    for wx in (cx - 95 * s, cx + 95 * s):
        d.ellipse([wx - 38 * s, cy + 10 * s, wx + 38 * s, cy + 86 * s], outline=color, width=6)


def anim_vs(canvas, age, t):
    d = ImageDraw.Draw(canvas)
    tech_bg(canvas, d, age, 210)
    mid = W // 2
    p = ease_out(age / 0.5)
    d.line([(mid, 300), (mid, int(300 + 1050 * p))], fill=(255, 255, 255, 120), width=3)
    fv = font(FONT_BLACK, 110)
    d.ellipse([mid - 90, 700, mid + 90, 880], fill=RED + (255,))
    d.text((mid - fv.getlength("VS") / 2, 718), "VS", font=fv, fill=WHITE)
    ft = font(FONT_BOLD, 54)
    fs = font(FONT_MED, 40)
    lx, rx = mid // 2, mid + mid // 2
    car_icon(d, lx, 520, 1.1 * p, (200, 210, 230), "taxi")
    car_icon(d, rx, 520, 1.0 * p, YELLOW, "bus")
    for x, title, col in ((lx, "特斯拉 Robotaxi", WHITE), (rx, "土豆巴士", YELLOW)):
        d.text((x - ft.getlength(title) / 2, 930), title, font=ft, fill=col)

    def item(x, y, txt, start, col):
        if t < start:
            return
        q = ease_out((t - start) / 0.35)
        f = font(FONT_BOLD, 46)
        tw = f.getlength(txt)
        d.rounded_rectangle([x - tw / 2 - 26, y, x + tw / 2 + 26, y + 80], 18,
                            fill=(col[0], col[1], col[2], int(60 * q)), outline=col + (int(255 * q),), width=3)
        d.text((x - tw / 2, y + 12 + (1 - q) * 20), txt, font=f, fill=WHITE + (int(255 * q),))

    if seg_kind_at(t) == "G" and t < 92.3:  # 第一段对比：特斯拉
        item(lx, 1060, "代步交通工具", 84.6, (180, 190, 210))
        item(lx, 1170, "科技手段", 87.5, (180, 190, 210))
        item(lx, 1280, "安全送达目的地", 90.9, (180, 190, 210))
        fq = font(FONT_BLACK, 200)
        a = int(255 * (0.6 + 0.4 * math.sin(age * 5)))
        d.text((rx - fq.getlength("?") / 2, 1060), "?", font=fq, fill=YELLOW + (a,))
    else:  # 第二段：两种方向
        item(lx, 1060, "改变出行方式", 99.8, (180, 190, 210))
        item(rx, 1060, "移动的生意", 99.8, YELLOW)
        item(rx, 1170, "探索商业运营空间", 101.5, YELLOW)


# ---------- 结尾 ----------

def draw_outro(canvas, d, t):
    if t < 110.18:
        return
    age = t - 110.18
    if t >= 111.46:
        q = ease_back((t - 111.46) / 0.35)
        f = font(FONT_BOLD, 48)
        txt = "评论区告诉我"
        tw = f.getlength(txt)
        y = int(lerp(1330, 1240, q))
        d.rounded_rectangle([(W - tw) / 2 - 40, y, (W + tw) / 2 + 40, y + 96], 48, fill=(8, 14, 28, 220),
                            outline=CYAN, width=4)
        d.text(((W - tw) / 2, y + 18), txt, font=f, fill=WHITE)
    if t >= 112.5:
        q = ease_back((t - 112.5) / 0.35)
        fb = font(FONT_BLACK, 56)
        txt = "+ 关注 老财科技观察"
        tw = fb.getlength(txt)
        bw = (tw + 100) * max(q, 0.05)
        x0 = W / 2 - bw / 2
        d.rounded_rectangle([x0, 1100, x0 + bw, 1210], 55, fill=RED + (255,))
        if q > 0.7:
            d.text(((W - tw) / 2, 1122), txt, font=fb, fill=WHITE)


# ---------- 主循环 ----------

def render_frame(n, segs):
    t = n / FPS
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    seg = next(s for s in segs if s[0] <= n < s[1]) if n < segs[-1][1] else segs[-1]
    f0, f1, kind, src, _, tag = seg
    age = (n - f0) / FPS
    if kind == "G":
        {"split": anim_split, "revenue": anim_revenue}.get(src, lambda c, a: anim_vs(c, a, t))(canvas, age)
    d = ImageDraw.Draw(canvas)
    if kind in ("B", "BP", "P"):
        draw_tag(canvas, d, tag, age, 460 if kind == "BP" else 430)
        if kind == "B":
            draw_corner_brackets(d, (40, 520, W - 40, 1162), CYAN + (230,), age)
    draw_breaking(d, t)
    draw_outro(canvas, d, t)
    draw_brand(d, t)
    draw_progress(d, t)
    draw_sub(canvas, t, 1560 if kind != "H" else 1500)
    return canvas


def main():
    segs = segments()
    total = segs[-1][1]
    only = None
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":  # 只出若干静帧检查
        times = [float(x) for x in sys.argv[2:]]
        base = HERE / "base.mp4"
        for tt in times:
            n = int(tt * FPS)
            bg = HERE / f"_pv_bg.png"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{tt}", "-i", str(base),
                            "-frames:v", "1", str(bg)], check=True)
            im = Image.open(bg).convert("RGBA")
            im.alpha_composite(render_frame(n, segs))
            im.convert("RGB").resize((360, 640)).save(HERE / f"pv_{tt:06.2f}.jpg", quality=80)
        return
    out = HERE / "final_noaudio.mp4"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(HERE / "base.mp4"),
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto",
           "-frames:v", str(total), "-c:v", "libx264", "-preset", "slow", "-crf", "15",
           "-maxrate", "18M", "-bufsize", "36M", "-profile:v", "high", "-level", "4.2", "-g", "60",
           "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(total):
        p.stdin.write(render_frame(n, segs).tobytes())
        if n % 300 == 0:
            print(f"{n}/{total}", flush=True)
    p.stdin.close()
    p.wait()
    print("完成", p.returncode)


if __name__ == "__main__":
    main()
