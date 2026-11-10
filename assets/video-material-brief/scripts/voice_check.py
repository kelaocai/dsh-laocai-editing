"""本地判断音频是否含人声，决定要不要送阿里云转写。

用法：fw/bin/python -I voice_check.py <音频目录或文件...>
分类：
  有人声   清晰语音，送阿里云
  少量人声 只有零星几句，看预览文字自行决定
  存疑     语音检测为 0，但 whisper 硬转出了内容，多为人声被背景音乐盖住，建议送阿里云
  无人声   纯音乐或环境声，跳过
"""
import re
import sys
from pathlib import Path

from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps

SR = 16000
# 直接用本地缓存的模型目录，不联网（避免走按流量计费的代理）
MODEL_DIR = next(Path.home().glob(".cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/*"))
MODEL = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
# whisper 在纯音乐上常输出的占位文字和幻听套话
MUSIC_TAGS = re.compile(
    r"^[\s\W]*(music|音乐|applause|掌声|you|thank you|thanks for watching|thank you for watching"
    r"|please subscribe|字幕|请不吝点赞|谢谢观看|\d+)?[\s\W]*$",
    re.I,
)


def check(path: Path) -> dict:
    audio = decode_audio(str(path), sampling_rate=SR)
    total = len(audio) / SR
    vad = get_speech_timestamps(audio, VadOptions(threshold=0.3, min_speech_duration_ms=300))
    vad_sec = sum(s["end"] - s["start"] for s in vad) / SR

    segments, info = MODEL.transcribe(audio, vad_filter=True, vad_parameters={"threshold": 0.3},
                                      beam_size=1, temperature=0)
    # 音乐上 whisper 易"幻听"，用两个置信度把假字幕过滤掉
    kept = [
        s for s in segments
        if s.no_speech_prob < 0.6 and s.avg_logprob > -1.0 and s.text.strip()
    ]
    speech_sec = sum(s.end - s.start for s in kept)
    text = " ".join(s.text.strip() for s in kept)

    if speech_sec >= 10 or speech_sec / total >= 0.2:
        label = "有人声"
    elif speech_sec >= 2:
        label = "少量人声"
    else:
        # 第二遍：关掉 VAD 硬转，纯音乐只会得到空或 "Music"。
        # 只抽首、中、尾 3 个 30 秒窗口，避免长片在幻听循环里耗时
        win = 30 * SR
        starts = sorted({0, max(0, len(audio) // 2 - win // 2), max(0, len(audio) - win)})
        hit_sec = 0.0
        for st in starts:
            # temperature=0：关掉随机温度重试，否则同一段音频每次结果不同
            raw, _ = MODEL.transcribe(audio[st:st + win], vad_filter=False, beam_size=1, temperature=0,
                                      condition_on_previous_text=False, without_timestamps=True)
            # 幻听套话的 avg_logprob 通常低于 -1.4，真实人声在 -1.0 附近或更高
            hit_sec += sum(s.end - s.start for s in raw
                           if s.no_speech_prob < 0.5 and s.avg_logprob > -1.4
                           and not MUSIC_TAGS.match(s.text))
        label = "存疑" if hit_sec >= 10 else "无人声"
    return {
        "file": path.name, "total": total, "vad": vad_sec, "speech": speech_sec,
        "lang": info.language, "label": label, "text": text[:80],
    }


def main():
    files = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        files += sorted(p.glob("*.mp3")) if p.is_dir() else [p]
    for f in files:
        r = check(f)
        print(f"{r['label']:<5} | {r['file']} | 时长 {r['total']:.0f}s | VAD {r['vad']:.0f}s "
              f"| 可信语音 {r['speech']:.0f}s | {r['lang']} | {r['text']}", flush=True)


main()
