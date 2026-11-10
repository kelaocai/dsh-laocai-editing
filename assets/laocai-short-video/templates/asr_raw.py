"""阿里云整段转写，取准确文字（不带逐字时间）。必须在 MEETING_ASR_BACKEND 指定的目录 下用它的 .venv 运行。
用法：python asr_raw.py <音频> <输出json>"""
import os
import asyncio, json, sys
from pathlib import Path
backend_value = os.environ.get("MEETING_ASR_BACKEND")
if not backend_value:
    raise SystemExit("请设置 MEETING_ASR_BACKEND，指向已安装的 ASR 后端目录")
backend = Path(backend_value).expanduser().resolve()
if not (backend / "app").is_dir():
    raise SystemExit("MEETING_ASR_BACKEND 缺少 app 目录，请检查后端安装")
sys.path.insert(0, str(backend))
from dotenv import load_dotenv
load_dotenv(backend / ".env")
from app import pipeline
async def main():
    f = Path(sys.argv[1])
    url = await asyncio.to_thread(pipeline.upload_to_oss, f)
    tid = await pipeline.submit_transcription(url)
    data = await pipeline.poll_transcription(tid)
    Path(sys.argv[2]).write_text(json.dumps(data, ensure_ascii=False, indent=1))
asyncio.run(main())
