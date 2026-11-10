"""千问看图基准：题目来自土豆巴士项目里 Claude 亲自看图确认过的判断，以及场景检测给出的切点（同镜头判断）。

python3 bench.py qwen3.8-flash qwen3.8-27b ...   → 打印每个模型的正确率、漏检/误报、token、耗时，明细写 bench_<模型>.json
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

for tool_root in [Path.home() / ".codex/tools", Path.home() / ".claude/tools"]:
    if (tool_root / "vlook.py").is_file():
        sys.path.insert(0, str(tool_root))
        break
else:
    raise FileNotFoundError("未找到本机 vlook.py；先安装视觉辅助工具，技能仓库不包含密钥环境")
from vlook import ask  # noqa: E402

R = "<项目素材目录>"
SW = f"{R}/瑞士 人声放大.mp4"
AP = f"{R}/美联社报道.mov"
AWS = f"{R}/Robobus海外运营案例/AWS采访视频（英文版）.mp4"
KTV = f"{R}/ktv车上线.mp4"
P3D = f"{R}/3D打印+NEV.mp4"
DE = f"{R}/新建文件夹德国公开道路载客/德国素材片段.mp4"
HOST = f"{R}/土豆巴士-第二版.mp4"
FIN = f"{R}/土豆巴士_第二版_成片_v2_上传版.mp4"
APC = "crop=2532:1420:528:252"
BUS = "画面里能看到一台方盒子造型的无人驾驶小巴（没有车头，像一个带轮子的胶囊舱）吗？"
SAME = "这两张图是同一个连续镜头里相隔零点几秒的两帧吗（同一机位同一场景、没有发生剪切）？"

# (类别, 帧列表, 问题, 标准答案, crop)  答案：yes / no，或 ("contains", 关键文字)
ITEMS = [
    # 素材内容研判：选 B-roll 时最常问的
    ("内容", [(SW, 24.5)], BUS, "yes", None),
    ("内容", [(SW, 15.9)], BUS, "yes", None),
    ("内容", [(SW, 5.5)], BUS, "no", None),
    ("内容", [(SW, 8.8)], BUS, "no", None),          # 有轨电车，易误判
    ("内容", [(SW, 4.0)], BUS, "no", None),
    ("内容", [(SW, 21.5)], "这是一个发布会或论坛现场（台上有人讲话、台下有观众）吗？", "yes", None),
    ("内容", [(SW, 18.5)], "这是一个发布会或论坛现场（台上有人讲话、台下有观众）吗？", "yes", None),
    ("内容", [(SW, 24.5)], "这是一个发布会或论坛现场（台上有人讲话、台下有观众）吗？", "no", None),
    ("内容", [(KTV, 43.5)], "画面里有人拿着话筒唱歌吗？", "yes", None),
    ("内容", [(KTV, 40.5)], "画面里有人拿着话筒唱歌吗？", "no", None),
    ("内容", [(KTV, 37.5)], "画面里有人手里拿着话筒吗？", "yes", None),  # 原标准答错：Claude 看 160px 缩略图漏看了话筒，max 纠正
    ("内容", [(KTV, 40.5)], "画面是在车厢内部拍的吗？", "yes", None),
    ("内容", [(AP, 77)], "画面里是饮品或食物制作/出售的设备吗（例如自动出杯、咖啡机）？", "yes", APC),
    ("内容", [(AP, 20)], "画面里是饮品或食物制作/出售的设备吗（例如自动出杯、咖啡机）？", "no", APC),
    ("内容", [(AP, 20)], "这是一个摆着沙发、桌子的休息舱或会客空间内景吗？", "yes", APC),
    ("内容", [(AP, 77)], "这是一个摆着沙发、桌子的休息舱或会客空间内景吗？", "no", APC),
    ("内容", [(AWS, 19)], "这是一个摆着沙发、桌子的休息舱或会客空间内景吗？", "yes", None),
    ("内容", [(P3D, 17)], "画面里有工业机器人或机械臂在工作吗？", "yes", None),
    ("内容", [(P3D, 30)], "画面里有工业机器人或机械臂在工作吗？", "no", None),
    ("内容", [(P3D, 32.5)], "画面主体是一个品牌 logo 或片尾标版吗？", "yes", None),
    ("内容", [(P3D, 20.5)], "画面主体是一个品牌 logo 或片尾标版吗？", "no", None),
    ("内容", [(DE, 149.5)], "画面里有穿西装的人正在上车或站在车门口吗？", "yes", None),
    ("内容", [(SW, 24.5)], "画面里有穿西装的人正在上车或站在车门口吗？", "no", None),
    # 文字识别
    ("文字", [(P3D, 24)], "画面里的英文字是什么？照原样写出。", ("contains", "chassis"), None),
    ("文字", [(P3D, 26.5)], "画面底部的英文字是什么？照原样写出。", ("contains", "stable"), None),
    ("文字", [(AWS, 19)], "画面里的英文字幕是什么？照原样写出。", ("contains", "moving spaces"), None),
    ("文字", [(DE, 152.8)], "画面左侧牌子上的英文字母是什么？", ("contains", "nex"), None),
    ("文字", [(P3D, 32.5)], "画面中央 logo 下方的小字是什么？", ("contains", "robo-ev"), None),
    ("文字", [(FIN, 43.5)], "画面左上角青色竖条旁边的角标文字是什么？照原样写出。", ("contains", "瑞士"), None),
    ("文字", [(FIN, 84.1)], "画面左上角青色竖条旁边的角标文字是什么？照原样写出。", ("contains", "餐车"), None),
    # 成片检查
    ("成片", [(FIN, 89.6)], "画面底部的大号字幕有没有遮挡人物的脸（眼睛、鼻子、嘴）？", "no", None),
    ("成片", [(FIN, 20.0)], "画面底部的大号字幕有没有遮挡人物的脸（眼睛、鼻子、嘴）？", "no", None),
    ("成片", [(FIN, 82.8)], "画面里的人物活动和'移动 KTV'这个说法对得上吗？", "yes", None),
    ("成片", [(FIN, 84.1)], "画面内容和'移动 KTV'这个说法对得上吗？", "no", None),
    # 同镜头判断（找闪帧、跳切用），答案来自场景检测切点
    ("同镜头", [(SW, 23.40), (SW, 23.70)], SAME, "no", None),
    ("同镜头", [(SW, 24.00), (SW, 24.60)], SAME, "yes", None),
    ("同镜头", [(KTV, 39.30), (KTV, 39.60)], SAME, "no", None),
    ("同镜头", [(KTV, 37.00), (KTV, 37.80)], SAME, "yes", None),
    ("同镜头", [(SW, 7.60), (SW, 7.95)], SAME, "no", None),
    ("同镜头", [(HOST, 67.60), (HOST, 67.85)], SAME, "no", None),   # 主播原片跳切：同场景同人，最难
    ("同镜头", [(HOST, 60.00), (HOST, 60.40)], SAME, "yes", None),
    ("同镜头", [(DE, 151.70), (DE, 152.10)], SAME, "no", None),
]


def grade(ans, gold):
    a = str(ans.get("answer", "")).strip().lower()
    if isinstance(gold, tuple):
        return gold[1].lower() in a
    return a.startswith(gold)


def run(model):
    def one(it):
        cat, frames, q, gold, crop = it
        r = ask(frames, q, model=model, crop=crop)
        return {"cat": cat, "q": q, "frames": frames, "gold": gold, "res": r,
                "ok": "error" not in r and grade(r, gold)}
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(one, ITEMS))
    Path(__file__).with_name(f"bench_{model}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    errs = [r for r in rows if "error" in r["res"]]
    if errs:
        print(f"{model}: {len(errs)} 题报错，例：{errs[0]['res']['error'][:160]}")
        if len(errs) == len(rows):
            return
    ok = sum(r["ok"] for r in rows)
    yn = [r for r in rows if r["gold"] in ("yes", "no")]
    miss = sum(1 for r in yn if r["gold"] == "yes" and not r["ok"])
    fa = sum(1 for r in yn if r["gold"] == "no" and not r["ok"])
    tin = sum((r["res"].get("tokens") or {}).get("in") or 0 for r in rows)
    tout = sum((r["res"].get("tokens") or {}).get("out") or 0 for r in rows)
    sec = sum(r["res"].get("sec", 0) for r in rows) / len(rows)
    cats = {}
    for r in rows:
        c = cats.setdefault(r["cat"], [0, 0])
        c[0] += r["ok"]
        c[1] += 1
    print(f"{model}: 正确 {ok}/{len(rows)}  漏检 {miss}/{sum(r['gold'] == 'yes' for r in yn)}  "
          f"误报 {fa}/{sum(r['gold'] == 'no' for r in yn)}  token 入 {tin} 出 {tout}  平均 {sec:.1f}s/题  "
          + "  ".join(f"{k} {v[0]}/{v[1]}" for k, v in cats.items()))
    for r in rows:
        if not r["ok"] and "error" not in r["res"]:
            print(f"   错：[{r['cat']}] {Path(r['frames'][0][0]).stem}@{r['frames'][0][1]} {r['q'][:24]} "
                  f"标准 {r['gold']} 回答 {r['res'].get('answer')}（{r['res'].get('detail', '')[:50]}）")


if __name__ == "__main__":
    for m in sys.argv[1:]:
        run(m)
