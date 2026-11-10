"""批量转写土豆巴士素材音频：复用 meeting-asr 的上传与转写函数，不做归档。"""
import os
import asyncio
import sys
from pathlib import Path

backend_value = os.environ.get("MEETING_ASR_BACKEND")
if not backend_value:
    raise SystemExit("请设置 MEETING_ASR_BACKEND，指向已安装的 ASR 后端目录")
backend = Path(backend_value).expanduser().resolve()
if not (backend / "app").is_dir():
    raise SystemExit("MEETING_ASR_BACKEND 缺少 app 目录，请检查后端安装")
sys.path.insert(0, str(backend))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(backend / ".env")
from app import pipeline  # noqa: E402


async def one(f: Path, out_dir: Path):
    url = await asyncio.to_thread(pipeline.upload_to_oss, f)
    task_id = await pipeline.submit_transcription(url)
    data = await pipeline.poll_transcription(task_id)
    text = pipeline.format_transcript(data)
    (out_dir / f"{f.stem}.txt").write_text(text, encoding="utf-8")
    print(f"OK {f.name} {len(text)} chars", flush=True)


async def main():
    src, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(exist_ok=True)
    files = sorted(src.glob("*.mp3"))
    results = await asyncio.gather(*(one(f, out_dir) for f in files), return_exceptions=True)
    for f, r in zip(files, results):
        if isinstance(r, Exception):
            print(f"FAIL {f.name}: {r}")


asyncio.run(main())
