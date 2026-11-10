"""阿里云整段转写，取准确文字（不带逐字时间）。必须在 <meeting-asr 后端目录> 下用它的 .venv 运行。
用法：python asr_raw.py <音频> <输出json>"""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, "<meeting-asr 后端目录>")
from dotenv import load_dotenv
load_dotenv("<meeting-asr 后端目录>/.env")
from app import pipeline
async def main():
    f = Path(sys.argv[1])
    url = await asyncio.to_thread(pipeline.upload_to_oss, f)
    tid = await pipeline.submit_transcription(url)
    data = await pipeline.poll_transcription(tid)
    Path(sys.argv[2]).write_text(json.dumps(data, ensure_ascii=False, indent=1))
asyncio.run(main())
