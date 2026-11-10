"""批量转写土豆巴士素材音频：复用 meeting-asr 的上传与转写函数，不做归档。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "<meeting-asr 后端目录>")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("<meeting-asr 后端目录>/.env")
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
