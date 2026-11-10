"""第二版原创配乐：120 BPM 电子节奏底乐，按剪辑段落编排，关键台词处放冲击音。完全代码合成，无版权问题。

python bgm2.py → bgm2.wav（48kHz 立体声）
"""
import wave
from pathlib import Path

import numpy as np

SR = 48000
BPM = 120
BEAT = 60 / BPM
TOTAL = 135.33
N = int(TOTAL * SR)
rng = np.random.default_rng(7)

# 卡点（秒），来自强制对齐
T_BOOM1 = 11.52      # 外网已经炸了
T_TITLE = 12.87      # 标题动画
T_GROOVE = 14.97     # 主播入场，主节奏进
T_DATA = 98.73       # 数据卡段，加拍手
T_DATA_END = 105.67
T_RISE = 123.83      # 换道超车前的上升
T_BOOM2 = 125.36     # 是换道超车
T_OUTRO = 133.43     # 结尾卡

L = np.zeros(N)
R = np.zeros(N)


def add(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * (1 - max(pan, 0))
    R[i:i + len(sig)] += sig * (1 + min(pan, 0))


def env(n, a, d):
    e = np.ones(n)
    na, nd = int(a * SR), int(d * SR)
    e[:na] = np.linspace(0, 1, na) if na else 1
    if nd:
        e[-nd:] *= np.linspace(1, 0, nd)
    return e


def kick():
    t = np.arange(int(0.35 * SR)) / SR
    f = 50 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def hat(open_=False):
    n = int((0.18 if open_ else 0.045) * SR)
    x = rng.standard_normal(n)
    x = np.diff(x, prepend=0)  # 简单高通
    return x * np.exp(-np.arange(n) / SR * (14 if open_ else 70)) * 0.35


def clap():
    n = int(0.22 * SR)
    x = rng.standard_normal(n)
    e = np.exp(-np.arange(n) / SR * 22)
    for k in (0.01, 0.02):  # 多次起音
        e[int(k * SR):] += np.exp(-np.arange(n - int(k * SR)) / SR * 30) * 0.6
    return x * e * 0.3


def boom():
    t = np.arange(int(2.2 * SR)) / SR
    f = 38 + 90 * np.exp(-t * 6)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    noise = rng.standard_normal(len(t)) * np.exp(-t * 5) * 0.25
    return (sub + noise) * 1.2


def riser(dur):
    t = np.arange(int(dur * SR)) / SR
    x = rng.standard_normal(len(t))
    k = np.linspace(0, 1, len(t))
    sweep = np.sin(2 * np.pi * np.cumsum(200 + 1800 * k ** 2) / SR) * 0.3
    return (x * 0.25 + sweep) * k ** 2


def saw(freq, dur, detune=0.0):
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(t)
    for d in (-detune, 0, detune):
        ph = (t * freq * (1 + d)) % 1.0
        out += 2 * ph - 1
    return out / 3


def lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # 一阶低通，pad 只调用少数几次，速度可接受
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


# 和弦进行：Am - F - C - G，每个和弦 2 小节（4 秒）
CHORDS = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
ROOTS = [45, 41, 36, 43]


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def chord_at(t):
    return int((t // (8 * BEAT)) % 4)


def pad_block(t0, dur, level):
    for c in range(int(np.ceil(dur / (8 * BEAT)))):
        tc = t0 + c * 8 * BEAT
        seg = min(8 * BEAT, t0 + dur - tc)
        if seg <= 0:
            break
        ci = chord_at(tc)
        x = sum(saw(midi(m), seg, 0.004) for m in CHORDS[ci]) / 3
        x = lowpass(x, 0.035) * env(len(x), 0.4, 0.4)
        add(x, tc, level, -0.3)
        add(x, tc + 0.012, level, 0.3)  # 轻微立体声展开


def bass_line(t0, t1, level):
    t = t0
    while t < t1:
        ci = chord_at(t)
        n = saw(midi(ROOTS[ci]), BEAT / 2 * 0.9)
        n = lowpass(n, 0.08) * env(len(n), 0.005, 0.05)
        add(n, t + BEAT / 2, level)  # 反拍贝斯
        t += BEAT


def drums(t0, t1, kick_on=True, hats=True, claps=False, hat_div=2):
    t = t0
    step = BEAT / hat_div
    k = 0
    while t < t1:
        if kick_on and k % hat_div == 0:
            add(kick(), t, 0.9)
        if hats:
            add(hat(open_=(k % (hat_div * 2) == hat_div)), t, 0.6, 0.25)
        if claps and k % (hat_div * 2) == hat_div:
            add(clap(), t, 0.8)
        t += step
        k += 1


def arp(t0, t1, level):
    t, k = t0, 0
    while t < t1:
        ci = chord_at(t)
        m = CHORDS[ci][k % 3] + 12
        tt = np.arange(int(BEAT / 2 * SR)) / SR
        n = np.sin(2 * np.pi * midi(m) * tt) * np.exp(-tt * 9)
        add(n, t, level, 0.4 if k % 2 else -0.4)
        t += BEAT / 2
        k += 1


def build():
    # 前奏：紧张感，十六分音符踩镲 + 贝斯 + 铺底
    pad_block(0, T_BOOM1, 0.20)
    drums(0, T_BOOM1 - 0.1, kick_on=False, hats=True, hat_div=4)
    bass_line(2 * BEAT * 4, T_BOOM1 - 0.1, 0.30)
    add(riser(2.5), T_BOOM1 - 2.5, 0.35)
    add(boom(), T_BOOM1, 0.9)
    # 标题：留白 + 铺底
    pad_block(T_TITLE, T_GROOVE - T_TITLE + 0.5, 0.16)
    # 主节奏
    pad_block(T_GROOVE, T_RISE - T_GROOVE, 0.13)
    bass_line(T_GROOVE, T_RISE, 0.28)
    drums(T_GROOVE, T_DATA, kick_on=True, hats=True)
    arp(T_GROOVE + 16 * BEAT, T_DATA, 0.08)
    # 数据段：加拍手，能量最高
    drums(T_DATA, T_DATA_END, kick_on=True, hats=True, claps=True)
    arp(T_DATA, T_DATA_END, 0.10)
    drums(T_DATA_END, T_RISE, kick_on=True, hats=True)
    # 换道超车：鼓停，上升，冲击
    add(riser(T_BOOM2 - T_RISE), T_RISE, 0.4)
    pad_block(T_RISE, T_BOOM2 - T_RISE, 0.12)
    add(boom(), T_BOOM2, 0.9)
    # 收尾
    pad_block(T_BOOM2, TOTAL - T_BOOM2, 0.15)
    bass_line(T_BOOM2 + 0.5, T_OUTRO, 0.25)
    drums(T_BOOM2 + 0.5, T_OUTRO, kick_on=True, hats=True)
    arp(T_OUTRO, TOTAL, 0.08)


def main():
    build()
    st = np.stack([L, R], axis=1)
    st /= np.max(np.abs(st)) + 1e-9
    st *= 0.9
    fade = int(1.2 * SR)
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    pcm = (st * 32767).astype(np.int16)
    with wave.open(str(Path(__file__).parent / "bgm2.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("bgm2.wav", TOTAL, "秒")


if __name__ == "__main__":
    main()
