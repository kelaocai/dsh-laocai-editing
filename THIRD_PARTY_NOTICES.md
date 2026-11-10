# 第三方声明与来源

## tencent-mps

本插件包含第三方技能 `tencent-mps`（腾讯云媒体处理服务），来源为 DSH 插件生态（Plugin Hub）。

- 原来源元数据（`assets/tencent-mps/_meta.json`）：`ownerId: 528707`、`slug: tencent-mps`、`version: 1.3.0`。
- 许可证：MIT（见 `assets/tencent-mps/LICENSE.txt`，保留原作者版权声明）。
- 用途：音视频与图片处理、AI 生成、内容理解等云端能力，作为剪辑与字幕流程的可选云端配套。

> 依据 MIT 许可，允许复制、使用、修改、合并、发布、分发、再许可与销售，前提是保留上述版权声明与许可声明。本插件的再分发不改变 tencent-mps 的原作者身份，也不把该第三方技能声明为老财自建。

## 自建技能

以下三个技能为 kelaocai 本地创建/维护：

- `laocai-short-video`（老财短视频成片）
- `dialogue-short-film-editing`（剧情对白短片剪辑）
- `video-material-brief`（视频素材梳理）

## 路径便携性

技能正文、模板与参考均不记录个人绝对路径。本机/项目相关路径由执行环境通过环境变量提供，不写回技能源：

| 配置 | 用途 |
|---|---|
| `VIDEO_PROJECT_DIR` | 当前工程与素材根目录；项目模板必填 |
| `MEETING_ASR_BACKEND` | 可选 ASR 后端目录；仅使用该适配器时必填 |
| `VIDEO_FONT_BOLD` / `VIDEO_FONT_BLACK` / `VIDEO_FONT_MED` | 三种字体角色的实际文件路径 |
| `VIDEO_TOOLS_DIR` | 可选视觉辅助工具目录（`$TOOLS`） |
| `PYTHON_BIN` | 对齐安装脚本使用的解释器；默认从 PATH 查找 python3.12 |
| `--config` | 分镜示例生成图片服务配置；实际生成时必须指定 |

技能内的相对资源（`references/`、`templates/`、`scripts/`）由 DSH 注入的 `<skill_resources>` 资源目录解析；正文中出现的 `~/models/`（对齐模型缓存）、`~/Library/Fonts/`（系统字体目录）、`~/.env` / `~/.profile` / `~/.bashrc`（通用 shell 配置）等为系统通用目录，不含个人标识。
