#!/usr/bin/env python3
"""录音豆分镜草图生成：读取合并稿里的分镜表，每 8 个镜头拼一张工作板，
调用 GPT Image（/v1/images/edits，参考图为录音豆产品图）生成黑白火柴人分镜草图，
可选追加到飞书文档末尾。

调用方式沿用 <其他项目目录> 与 <其他项目目录> 的 GPT Image 图片编辑协议：
multipart，字段 model / prompt / n=1 / size / quality=high / output_format=png，原图字段 image。
密钥读取 <其他项目 openai.json>（或 --config 指定），不打印密钥。

用法：
  python3 gen_storyboard.py --dry-run            # 只打印每张板的提示词
  python3 gen_storyboard.py --boards 1           # 只生成第 1 张（先试风格）
  python3 gen_storyboard.py                      # 生成全部
  python3 gen_storyboard.py --upload --boards 1-7  # 已生成的板追加到飞书文档
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
SCRIPT_MD = ROOT / "录音豆_逐字稿与分镜稿_合并版.md"
REF_IMAGE = ROOT / "分镜草图" / "参考_录音豆.png"
OUT_DIR = ROOT / "分镜草图"
DEFAULT_CONFIG = Path.home() / "code/huxiao/config/openai.json"
DOC_ID = "MPgudl8FToZzp0xHTLucg5iTnlf"
PER_BOARD = 8
SIZE = "1536x1024"
TIMEOUT = 300

# 沿用土豆巴士已认可的分镜风格，并按本片（办公室工位坐姿口播 + 9:16 竖屏）调整
STYLE = (
    "生成一张分镜工作板：黑白灰火柴人草图风格，白底黑线，少量灰色铺影，手绘铅笔质感，不上彩色，不画写实人脸。"
    "整板16:9横版，两行四列八个等大面板，阅读顺序从左到右、从上到下。"
    "每格中央画一个虚线9:16竖向安全框（宽为高的0.5625），主体和必要文字都在框内，框外只画背景。"
    "每格底部有独立信息带，只写“镜号 / 景别 / 时长”，例如“1-1 / 中景 / 3s”。"
    "主播硬性要求：主播（即“老财”）用火柴人表示、不画具体相貌，在办公室工位上坐姿半身口播，桌沿或椅背必须可见，"
    "只画到胸口或腰部以上，无腿、无全身、无站姿、无起身、无走动，手势在胸前不高于肩膀，固定机位。"
    "A机位为正面中景，B机位为45度侧面近景。"
    "参考图是产品“录音豆”：圆角鹅卵石形小方块，比一元硬币略大，正面一个小孔和W标志，"
    "画面中出现录音豆时保持这个外形，用简洁线稿表示。旧产品“录音卡”是信用卡大小的薄卡片，和录音豆外形不同。"
    "“金句卡”“数据卡”只是剪辑术语，画面中不要写出这几个字。"
    "B-roll、App录屏、动画格用简化线框示意：手机录屏画手机外框加几行横线，动画画箭头与符号。"
    "画面中文字只用短词，不写长句，不新增文案事实，不画品牌名（录音豆、WorkBuddy除外）。"
)


def parse_shots(md: str):
    shots = []
    for line in md.splitlines():
        m = re.match(r"^\|\s*(\d-\d+)\s*\|\s*([\d:]+-[\d:]+)\s*\|(.*)\|\s*$", line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(3).split("|")]
        if len(cells) < 5:
            continue
        a, b = m.group(2).split("-")
        secs = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1])
        shots.append({
            "id": m.group(1), "dur": secs(b) - secs(a),
            "vo": cells[0], "pic": cells[1], "src": cells[2], "fx": cells[3],
        })
    return shots


def shot_scale(s):
    p = s["pic"]
    if "特写" in p or "推近到特写" in p:
        return "特写"
    if "近景" in p or "B 机位" in p:
        return "近景"
    if "录屏" in p or "App" in p or s["src"].startswith(("M2", "M3", "R10", "R15")):
        return "录屏"
    if s["src"].startswith("动画") or "符号" in p or "分屏" in p:
        return "动画"
    if "空镜" in p:
        return "全景"
    return "中景"


def board_prompt(idx, shots):
    lines = []
    for i, s in enumerate(shots, 1):
        lines.append(
            f"第{i}格「{s['id']} / {shot_scale(s)} / {s['dur']}s」：画面：{s['pic']}；"
            f"格内短字幕：{re.sub(r'(金句卡两行|金句卡|大字|数据卡|数据标注)：', '', s['fx'])}"
        )
    tail = ""
    if len(shots) < PER_BOARD:
        tail = f"本板只有{len(shots)}个镜头，剩余格子完全留空，只画浅灰斜线，底部信息带不写任何镜号。"
    return f"{STYLE}\n这是录音豆短视频分镜第{idx}板。\n" + "\n".join(lines) + "\n" + tail


def load_cfg(path):
    cfg = json.loads(Path(path).read_text())
    if not cfg.get("api_key"):
        sys.exit("配置中没有 api_key")
    return cfg


def edits_url(cfg):
    base = (cfg.get("base_url") or "https://api.openai.com").rstrip("/")
    return f"{base}/images/edits" if base.endswith("/v1") else f"{base}/v1/images/edits"


def generate(cfg, model, prompt, out):
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    if cfg.get("organization"):
        headers["OpenAI-Organization"] = cfg["organization"]
    data = {"model": model, "prompt": prompt, "n": "1", "size": SIZE,
            "quality": cfg.get("quality") or "high", "output_format": "png"}
    files = {"image": ("reference.png", REF_IMAGE.read_bytes(), "image/png")}
    t = time.time()
    res = httpx.post(edits_url(cfg), headers=headers, data=data, files=files,
                     timeout=TIMEOUT, trust_env=False)
    if res.status_code != 200:
        raise RuntimeError(f"HTTP {res.status_code}: {res.text[:500]}")
    d0 = res.json()["data"][0]
    if d0.get("b64_json"):
        out.write_bytes(base64.b64decode(d0["b64_json"]))
    else:
        out.write_bytes(httpx.get(d0["url"], timeout=120, trust_env=False).content)
    print(f"  已生成 {out.name}（{time.time() - t:.0f}s）")


def lark(*args):
    r = subprocess.run(["lark-cli", *args], capture_output=True, text=True)
    if r.returncode != 0 or '"ok": false' in r.stdout:
        raise RuntimeError(r.stdout + r.stderr)


def upload(boards, groups):
    lark("docs", "+update", "--doc", DOC_ID, "--command", "append", "--doc-format", "markdown",
         "--content", "## 七、分镜草图\n\n黑白火柴人草图，每板 8 格，格内虚线为 9:16 安全框；底部为镜号 / 景别 / 时长。由 GPT Image 生成，仅作构图参考。")
    for b in boards:
        f = OUT_DIR / f"录音豆_分镜_板{b}.png"
        g = groups[b - 1]
        cap = f"板{b}：镜头 {g[0]['id']} 至 {g[-1]['id']}"
        lark("docs", "+media-insert", "--doc", DOC_ID, "--file", str(f), "--caption", cap, "--align", "center")
        print(f"  已插入 {f.name}")


def parse_range(s, n):
    if not s:
        return list(range(1, n + 1))
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return [x for x in out if 1 <= x <= n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", help="如 1 或 1-3 或 2,5")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--model", help="默认取配置里的 model")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的板")
    ap.add_argument("--upload", action="store_true", help="把已生成的板追加到飞书文档")
    args = ap.parse_args()

    shots = parse_shots(SCRIPT_MD.read_text(encoding="utf-8"))
    groups = [shots[i:i + PER_BOARD] for i in range(0, len(shots), PER_BOARD)]
    boards = parse_range(args.boards, len(groups))
    print(f"共 {len(shots)} 个镜头，{len(groups)} 张板；本次处理板 {boards}")

    if args.upload:
        upload(boards, groups)
        return

    cfg = None if args.dry_run else load_cfg(args.config)
    for b in boards:
        prompt = board_prompt(b, groups[b - 1])
        (OUT_DIR / f"板{b}_提示词.txt").write_text(prompt, encoding="utf-8")
        if args.dry_run:
            print(f"--- 板{b}\n{prompt}\n")
            continue
        out = OUT_DIR / f"录音豆_分镜_板{b}.png"
        if out.exists() and not args.force:
            print(f"  跳过 {out.name}（已存在，用 --force 覆盖）")
            continue
        model = args.model or cfg.get("model") or "gpt-image-2"
        print(f"板{b}：调用 {model} ...")
        generate(cfg, model, prompt, out)


if __name__ == "__main__":
    main()
