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

## 占位符说明

技能正文中的本机绝对路径与示例素材路径，在打包时已替换为 `<...>` 形式的占位符（如 `<项目素材目录>`、`<meeting-asr 后端目录>`、`<本技能资源目录>`、`<系统字体目录>`、`<本地模型目录>`、`<外部视觉工具…（本包不含）>` 等）。这些占位符须在使用时按实际环境填写；本插件的随包技能资源通过 DSH 注入的 `<skill_resources>` 资源目录解析相对引用，不依赖任何本机绝对路径。
