# dsh-laocai-editing · 老财剪辑

[![license](https://img.shields.io/npm/l/dsh-laocai-editing.svg)](LICENSE)

**老财（老财科技观察）本地剪辑与字幕技能包**，以 DeepSeek Harness「随包技能（bundled skill）」插件的形式交付：安装后，四个技能会作为可加载的 `skill` 出现在会话目录里，模型按需用 `skill` 工具加载正文，脚本、模板与参考文件通过随包的资源目录解析。

技能正文只提供方法，不赋予执行工具。执行剪辑任务的角色需自行具备读取本地文件、运行终端命令、访问素材与输出目录的能力。

## 包含的技能

| 技能 | 用途 | 字幕能力 |
|---|---|---|
| `laocai-short-video` | 主播口播、B-roll、包装、成片与 FCP 协作 | 校稿、逐字对齐、逐字弹入、关键词动效、字幕安全区 |
| `dialogue-short-film-editing` | 多人对白、剧情短片、局部返修 | 台词与气口核对、避免重复烧字、人物标签与字幕检查 |
| `video-material-brief` | 素材盘点、抽音轨、人声检测、转写、分镜脚本 | 提供准确台词底稿 |
| `tencent-mps` | 腾讯云媒体处理（第三方，MIT） | 语音识别、字幕提取、翻译、SRT、字幕擦除 |

加字幕首选 `laocai-short-video`；剧情剪辑配套 `dialogue-short-film-editing`；前期转写配套 `video-material-brief`；腾讯 MPS 为可选云端能力（会产生云费用，触发前需用户确认）。

## 安装

### 方式一：市场索引（推荐，一键安装）

1. 在 DSH「插件」页启用实验插件 **自定义插件索引**（`@deepseek-ai/dsh-experimental-plugin-market-bundle`）。
2. 打开「发现」页 → **添加索引源**，粘贴：

```text
https://cdn.jsdelivr.net/gh/kelaocai/dsh-laocai-editing@main/market/index.json
```

（备用：`https://raw.githubusercontent.com/kelaocai/dsh-laocai-editing/main/market/index.json`）

3. 搜索 `dsh-laocai-editing`（老财剪辑），点击安装。

### 方式二：从 GitHub 仓库安装

```bash
dsh plugin add git+https://github.com/kelaocai/dsh-laocai-editing.git
```

随后在「插件」页启用 `dsh-laocai-editing` 这个 bundle。

### 方式三：npm

```bash
dsh plugin add dsh-laocai-editing
```

npm 包地址：<https://www.npmjs.com/package/dsh-laocai-editing>

> 需要支持 skills 子系统（`ctx.skills`）的 DeepSeek Harness 版本；本插件沿用了官方 `dsh-skill-office` 的随包技能提供方模式。

## 安装后

- 启用插件后，会话目录里会出现 `laocai-short-video`、`dialogue-short-film-editing`、`video-material-brief`、`tencent-mps` 四个技能；模型在需要时自动加载，也可用 `/技能名` 手动调用。
- 技能内的 `references/`、`templates/`、`scripts/` 相对引用，由 DSH 注入的 `<skill_resources>` 资源目录解析，无需配置任何本机绝对路径。
- 建议先绑定 `laocai-short-video` 与 `dialogue-short-film-editing`，需要前期转写再绑定 `video-material-brief`；腾讯 MPS 按需绑定，避免宽泛触发规则与本地流程冲突。

## 首次验收建议

用一段 10–20 秒、含中文、人名、数字和停顿的已授权素材，在独立 work 目录完成校稿、对齐和字幕预览，核对最终文件、时间同步、换行、安全区、字体和音轨后，再做整片。不以「插件已安装」代替执行成功。

## 依赖与限制

- 基础：FFmpeg、ffprobe、Python、Pillow、NumPy；具体 FFmpeg 滤镜能力现场检查。
- 本地 ASR：faster-whisper 及本地模型；或本机 meeting-asr 后端（阿里云转写，依赖已有后端与账号环境，本包不含）。
- 逐字对齐：torch、torchaudio、qwen-asr、transformers，对齐模型约 1.8GB（默认读取本地模型目录）；国内镜像/ModelScope 优先，禁止走计费代理。
- 字体文件未随包分发，需检查本机已安装字体并调整 `render.py` 的字体路径。
- 烧录字幕是视频像素，需要 SRT 或 FCP 原生文字编辑时另做对应导出。

## 占位符与隐私

技能正文里的本机绝对路径与示例素材路径，打包时已替换为 `<...>` 占位符（`<项目素材目录>`、`<meeting-asr 后端目录>`、`<本技能资源目录>`、`<系统字体目录>`、`<本地模型目录>`、`<外部视觉工具…（本包不含）>` 等）。使用时按实际环境填写，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可

- 本插件代码：MIT（见 [LICENSE](LICENSE)）。
- `tencent-mps`：第三方技能，MIT，保留原作者版权与来源说明（见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 `assets/tencent-mps/LICENSE.txt`）。
