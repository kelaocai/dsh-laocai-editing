"""重拍版：按飞书分镜逐个制作包装动画，每个输出一段带透明通道的 MOV（ProRes 4444），可直接叠到任何剪辑里。

用法：
  python anims.py                 渲染全部
  python anims.py a13 a45         只渲染指定镜头
  python anims.py --preview a13   每个动画出 4 张静帧拼图，检查用
时长是按分镜的默认值，拿到新口播后可在 SPECS 里改。
"""
import math
import re
from functools import lru_cache
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from render import (CYAN, FONT_BLACK, FONT_BOLD, FONT_MED, RED, WHITE, YELLOW,
                    ease_back, ease_out, font, glow_layer, lerp)

W, H, FPS = 1080, 1920, 30
ROOT = Path("<项目素材目录>")
OUT = ROOT / "动画素材"
FRAMES = Path(__file__).parent / "anim_frames"   # 1-3 标题墙用到的素材截图
GREY = (150, 165, 190)


def blank(dim=0):
    return Image.new("RGBA", (W, H), (4, 10, 22, dim))


def grid(c, age, alpha=22):
    d = ImageDraw.Draw(c)
    off = int(age * 40) % 80
    for x in range(-80, W + 80, 80):
        d.line([(x + off, 0), (x + off, H)], fill=CYAN + (alpha,), width=1)
    for y in range(0, H, 80):
        d.line([(0, y + off), (W, y + off)], fill=CYAN + (alpha,), width=1)


def glow(c, fn, times=2):
    b, l = glow_layer(fn)
    for _ in range(times):
        c.alpha_composite(b)
    c.alpha_composite(l)


def text_c(d, y, txt, f, fill, stroke=0):
    d.text(((W - f.getlength(txt)) / 2, y), txt, font=f, fill=fill,
           stroke_width=stroke, stroke_fill=(0, 0, 0))


def fade_alpha(c, a):
    if a >= 1:
        return c
    ch = c.getchannel("A").point(lambda v: int(v * a))
    c.putalpha(ch)
    return c


def bus(d, cx, cy, s, col, width=6, inner=True):
    """土豆巴士线框：圆角方盒 + 大窗 + 两轮。"""
    d.rounded_rectangle([cx - 300 * s, cy - 230 * s, cx + 300 * s, cy + 60 * s], 110 * s, outline=col, width=width)
    if inner:
        d.rounded_rectangle([cx - 230 * s, cy - 175 * s, cx + 230 * s, cy - 40 * s], 40 * s, outline=col, width=max(2, width - 2))
    for wx in (cx - 190 * s, cx + 190 * s):
        d.ellipse([wx - 75 * s, cy + 10 * s, wx + 75 * s, cy + 160 * s], outline=col, width=width)
        d.ellipse([wx - 28 * s, cy + 57 * s, wx + 28 * s, cy + 113 * s], outline=col, width=max(2, width - 3))


# ---------------- 1-3 外媒标题墙 ----------------

def a13(age, dur):
    c = blank(0)
    tiles = sorted(FRAMES.glob("*.jpg"))
    d = ImageDraw.Draw(c)
    rnd = [(0.12, 0.18), (0.70, 0.15), (0.18, 0.62), (0.75, 0.58), (0.45, 0.80), (0.08, 0.40),
           (0.82, 0.36), (0.40, 0.10), (0.60, 0.72), (0.25, 0.88), (0.88, 0.82), (0.50, 0.42)]
    for i, path in enumerate(tiles[:12]):
        st = 0.15 + i * 0.22
        if age < st:
            continue
        p = ease_back((age - st) / 0.25)
        im = Image.open(path).convert("RGBA")
        tw = int(380 * max(p, 0.05))
        im = im.resize((tw, int(tw * im.height / im.width)))
        x, y = int(rnd[i][0] * W - tw / 2), int(rnd[i][1] * H - im.height / 2)
        d.rectangle([x - 6, y - 6, x + im.width + 6, y + im.height + 6], fill=WHITE + (255,))
        c.alpha_composite(im, (max(-tw, x), y))
        if age - st < 0.3:  # 弹出放射线
            r = int(40 + 200 * (age - st) / 0.3)
            cx, cy = x + tw // 2, y + im.height // 2
            for k in range(8):
                a = k * math.pi / 4
                d.line([(cx + r * 0.6 * math.cos(a), cy + r * 0.6 * math.sin(a)),
                        (cx + r * math.cos(a), cy + r * math.sin(a))], fill=YELLOW + (220,), width=5)
    # 热度计数器（装饰，不写具体数）
    f = font(FONT_BLACK, 44)
    d.rounded_rectangle([W - 360, 220, W - 40, 300], 20, fill=RED + (230,))
    bars = int(min(1, age / dur) * 10)
    d.text((W - 340, 232), "热度", font=f, fill=WHITE)
    for k in range(bars):
        d.rectangle([W - 220 + k * 17, 280 - k * 5, W - 208 + k * 17, 285], fill=WHITE + (255,))
    return c


# ---------------- 1-4 外网炸了 ----------------

def a14(age, dur):
    c = blank(0)
    d = ImageDraw.Draw(c)
    p = ease_back(age / 0.25)
    f = font(FONT_BLACK, int(220 * max(p, 0.05)))
    txt = "外网炸了"
    shake = int(18 * math.sin(age * 60) * max(0, 1 - age / 0.8))
    y = 780
    # RGB 错位故障
    if int(age * 12) % 3 == 0 and age < 1.5:
        d.text(((W - f.getlength(txt)) / 2 - 12 + shake, y), txt, font=f, fill=(255, 0, 80, 180))
        d.text(((W - f.getlength(txt)) / 2 + 12 + shake, y), txt, font=f, fill=(0, 230, 255, 180))
    d.text(((W - f.getlength(txt)) / 2 + shake, y), txt, font=f, fill=YELLOW, stroke_width=10, stroke_fill=(0, 0, 0))
    for k in range(6):  # 扫描条
        yy = (int(age * 900) + k * 330) % H
        d.rectangle([0, yy, W, yy + 6], fill=(255, 255, 255, 40))
    return c


# ---------------- 1-5 线框扫描成型 + 标题 ----------------

def a15(age, dur):
    c = blank(255)
    grid(c, age, 18)
    scan = ease_out(age / 1.4)
    y_scan = int(500 + 900 * scan)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    bus(ld, W // 2, 1000, 1.25, CYAN)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rectangle([0, 0, W, y_scan], fill=255)
    layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (W, H), 0), mask))
    c.alpha_composite(layer.filter(ImageFilter.GaussianBlur(12)))
    c.alpha_composite(layer)
    d = ImageDraw.Draw(c)
    if scan < 1:
        d.rectangle([0, y_scan - 3, W, y_scan + 3], fill=WHITE + (230,))
    if age > 1.2:
        q = ease_out((age - 1.2) / 0.5)
        text_c(d, 1330 + (1 - q) * 40, "土豆巴士", font(FONT_BLACK, 130), WHITE + (int(255 * q),))
        text_c(d, 1490, "一台没有方向盘的中国车", font(FONT_BOLD, 54), CYAN + (int(255 * q),))
        text_c(d, 1580, "PIX Moving 出品", font(FONT_MED, 38), GREY + (int(255 * q),))
    return c


# ---------------- 2-1 海外爆火 → 火回国内 时间线 ----------------

FADE_TOP = 980  # 主播脸在 420-1020，渐变从这里开始往下压暗，不挡脸
OUTLINE = (4, 10, 22)  # 文字描边色：没有面板托底，靠粗描边保证可读


def track(d, y, label, lab_col, nodes, age, start):
    """一条横向路径：左侧标签 + 依次点亮的节点。nodes: [(文字, 颜色, 出现时间)]。"""
    if age < start:
        return
    q = ease_out((age - start) / 0.35)
    a = int(255 * q)
    d.text((60 - (1 - q) * 60, y - 32), label, font=font(FONT_BLACK, 56), fill=lab_col + (a,),
           stroke_width=5, stroke_fill=OUTLINE + (a,))
    xs = [430, 830]
    for i, (txt, col, t0) in enumerate(nodes):
        if age < t0:
            continue
        k = ease_out((age - t0) / 0.4)
        x_prev = 330 if i == 0 else xs[i - 1] + 28
        x_end = lerp(x_prev, xs[i] - 28, k)
        d.line([(x_prev, y), (x_end, y)], fill=OUTLINE + (150,), width=11)  # 线也加一道暗色底
        d.line([(x_prev, y), (x_end, y)], fill=(255, 255, 255, 220), width=5)
        if k > 0.9:
            p = ease_back((age - t0 - 0.36) / 0.3)
            r = int(24 * max(p, 0.05))
            d.ellipse([xs[i] - r - 4, y - r - 4, xs[i] + r + 4, y + r + 4], fill=OUTLINE + (200,))
            d.ellipse([xs[i] - r, y - r, xs[i] + r, y + r], fill=col + (255,))
            f = font(FONT_BOLD, 44)
            a = int(255 * min(p, 1))
            d.text((xs[i] - f.getlength(txt) / 2, y + 40), txt, font=f, fill=WHITE + (a,),
                   stroke_width=5, stroke_fill=OUTLINE + (a,))


def a21(age, dur):
    """2-1 底部渐变（方案 B）：名牌 → DeepSeek 路径 → 土豆巴士同一条路。时间按口播对齐（镜头内相对秒）。"""
    c = blank(0)
    d = ImageDraw.Draw(c)
    fade_in = ease_out(age / 0.4)
    for y in range(FADE_TOP, H):  # 从胸口往下渐渐压暗，没有面板边界
        d.line([(0, y), (W, y)], fill=OUTLINE + (int(min(1, (y - FADE_TOP) / 340) * 190 * fade_in),))
    # 名牌：我是老财（0.55s）→ 在 DeepSeek 出现前收掉
    if 0.4 < age < 3.0:
        q = ease_out((age - 0.4) / 0.3) * (1 - ease_out((age - 2.7) / 0.3))
        f1, f2 = font(FONT_BLACK, 80), font(FONT_BOLD, 46)
        a = int(255 * q)
        d.rectangle([60, 1130, 72, 1290], fill=YELLOW + (a,))
        d.text((100, 1120), "老财", font=f1, fill=WHITE + (a,), stroke_width=5, stroke_fill=OUTLINE + (a,))
        d.text((100, 1230), "老财科技观察", font=f2, fill=CYAN + (a,), stroke_width=5, stroke_fill=OUTLINE + (a,))
    # DeepSeek 路径（3.03 出现，3.83 海外刷屏，5.11 火回国内）
    track(d, 1150, "DeepSeek", GREY, [("海外刷屏", RED, 3.6), ("火回国内", YELLOW, 4.9)], age, 3.0)
    # 土豆巴士路径（6.31 出现，7.99 同一条路）
    track(d, 1350, "土豆巴士", YELLOW, [("海外爆火", RED, 6.5), ("火回国内？", YELLOW, 7.7)], age, 6.3)
    if age > 8.0:  # 终点脉冲 + "同一条路"
        a = int(255 * (0.55 + 0.45 * math.sin((age - 8.0) * 8)))
        d.ellipse([830 - 44, 1350 - 44, 830 + 44, 1350 + 44], outline=YELLOW + (a,), width=6)
        q = ease_back((age - 8.0) / 0.3)
        f = font(FONT_BLACK, int(46 * max(q, 0.05)))
        d.rounded_rectangle([700, 1060, 1030, 1130], 20, fill=YELLOW + (255,))
        d.text((865 - f.getlength("同一条路") / 2, 1068), "同一条路", font=f, fill=(20, 20, 30))
    return c


# ---------------- 2-2 部件打叉 + 四国国旗 ----------------

def flag(d, kind, x, y, w):
    h = int(w * 0.66)
    if kind == "法国":
        for i, col in enumerate([(0, 85, 164), (255, 255, 255), (239, 65, 53)]):
            d.rectangle([x + i * w // 3, y, x + (i + 1) * w // 3, y + h], fill=col + (255,))
    elif kind == "德国":
        for i, col in enumerate([(0, 0, 0), (221, 0, 0), (255, 206, 0)]):
            d.rectangle([x, y + i * h // 3, x + w, y + (i + 1) * h // 3], fill=col + (255,))
    elif kind == "瑞士":
        d.rectangle([x, y, x + w, y + h], fill=(218, 41, 28, 255))
        cx, cy, s = x + w // 2, y + h // 2, h // 6
        d.rectangle([cx - s, cy - 3 * s, cx + s, cy + 3 * s], fill=WHITE + (255,))
        d.rectangle([cx - 3 * s, cy - s, cx + 3 * s, cy + s], fill=WHITE + (255,))
    else:  # 日本
        d.rectangle([x, y, x + w, y + h], fill=WHITE + (255,))
        r = h * 3 // 10
        d.ellipse([x + w // 2 - r, y + h // 2 - r, x + w // 2 + r, y + h // 2 + r], fill=(188, 0, 45, 255))
    d.rectangle([x, y, x + w, y + h], outline=(255, 255, 255, 200), width=2)


def a22(age, dur):
    c = blank(0)
    d = ImageDraw.Draw(c)
    parts = ["方向盘", "踏板", "后视镜", "雨刮器"]
    f = font(FONT_BOLD, 48)
    for i, name in enumerate(parts):
        st = 0.2 + i * 0.55
        if age < st:
            continue
        q = ease_back((age - st) / 0.25)
        x, y = 60, 560 + i * 130
        d.rounded_rectangle([x, y, x + 300, y + 100], 22, fill=(4, 10, 22, 210), outline=WHITE + (180,), width=3)
        d.text((x + 30, y + 22), name, font=f, fill=WHITE)
        if age > st + 0.25:  # 红叉
            k = ease_out((age - st - 0.25) / 0.2)
            cx, cy, r = x + 255, y + 50, 30
            d.line([(cx - r, cy - r), (cx - r + 2 * r * k, cy - r + 2 * r * k)], fill=RED, width=10)
            d.line([(cx + r, cy - r), (cx + r - 2 * r * k, cy - r + 2 * r * k)], fill=RED, width=10)
    # 四国国旗
    for i, name in enumerate(["法国", "德国", "瑞士", "日本"]):
        st = 2.8 + i * 0.4
        if age < st:
            continue
        q = ease_out((age - st) / 0.3)
        x, y = 690, int(560 + i * 130 + (1 - q) * 30)
        flag(d, name, x, y, 120)
        d.text((x + 140, y + 12), name, font=font(FONT_BOLD, 46), fill=WHITE + (int(255 * q),))
    if age > dur - 1.4:
        q = ease_back((age - dur + 1.4) / 0.35)
        f2 = font(FONT_BLACK, int(150 * max(q, 0.05)))
        text_c(d, 1150, "凭什么？", f2, YELLOW, stroke=8)
    return c


# ---------------- 3-1 / 3-5 地球飞线 ----------------

CITIES = {  # 经度, 纬度
    "贵阳": (106.6, 26.6), "巴黎": (2.35, 48.85), "开姆尼茨": (12.9, 50.8), "苏黎世": (8.5, 47.4),
    "东京": (139.8, 35.7), "意大利": (12.5, 41.9), "西班牙": (-3.7, 40.4), "比利时": (4.35, 50.85),
    "美国": (-95.0, 38.0), "印度": (77.2, 28.6),
}


def project(lon, lat, rot, R, cx, cy):
    lam, phi = math.radians(lon + rot), math.radians(lat)
    x = math.cos(phi) * math.sin(lam)
    y = math.sin(phi)
    z = math.cos(phi) * math.cos(lam)
    return cx + R * x, cy - R * y, z


def globe(c, age, rot, R, cx, cy, targets, start, step):
    d = ImageDraw.Draw(c)

    def base(dd):
        dd.ellipse([cx - R, cy - R, cx + R, cy + R], outline=CYAN + (200,), width=4)
        for lat in range(-60, 90, 30):
            pts = [project(lon, lat, rot, R, cx, cy) for lon in range(-180, 181, 6)]
            for a, b in zip(pts, pts[1:]):
                if a[2] > 0 and b[2] > 0:
                    dd.line([a[:2], b[:2]], fill=CYAN + (70,), width=2)
        for lon in range(-180, 180, 30):
            pts = [project(lon, lat, rot, R, cx, cy) for lat in range(-90, 91, 6)]
            for a, b in zip(pts, pts[1:]):
                if a[2] > 0 and b[2] > 0:
                    dd.line([a[:2], b[:2]], fill=CYAN + (70,), width=2)
    glow(c, base, 1)
    gx, gy, gz = project(*CITIES["贵阳"], rot, R, cx, cy)
    pulse = 18 + 14 * math.sin(age * 6)
    d.ellipse([gx - pulse, gy - pulse, gx + pulse, gy + pulse], outline=YELLOW, width=4)
    d.ellipse([gx - 10, gy - 10, gx + 10, gy + 10], fill=YELLOW + (255,))
    d.text((gx + 20, gy - 20), "贵阳", font=font(FONT_BOLD, 40), fill=YELLOW)
    for i, name in enumerate(targets):
        st = start + i * step
        if age < st:
            continue
        k = ease_out((age - st) / 0.6)
        tx, ty, tz = project(*CITIES[name], rot, R, cx, cy)
        mx, my = (gx + tx) / 2, (gy + ty) / 2 - R * 0.35
        pts = []
        for j in range(int(30 * k) + 1):
            u = j / 30
            pts.append(((1 - u) ** 2 * gx + 2 * (1 - u) * u * mx + u * u * tx,
                        (1 - u) ** 2 * gy + 2 * (1 - u) * u * my + u * u * ty))
        if len(pts) > 1:
            d.line(pts, fill=YELLOW + (230,), width=4)
        if k >= 1:
            d.ellipse([tx - 9, ty - 9, tx + 9, ty + 9], fill=WHITE + (255,))
            d.text((tx + 14, ty - 22), name, font=font(FONT_BOLD, 34), fill=WHITE)


def a31(age, dur):
    c = blank(235)
    grid(c, age, 14)
    globe(c, age, -106.6 + 40 * (1 - ease_out(age / dur)), 380, W // 2, 900, [], 0, 0)
    d = ImageDraw.Draw(c)
    q = ease_out((age - 0.5) / 0.5)
    lat = 26.6 * ease_out(age / 1.5)
    text_c(d, 1380, f"GUIYANG  {lat:4.1f}°N  106.6°E", font(FONT_MED, 46), CYAN + (int(255 * q),))
    return c


def a35_globe(age, dur):
    """旧版 3D 地球（欧洲几个点挤在一起，已弃用，留作参考）。"""
    c = blank(235)
    grid(c, age, 14)
    R = int(lerp(380, 300, ease_out(age / 1.0)))
    globe(c, age, -60, R, W // 2, 820, ["巴黎", "开姆尼茨", "苏黎世", "东京", "意大利", "西班牙", "比利时", "美国", "印度"],
          0.1, 0.45)
    return c


# 粗略大陆轮廓（经度, 纬度），只用于点阵示意，不追求精确
LAND = [
    [(-168, 66), (-140, 70), (-95, 72), (-80, 62), (-60, 55), (-55, 48), (-70, 43), (-76, 35), (-81, 25),
     (-97, 26), (-105, 20), (-95, 16), (-83, 9), (-78, 8), (-90, 15), (-105, 22), (-117, 32), (-124, 40),
     (-125, 49), (-135, 58), (-150, 60), (-165, 60)],
    [(-55, 60), (-45, 60), (-20, 70), (-20, 80), (-60, 82), (-72, 77), (-55, 68)],
    [(-80, 8), (-60, 10), (-50, 0), (-35, -6), (-40, -22), (-48, -28), (-58, -38), (-65, -55), (-72, -50),
     (-72, -30), (-70, -18), (-81, -5)],
    [(-10, 36), (-9, 43), (-2, 44), (-5, 48), (2, 51), (8, 54), (5, 58), (10, 63), (20, 70), (30, 70),
     (40, 66), (40, 45), (28, 41), (26, 38), (20, 40), (18, 40), (16, 38), (12, 44), (8, 44), (3, 42), (-5, 36)],
    [(-6, 50), (2, 51), (0, 58), (-6, 58)],
    [(-17, 21), (-10, 35), (10, 37), (32, 31), (43, 12), (51, 12), (40, -15), (32, -29), (20, -35), (12, -17),
     (9, -1), (-8, 4), (-17, 14)],
    [(26, 40), (36, 36), (35, 30), (43, 13), (52, 15), (57, 24), (66, 25), (72, 20), (77, 8), (80, 15), (88, 22),
     (92, 21), (98, 16), (100, 5), (104, 1), (109, 12), (108, 21), (117, 23), (122, 30), (122, 40), (128, 35),
     (130, 42), (140, 50), (143, 59), (160, 62), (180, 66), (180, 72), (140, 73), (100, 78), (70, 73), (60, 70),
     (40, 66), (40, 45), (28, 41)],
    [(130, 31), (135, 34), (141, 36), (142, 40), (141, 45), (139, 40), (133, 34)],
    [(114, -22), (122, -17), (131, -12), (137, -12), (142, -11), (146, -19), (153, -26), (150, -37), (141, -38),
     (131, -31), (116, -35), (113, -26)],
]


def inside(lon, lat):
    for poly in LAND:
        hit = False
        for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                hit = not hit
        if hit:
            return True
    return False


@lru_cache(maxsize=4)
def land_dots(lon0, lon1, lat0, lat1, step):
    return [(lon, lat) for lat in np.arange(lat0, lat1, step) for lon in np.arange(lon0, lon1, step)
            if inside(lon, lat)]


class Proj:
    """经纬度 → 屏幕坐标（等距圆柱投影）。"""

    def __init__(self, box, lon0, lon1, lat0, lat1):
        self.x0, self.y0, self.x1, self.y1 = box
        self.lon0, self.lon1, self.lat0, self.lat1 = lon0, lon1, lat0, lat1

    def __call__(self, lon, lat):
        x = self.x0 + (lon - self.lon0) / (self.lon1 - self.lon0) * (self.x1 - self.x0)
        y = self.y1 - (lat - self.lat0) / (self.lat1 - self.lat0) * (self.y1 - self.y0)
        return x, y


GUIYANG = (106.6, 26.6)
WORLD = [("日本", (139.8, 35.7), 0.0, (16, -30)), ("美国", (-95.0, 38.0), 2.07, (16, -30)),
         ("印度", (77.2, 28.6), 2.63, (-100, -46))]
EUROPE = [("法国", (2.35, 48.85), 0.0, (-110, 0)), ("德国", (12.9, 50.8), 0.0, (18, -40)),
          ("瑞士", (8.5, 47.4), 0.0, (18, 4)), ("意大利", (12.5, 41.9), 0.39, (18, -10)),
          ("西班牙", (-3.7, 40.4), 0.95, (-40, 22)), ("比利时", (4.35, 50.85), 1.51, (-150, -46))]
EU_BOX = (-12, 24, 35, 57)


def pin(d, x, y, name, off, q, col, size):
    if q <= 0.02:  # 出现前不画（否则文字描边会留下残影）
        return
    q = min(q, 1.0) if q < 1 else q
    r = 10 + 14 * (1 - q) if q < 1 else 10
    d.ellipse([x - r - 8, y - r - 8, x + r + 8, y + r + 8], outline=col + (int(160 * q),), width=3)
    d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=col + (int(255 * q),))
    f = font(FONT_BOLD, size)
    a = int(255 * min(q, 1.0))
    d.text((x + off[0], y + off[1]), name, font=f, fill=WHITE + (a,),
           stroke_width=4, stroke_fill=(4, 10, 22, a))


def arc(d, a, b, k, col, lift=0.35):
    (ax, ay), (bx, by) = a, b
    mx, my = (ax + bx) / 2, min(ay, by) - abs(bx - ax) * lift
    pts = [((1 - u) ** 2 * ax + 2 * (1 - u) * u * mx + u * u * bx,
            (1 - u) ** 2 * ay + 2 * (1 - u) * u * my + u * u * by) for u in np.linspace(0, k, max(2, int(40 * k)))]
    d.line(pts, fill=col, width=4)


def a35(age, dur):
    """3-5 平面世界地图 + 欧洲放大图，国家按口播顺序点亮（时间来自强制对齐）。"""
    c = blank(235)
    grid(c, age, 12)
    d = ImageDraw.Draw(c)
    appear = ease_out(age / 0.3)

    # 标题
    text_c(d, 250, "已落地多国", font(FONT_BLACK, 84), YELLOW + (int(255 * appear),))
    text_c(d, 350, "公开道路 · 载客运营", font(FONT_BOLD, 44), WHITE + (int(255 * appear),))

    # 世界地图
    wp = Proj((40, 440, W - 40, 860), -130, 160, -40, 72)
    for lon, lat in land_dots(-130, 160, -40, 72, 3.0):
        x, y = wp(lon, lat)
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(0, 229, 255, int(90 * appear)))
    g = wp(*GUIYANG)

    # 欧洲框 + 放大连接线
    ex0, ey0 = wp(EU_BOX[0], EU_BOX[3])
    ex1, ey1 = wp(EU_BOX[1], EU_BOX[2])
    ip = Proj((60, 930, W - 60, 1560), *EU_BOX)
    d.rectangle([ex0, ey0, ex1, ey1], outline=YELLOW + (int(230 * appear),), width=3)
    d.line([(ex0, ey1), (ip.x0, ip.y0)], fill=YELLOW + (int(110 * appear),), width=2)
    d.line([(ex1, ey1), (ip.x1, ip.y0)], fill=YELLOW + (int(110 * appear),), width=2)
    arc(d, g, ((ex0 + ex1) / 2, (ey0 + ey1) / 2), ease_out(age / 0.4), YELLOW + (230,))

    # 世界级的点
    for name, ll, st, off in WORLD:
        k = ease_out((age - st) / 0.45) if st else appear
        if k > 0:
            arc(d, g, wp(*ll), k, YELLOW + (230,))
        pin(d, *wp(*ll), name, off, ease_back((age - st - 0.3) / 0.3) if st else appear, WHITE, 38)
    pin(d, *g, "中国 · 贵阳", (-60, 18), appear, YELLOW, 40)

    # 欧洲放大图
    d.rounded_rectangle([ip.x0 - 10, ip.y0 - 10, ip.x1 + 10, ip.y1 + 10], 24,
                        fill=(4, 10, 22, int(200 * appear)), outline=YELLOW + (int(200 * appear),), width=3)
    for lon, lat in land_dots(*EU_BOX, 0.9):
        x, y = ip(lon, lat)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(0, 229, 255, int(70 * appear)))
    d.text((ip.x0 + 16, ip.y0 + 8), "欧洲", font=font(FONT_BOLD, 36), fill=YELLOW + (int(255 * appear),))
    for name, ll, st, off in EUROPE:
        q = ease_back((age - st) / 0.3) if st else appear
        pin(d, *ip(*ll), name, off, q, YELLOW if st else WHITE, 46)

    # "多个国家"时整体脉冲一次
    if 3.35 < age < 3.95:
        a = int(120 * math.sin((age - 3.35) / 0.6 * math.pi))
        d.rounded_rectangle([ip.x0 - 10, ip.y0 - 10, ip.x1 + 10, ip.y1 + 10], 24, outline=WHITE + (a,), width=8)
    return c


# ---------------- 4-1 车？→ 移动空间 ----------------

def a41(age, dur):
    c = blank(0)
    d = ImageDraw.Draw(c)
    f = font(FONT_BLACK, 170)
    y = 560
    text_c(d, y, "车？", f, WHITE, stroke=8)
    if age > 1.2:
        k = ease_out((age - 1.2) / 0.3)
        tw = f.getlength("车？")
        x0 = (W - tw) / 2 - 20
        d.line([(x0, y + 110), (x0 + (tw + 40) * k, y + 90)], fill=RED, width=16)
    if age > 2.6:
        q = ease_back((age - 2.6) / 0.35)
        f2 = font(FONT_BLACK, int(150 * max(q, 0.05)))
        text_c(d, 800, "移动空间", f2, YELLOW, stroke=8)
    return c


# ---------------- 4-2 X 光线框 + 标注 + 分离 ----------------

def a42(age, dur):
    c = blank(225)
    grid(c, age, 18)
    cx, base_y = W // 2, 1180
    lift = ease_out((age - 4.0) / 1.2) * 240

    def draw(dd):
        top = base_y - 330 - lift
        dd.rounded_rectangle([cx - 380, top, cx + 380, top + 320], 90, outline=WHITE, width=6)
        dd.rounded_rectangle([cx - 300, top + 50, cx + 300, top + 190], 40, outline=WHITE + (140,), width=3)
        # 车内空：无驾驶位，用虚线座椅轮廓表示只有乘客区
        for sx in (cx - 200, cx + 120):
            for yy in range(int(top + 210), int(top + 300), 14):
                dd.line([(sx, yy), (sx, yy + 7)], fill=WHITE + (120,), width=3)
        dd.rounded_rectangle([cx - 400, base_y, cx + 400, base_y + 70], 30, outline=CYAN, width=6)
        for wx in (cx - 290, cx + 290):
            dd.ellipse([wx - 85, base_y + 20, wx + 85, base_y + 190], outline=CYAN, width=7)
        # 传感器
        for sx in (cx - 340, cx + 340):
            dd.ellipse([sx - 16, top - 16, sx + 16, top + 16], outline=YELLOW, width=4)
    glow(c, draw)
    d = ImageDraw.Draw(c)
    top = base_y - 330 - lift
    labels = [("无驾驶位", (cx - 200, top + 250), (90, top - 160)),
              ("无方向盘 · 无踏板", (cx + 120, top + 250), (560, top - 160)),
              ("传感器阵列", (cx + 340, top), (700, top - 300)),
              ("线控底盘", (cx, base_y + 35), (360, base_y + 260))]
    f = font(FONT_BOLD, 42)
    for i, (txt, (px, py), (lx, ly)) in enumerate(labels):
        st = 0.4 + i * 0.7
        if age < st:
            continue
        k = ease_out((age - st) / 0.4)
        ex, ey = lerp(px, lx + 10, k), lerp(py, ly + 60, k)
        d.line([(px, py), (ex, ey)], fill=YELLOW, width=3)
        d.ellipse([px - 8, py - 8, px + 8, py + 8], fill=YELLOW + (255,))
        if k > 0.9:
            tw = f.getlength(txt)
            d.rounded_rectangle([lx, ly, lx + tw + 40, ly + 66], 14, fill=(4, 10, 22, 230), outline=YELLOW, width=3)
            d.text((lx + 20, ly + 10), txt, font=f, fill=WHITE)
    if age > 4.6:
        q = ease_out((age - 4.6) / 0.4)
        d.text((cx - 400, top - 70 - 60), "上层 · 盒子随意换", font=font(FONT_BOLD, 46), fill=YELLOW + (int(255 * q),))
        d.text((cx - 400, base_y + 210), "下层 · 滑板式底盘", font=font(FONT_BOLD, 46), fill=CYAN + (int(255 * q),))
    hd = font(FONT_BLACK, 64)
    d.text((60, 260), "正向研发 · 取消驾驶位", font=hd, fill=WHITE)
    return c


# ---------------- 4-3 数天 → 数小时 ----------------

def a43(age, dur):
    c = blank(0)
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([90, 1230, W - 90, 1560], 30, fill=(4, 10, 22, 225), outline=CYAN, width=4)
    d.text((140, 1260), "设计 → 制造 周期", font=font(FONT_BOLD, 44), fill=CYAN)
    p = ease_out((age - 0.6) / 1.6)
    f = font(FONT_BLACK, 110)
    if p < 0.5:
        txt, col = "数天", WHITE
    else:
        txt, col = "数小时", YELLOW
    d.text((140, 1340), txt, font=f, fill=col)
    # 进度条缩短
    bw = int(lerp(800, 180, p))
    d.rounded_rectangle([140, 1490, 140 + bw, 1520], 15, fill=col + (255,))
    if p >= 0.5:
        d.text((560, 1370), "未来", font=font(FONT_BOLD, 52), fill=YELLOW)
    tag = "PIX × Autodesk × AWS"
    d.rounded_rectangle([60, 260, 60 + font(FONT_BOLD, 40).getlength(tag) + 40, 330], 16, fill=(4, 10, 22, 220))
    d.text((80, 270), tag, font=font(FONT_BOLD, 40), fill=WHITE)
    return c


# ---------------- 4-4 四场景卡片 ----------------

SCENES = [("01", "移动 KTV"), ("02", "移动餐车"), ("03", "移动办公室"), ("04", "移动化妆间")]


def a44(age, dur):
    """16 秒：每 4 秒一个场景卡片翻转进入，叠在对应场景素材上。"""
    c = blank(0)
    d = ImageDraw.Draw(c)
    k = min(3, int(age / (dur / 4)))
    local = age - k * dur / 4
    num, name = SCENES[k]
    flip = ease_out(local / 0.35)
    f = font(FONT_BLACK, 84)
    tw = f.getlength(name)
    cw = int((tw + 120) * max(flip, 0.03))
    x0 = (W - cw) // 2
    d.rounded_rectangle([x0, 1260, x0 + cw, 1420], 30, fill=(4, 10, 22, 230), outline=YELLOW, width=5)
    if flip > 0.7:
        d.text(((W - tw) / 2, 1290), name, font=f, fill=WHITE)
    d.text((60, 260), f"{num}/04", font=font(FONT_BLACK, 70), fill=YELLOW)
    for i in range(4):
        col = YELLOW if i <= k else (255, 255, 255, 80)
        d.rounded_rectangle([60 + i * 60, 360, 100 + i * 60, 372], 6, fill=col)
    return c


# ---------------- 4-5 三个关键词 ----------------

def a45(age, dur):
    c = blank(0)
    d = ImageDraw.Draw(c)
    words = ["能走", "能赚钱", "能百变"]
    f = font(FONT_BLACK, 72)
    gap = 40
    ws = [f.getlength(w) + 60 for w in words]
    x = (W - sum(ws) - gap * 2) / 2
    for i, (w, bw) in enumerate(zip(words, ws)):
        st = 0.2 + i * 0.8
        on = age >= st
        q = ease_back((age - st) / 0.3) if on else 0
        y = 1240 - (20 * q if on else 0)
        d.rounded_rectangle([x, y, x + bw, y + 120], 26, fill=(YELLOW + (255,)) if on else (4, 10, 22, 160),
                            outline=YELLOW, width=4)
        d.text((x + 30, y + 18), w, font=f, fill=(20, 20, 30) if on else (255, 255, 255, 120))
        x += bw + gap
    return c


# ---------------- 5-1 NOT A CONCEPT 印章 ----------------

def a51(age, dur):
    c = blank(0)
    st = 0.6
    if age < st:
        return c
    q = (age - st) / 0.2
    scale = lerp(2.6, 1.0, ease_out(q)) if q < 1 else 1.0
    stamp = Image.new("RGBA", (860, 300), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.rounded_rectangle([10, 10, 850, 290], 30, outline=RED, width=14)
    f = font(FONT_BLACK, 84)
    sd.text(((860 - f.getlength("NOT A CONCEPT")) / 2, 50), "NOT A CONCEPT", font=f, fill=RED)
    f2 = font(FONT_BOLD, 50)
    sd.text(((860 - f2.getlength("不是概念车")) / 2, 180), "不是概念车", font=f2, fill=RED)
    stamp = stamp.rotate(-8, expand=True, resample=Image.BICUBIC)
    stamp = stamp.resize((int(stamp.width * scale), int(stamp.height * scale)))
    shake = int(10 * math.sin(age * 80)) if 1 < q < 2.5 else 0
    c.alpha_composite(stamp, ((W - stamp.width) // 2 + shake, 1180 - stamp.height // 2))
    return c


# ---------------- 5-2 数据卡 841 ----------------

def a52(age, dur):
    c = blank(230)
    grid(c, age, 16)
    d = ImageDraw.Draw(c)
    d.text((80, 360), "贵阳 · 实际运营数据", font=font(FONT_BOLD, 54), fill=CYAN)
    p = ease_out((age - 0.5) / 1.4)
    val = 841 if p > 0.995 else int(841 * p)
    fn = font(FONT_BLACK, 260)
    num = f"¥{val}"
    tw = fn.getlength(num)
    glow(c, lambda dd: dd.text(((W - tw) / 2, 700), num, font=fn, fill=YELLOW))
    d = ImageDraw.Draw(c)
    text_c(d, 1030, "单线日均营收", font(FONT_BOLD, 64), WHITE)
    text_c(d, 1700, "数据来源：PIX", font(FONT_MED, 34), GREY)
    return c


# ---------------- 5-3 数据卡 841 vs 2600+ ----------------

def a53(age, dur):
    c = blank(230)
    grid(c, age, 16)
    d = ImageDraw.Draw(c)
    d.text((80, 360), "爆款 · 移动 KTV", font=font(FONT_BOLD, 54), fill=CYAN)
    p = ease_out((age - 0.8) / 1.6)
    val = 2600 if p > 0.995 else int(2600 * p)
    fn = font(FONT_BLACK, 200)
    num = f"¥{val:,}" + ("+" if p > 0.995 else "")
    tw = fn.getlength(num)
    glow(c, lambda dd: dd.text(((W - tw) / 2, 480), num, font=fn, fill=YELLOW))
    d = ImageDraw.Draw(c)
    text_c(d, 720, "单车营收", font(FONT_BOLD, 60), WHITE)
    base, bw = 1480, 240
    h1 = 170 * ease_out((age - 0.2) / 0.7)
    h2 = 525 * p
    x1, x2 = 200, 640
    d.rectangle([x1, base - h1, x1 + bw, base], fill=GREY + (255,))
    d.rectangle([x2, base - h2, x2 + bw, base], fill=YELLOW + (255,))
    d.line([(120, base), (W - 120, base)], fill=(220, 220, 230, 200), width=4)
    fl = font(FONT_BOLD, 42)
    d.text((x1 + 20, base - h1 - 70), "¥841", font=fl, fill=WHITE)
    d.text((x1 - 10, base + 20), "普通线路", font=fl, fill=WHITE)
    d.text((x2 - 10, base + 20), "移动 KTV", font=fl, fill=YELLOW)
    text_c(d, 1700, "数据来源：PIX", font(FONT_MED, 34), GREY)
    return c


# ---------------- 6-1 / 6-2 VS 与对比表 ----------------

def taxi(d, cx, cy, s, col):
    d.polygon([(cx - 170 * s, cy + 40 * s), (cx - 120 * s, cy - 15 * s), (cx - 40 * s, cy - 65 * s),
               (cx + 75 * s, cy - 65 * s), (cx + 165 * s, cy), (cx + 175 * s, cy + 40 * s)], outline=col, width=6)
    for wx in (cx - 100 * s, cx + 100 * s):
        d.ellipse([wx - 40 * s, cy + 10 * s, wx + 40 * s, cy + 90 * s], outline=col, width=6)


def a61(age, dur):
    c = blank(225)
    grid(c, age, 16)
    d = ImageDraw.Draw(c)
    mid = W // 2
    p = ease_out(age / 0.5)
    d.line([(mid, 300), (mid, int(300 + 1200 * p))], fill=(255, 255, 255, 110), width=3)
    lx, rx = mid // 2, mid + mid // 2
    taxi(d, int(lerp(-300, lx, p)), 640, 1.15, (205, 215, 235))
    bus(d, int(lerp(W + 300, rx, p)), 660, 0.6, YELLOW)
    ft = font(FONT_BOLD, 56)
    for x, t1, t2, col in ((lx, "特斯拉", "Cybercab", WHITE), (rx, "PIX", "土豆巴士", YELLOW)):
        d.text((x - ft.getlength(t1) / 2, 860), t1, font=ft, fill=col)
        d.text((x - ft.getlength(t2) / 2, 935), t2, font=ft, fill=col)
    if age > 0.4:
        q = ease_back((age - 0.4) / 0.3)
        r = int(100 * max(q, 0.05))
        d.ellipse([mid - r, 640 - r, mid + r, 640 + r], fill=RED + (255,))
        fv = font(FONT_BLACK, int(110 * max(q, 0.05)))
        d.text((mid - fv.getlength("VS") / 2, 640 - 70 * q), "VS", font=fv, fill=WHITE)
    if age > 3.0:
        q = ease_out((age - 3.0) / 0.4)
        text_c(d, 1150, "都没有方向盘", font(FONT_BOLD, 56), WHITE + (int(255 * q),))
    if age > 5.0:
        q = ease_back((age - 5.0) / 0.35)
        text_c(d, 1260, "完全不同的赛道", font(FONT_BLACK, int(84 * max(q, 0.05))), YELLOW, stroke=6)
    return c


def a62(age, dur):
    c = blank(225)
    grid(c, age, 16)
    d = ImageDraw.Draw(c)
    rows = [("", "Cybercab", "土豆巴士"),
            ("定位", "Robotaxi", "商用移动空间"),
            ("形态", "代步工具", "上层空间可换"),
            ("商业化", "测试推进中", "已在中国盈利运营")]
    x0, x1, x2, x3 = 70, 290, 640, W - 70
    y0, rh = 520, 170
    for i, (a, b, cc) in enumerate(rows):
        st = i * 0.9
        if age < st:
            continue
        q = ease_out((age - st) / 0.4)
        y = y0 + i * rh
        fill = (4, 10, 22, int(220 * q)) if i else (0, 229, 255, int(60 * q))
        d.rectangle([x0, y, x3, y + rh - 14], fill=fill)
        f = font(FONT_BOLD, 46 if i else 50)
        d.text((x0 + 24, y + 50), a, font=f, fill=CYAN + (int(255 * q),))
        d.text((x1 + 20, y + 50), b, font=f, fill=WHITE + (int(255 * q),))
        d.text((x2 + 20, y + 50), cc, font=f, fill=YELLOW + (int(255 * q),))
    return c


# ---------------- 6-3 换道超车 ----------------

def a63(age, dur):
    c = blank(0)
    d = ImageDraw.Draw(c)
    y_top, y_bot = 1180, 1620
    lane_l, lane_r = 380, 700
    d.rounded_rectangle([200, y_top - 20, 880, y_bot + 20], 20, fill=(4, 10, 22, 200))
    off = int(age * 600) % 120
    for x in (240, 540, 840):
        for y in range(y_top - 120 + off, y_bot, 120):
            d.line([(x, max(y, y_top)), (x, min(y + 60, y_bot))], fill=(255, 255, 255, 160), width=6)
    # 对手车在左道匀速
    d.rounded_rectangle([lane_l - 50, 1420, lane_l + 50, 1560], 20, outline=GREY, width=6)
    # 我方车：从左道变到右道并超前
    k = ease_out((age - 0.6) / 1.2)
    x = lerp(lane_l, lane_r, k)
    y = lerp(1460, 1230, ease_out((age - 0.9) / 1.5))
    glow(c, lambda dd: dd.rounded_rectangle([x - 50, y, x + 50, y + 140], 20, outline=YELLOW, width=7))
    d = ImageDraw.Draw(c)
    if age > 1.8:
        q = ease_back((age - 1.8) / 0.35)
        text_c(d, 980, "换道超车", font(FONT_BLACK, int(150 * max(q, 0.05))), YELLOW, stroke=8)
    if age > 1.0:
        q = ease_out((age - 1.0) / 0.4)
        f = font(FONT_BOLD, 44)
        d.text((230, 260), "弯道超车", font=f, fill=(255, 255, 255, int(160 * q)))
        d.line([(230, 290), (230 + f.getlength("弯道超车") * q, 290)], fill=RED, width=6)
    return c


# ---------------- 6-5 结尾卡 ----------------

def a65(age, dur):
    c = blank(int(235 * ease_out(age / 0.4)))
    grid(c, age, 14)
    d = ImageDraw.Draw(c)
    q = ease_out(age / 0.6)
    glow(c, lambda dd: bus(dd, W // 2, 760, 0.95, YELLOW))
    d = ImageDraw.Draw(c)
    text_c(d, 1040, "土豆巴士", font(FONT_BLACK, 110), WHITE + (int(255 * q),))
    text_c(d, 1180, "PIX Moving", font(FONT_BOLD, 50), CYAN + (int(255 * q),))
    if age > 1.0:
        k = ease_back((age - 1.0) / 0.35)
        fb = font(FONT_BLACK, 56)
        txt = "+ 关注 老财科技观察"
        tw = fb.getlength(txt)
        bw = (tw + 100) * max(k, 0.05)
        d.rounded_rectangle([W / 2 - bw / 2, 1360, W / 2 + bw / 2, 1470], 55, fill=RED + (255,))
        if k > 0.7:
            d.text(((W - tw) / 2, 1382), txt, font=fb, fill=WHITE)
    if age > 1.6:
        k = ease_out((age - 1.6) / 0.4)
        text_c(d, 1530, "带你看懂中国科技", font(FONT_BOLD, 46), WHITE + (int(255 * k),))
    return c


# ---------------- 渲染 ----------------

# 镜号: (函数, 默认时长秒, 说明)
SPECS = {
    "a13": (a13, 4.0, "1-3 外媒标题墙，叠在美联社页面上"),
    "a14": (a14, 3.0, "1-4 外网炸了，叠在巴黎围观素材上"),
    "a15": (a15, 3.0, "1-5 线框扫描成型 + 标题，全屏"),
    "a21": (a21, 9.4, "2-1 海外爆火→火回国内时间线，底部渐变"),
    "a22": (a22, 8.0, "2-2 部件打叉 + 四国国旗 + 凭什么，叠在主播画面"),
    "a31": (a31, 3.0, "3-1 地球 + 贵阳，全屏"),
    "a35": (a35, 5.2, "3-5 地球多国飞线 + 数据卡，全屏"),
    "a41": (a41, 6.0, "4-1 车？划掉→移动空间，叠在主播画面"),
    "a42": (a42, 8.0, "4-2 X 光线框标注 + 上下分离，全屏"),
    "a43": (a43, 8.0, "4-3 数天→数小时 + 合作方角标，叠在设计/工厂素材上"),
    "a44": (a44, 16.0, "4-4 四场景卡片 01-04，叠在对应场景素材上"),
    "a45": (a45, 4.0, "4-5 能走/能赚钱/能百变，叠在主播画面"),
    "a51": (a51, 5.0, "5-1 NOT A CONCEPT 印章，叠在主播画面"),
    "a52": (a52, 7.0, "5-2 数据卡 ¥841，全屏"),
    "a53": (a53, 8.0, "5-3 数据卡 ¥2600+ 柱状对比，全屏"),
    "a61": (a61, 8.0, "6-1 Cybercab VS 土豆巴士，全屏"),
    "a62": (a62, 7.0, "6-2 对比表，全屏"),
    "a63": (a63, 12.0, "6-3 换道超车，叠在主播画面下半部"),
    "a65": (a65, 5.0, "6-5 结尾卡，全屏"),
}


def render(key):
    fn, dur, desc = SPECS[key]
    name = re.sub(r"[ /+?？→·]+", "_", desc.split(" ", 1)[1].split("，")[0]).strip("_")
    out = OUT / f"{key[1]}-{key[2]}_{name}.mov"
    n = int(dur * FPS)
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
           "-vendor", "apl0", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(fn(i / FPS, dur).tobytes())
    p.stdin.close()
    p.wait()
    return out


def preview(keys):
    """每个动画取 4 个时间点，放在灰底上拼成一行，检查用。"""
    rows = []
    for key in keys:
        fn, dur, _ = SPECS[key]
        cells = []
        for t in (dur * 0.15, dur * 0.4, dur * 0.7, dur * 0.97):
            bg = Image.new("RGBA", (W, H), (70, 75, 85, 255))
            bg.alpha_composite(fn(t, dur))
            cells.append(bg.convert("RGB").resize((216, 384)))
        row = Image.new("RGB", (216 * 4, 384))
        for i, im in enumerate(cells):
            row.paste(im, (i * 216, 0))
        rows.append(row)
    sheet = Image.new("RGB", (216 * 4 * 2, 384 * ((len(rows) + 1) // 2)), (0, 0, 0))
    for i, r in enumerate(rows):
        sheet.paste(r, ((i % 2) * 216 * 4, (i // 2) * 384))
    path = Path(__file__).parent / "anim_preview.jpg"
    sheet.save(path, quality=72)
    print(path)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--preview":
        preview(args[1:] or list(SPECS))
        return
    OUT.mkdir(exist_ok=True)
    for key in args or list(SPECS):
        print("完成", render(key).name, flush=True)


if __name__ == "__main__":
    main()
