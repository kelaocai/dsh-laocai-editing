"""成片自动质检：能用代码判断的不看图。

用法：python qc.py <成片.mp4> [预期时长秒]
输出一份文字报告，有问题的行以 [!] 开头。
"""
import json
import re
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,width,height,r_frame_rate,bit_rate,sample_rate:format=duration,size",
             "-of", "json", path])
    return json.loads(r.stdout)


def main():
    print("[人工必查] 自动 QC 不检查文字安全区/遮罩。按 references/safe-area.md 复核最终导出：安全框、字幕与小字净距、底板透底、切点及花字动画。未完成不得判定视觉 QC 通过。")
    path = sys.argv[1]
    expect = float(sys.argv[2]) if len(sys.argv) > 2 else None
    bad = 0

    def line(ok, text):
        nonlocal bad
        bad += not ok
        print(("    " if ok else "[!] ") + text)

    info = probe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    fps = eval(v["r_frame_rate"])
    vbr = int(v.get("bit_rate", 0)) / 1e6
    line(v["width"] == 1080 and v["height"] == 1920, f"分辨率 {v['width']}x{v['height']}（应为 1080x1920）")
    line(abs(fps - 30) < 0.01, f"帧率 {fps:g}（应为 30）")
    line(vbr >= 8, f"视频码率 {vbr:.1f} Mbps（上传版应 ≥ 8）")
    line(a is not None and a.get("sample_rate") == "48000", f"音频采样率 {a.get('sample_rate') if a else '无音轨'}（应为 48000）")
    if expect:
        line(abs(dur - expect) < 0.1, f"时长 {dur:.2f}s（预期 {expect:.2f}s）")
    else:
        print(f"    时长 {dur:.2f}s")

    # 黑屏（排除片尾 0.6 秒淡出）
    r = run(["ffmpeg", "-nostdin", "-v", "info", "-i", path, "-vf", "blackdetect=d=0.15:pix_th=0.06", "-an", "-f", "null", "-"])
    blacks = [(float(s), float(e)) for s, e in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)]
    blacks = [b for b in blacks if b[0] < dur - 0.6]
    line(not blacks, f"黑屏段 {len(blacks)} 处" + (f"：{blacks[:5]}" if blacks else ""))

    # 冻帧（画面 ≥1 秒完全不动；数据卡、结尾卡可能是合理的静止，只提示）
    r = run(["ffmpeg", "-nostdin", "-v", "info", "-i", path, "-vf", "freezedetect=n=0.001:d=1.0", "-an", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
    print(f"    冻帧 ≥1s：{len(starts)} 处 {[round(x, 1) for x in starts[:8]]}（静止的动画卡片属正常，其余需人工看）")

    # 最后一帧是否可解码、是否异常（马赛克多表现为解码报错或最后帧缺失）
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-sseof", "-0.1", "-i", path, "-f", "null", "-"])
    line(not r.stderr.strip(), "片尾解码" + ("正常" if not r.stderr.strip() else f"报错：{r.stderr.strip()[:120]}"))
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-map", "0:v", "-f", "null", "-"])
    line(not r.stderr.strip(), "全片解码" + ("无错误" if not r.stderr.strip() else f"报错：{r.stderr.strip()[:120]}"))

    # 响度与峰值
    if a:
        r = run(["ffmpeg", "-nostdin", "-hide_banner", "-i", path, "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"])
        i_lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
        peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)[-1])
        line(-15.5 <= i_lufs <= -13, f"响度 {i_lufs} LUFS（应在 -14 左右）")
        line(peak <= -0.5, f"真峰值 {peak} dBFS（应 ≤ -1，防削顶）")
        r = run(["ffmpeg", "-nostdin", "-v", "info", "-i", path, "-af", "silencedetect=n=-45dB:d=1.5", "-vn", "-f", "null", "-"])
        sil = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
        sil = [s for s in sil if s < dur - 1.5]
        line(not sil, f"长静音（>1.5s）{len(sil)} 处 {[round(s, 1) for s in sil[:5]]}")

    print(f"\n结论：{'全部通过' if not bad else f'{bad} 项需要处理'}")


if __name__ == "__main__":
    main()
