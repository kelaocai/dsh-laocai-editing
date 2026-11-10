"""本地 faster-whisper 逐字时间戳。用法：python words.py <音频> <输出json> [提示词]
第三个参数填专有名词，能明显减少错字。"""
import json, sys
from pathlib import Path
from faster_whisper import WhisperModel
d = next(Path.home().glob(".cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/*"))
m = WhisperModel(str(d), device="cpu", compute_type="int8")
segs, _ = m.transcribe(sys.argv[1], language="zh", word_timestamps=True, beam_size=5, temperature=0,
                       initial_prompt=sys.argv[3] if len(sys.argv) > 3 else None)
out = []
for s in segs:
    out.append({"start": s.start, "end": s.end, "text": s.text,
                "words": [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2)} for w in s.words]})
    print(f"{s.start:6.2f}-{s.end:6.2f} {s.text}", flush=True)
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False))
