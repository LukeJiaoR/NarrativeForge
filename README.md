# NarrativeForge

NarrativeForge 是一个面向 AI Agent 的本地媒体编排实验室。它把叙事规划、语音、
字幕时间轴、视觉素材检索、合成与质量验证拆成可观察、可替换、可审计的工作阶段。

项目主页：[github.com/LukeJiaoR/NarrativeForge](https://github.com/LukeJiaoR/NarrativeForge)

这个仓库目前处于重构早期。重点不是提供一个固定内容类型的“一键生成器”，而是建立
一套可以被 Agent、CLI、API 和 WebUI 共同调用的通用媒体工作流。

## 设计方向

- **Agent-first**：每个阶段拥有明确输入、输出、错误状态和可恢复产物。
- **时间轴可信**：字幕默认从最终音频对齐，不用字符数估算替代真实时间戳。
- **视觉语义可信**：把文案转换成可见场景意图，处理品牌名、专有名词和同形异义词。
- **来源可追踪**：素材记录提供方、查询词、资源 ID、来源页面和创作者信息。
- **Provider 可替换**：LLM、TTS、ASR、素材库、配乐和发布通道保持独立。
- **Local-first**：配置、任务产物、模型和生成文件默认留在本机。

## 当前能力

- WebUI、FastAPI 与 CLI 三种入口
- 多种 LLM 和兼容 OpenAI 协议的模型网关
- Edge、MiMo、Gemini、Azure、ElevenLabs 等语音来源
- Whisper 音频对齐字幕
- Pexels、Pixabay、Coverr 与本地素材
- 竖屏、横屏视频合成与字幕渲染
- 任务状态、素材来源记录和跨平台发布扩展

## 快速开始

需要 Python 3.11+、FFmpeg 和 [uv](https://docs.astral.sh/uv/)。

```bash
cp config.example.toml config.toml
uv python install 3.11
uv sync --frozen
sh webui.sh
```

WebUI 默认地址：

```text
http://127.0.0.1:8501
```

启动 API：

```bash
uv run python main.py
```

API 文档：

```text
http://127.0.0.1:8080/docs
```

配置文件 `config.toml`、本地模型目录 `models/` 和任务目录 `storage/` 都不会提交到 Git。
仓库不捆绑字体或音乐二进制；字幕默认使用系统 Unicode 字体，背景音乐请通过
WebUI/API 上传拥有使用权的文件。

## 默认质量策略

- `match_materials_to_script = true`
- `subtitle_provider = "whisper"`
- Whisper 模型为 `large-v3-turbo`
- 视觉检索词必须描述可见的人物、动作、物体、地点或事件
- 专有名词和同形异义词不得机械重复到每条素材查询中

首次使用 Whisper 会下载本地模型。若只想快速试验，可以自行在配置中切回其他字幕策略。

## 重构路线

详细设计见 [docs/refactor-roadmap.md](docs/refactor-roadmap.md)。当前优先级：

1. 用结构化 shot intent 取代字符串关键词数组。
2. 给素材候选增加语义评分、歧义拦截和拒绝原因。
3. 统一 TTS 时间戳能力声明，并对无时间戳语音强制执行 ASR 对齐。
4. 将任务阶段改造成可恢复、幂等的 Agent 工具契约。
5. 建立渲染前后自动 QA 和可人工复核的证据包。

## 测试

```bash
uv run pytest -q
```

## 项目状态

这是一次独立的新仓库初始化，不继承其他仓库的 Git 历史，也不是 GitHub Fork。
接口、配置结构和目录布局都可能在重构期间变化。

## License

MIT。仓库包含基于既有 MIT 许可代码继续演进的部分，原始版权声明保留在
[LICENSE](LICENSE) 和 [NOTICE.md](NOTICE.md) 中。
