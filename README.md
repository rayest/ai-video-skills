# AI 视频技能包

让 AI Agent（Claude Code 等支持 Skills 的工具）自己做短视频：查资料、写脚本、配音、出图、渲染、配乐，全部用代码完成，不用剪辑软件，也不用版权音乐。

这些技能来自我日常做视频的真实流程，每一条规则背后都是一次返工。

## 里面有什么

| 技能 | 做什么 |
| --- | --- |
| [`explainer-video`](skills/explainer-video/SKILL.md) | 竖屏讲解 / 测评短视频（1080×1920，60–90 秒）。核实官方资料 → 出展示图 → 豆包配音（带逐字时间戳）→ 发布会风格渲染：卡点切镜，关键词出现的那一刻画面同步弹出，原创配乐和音效全部代码合成。 |
| [`product-promo-from-repo`](skills/product-promo-from-repo/SKILL.md) | 从代码仓库做产品宣传片：读代码拿真实的功能和文案 → 三条故事线 → 分镜 → MiniMax 配音 → 用 HTML 按源码重绘产品界面（不用截图）→ 原创配乐。 |
| [`tools/mem-guard`](tools/mem-guard) | 在 4GB 小服务器上安全跑 ffmpeg / whisper / 逐帧渲染的内存护栏，配套[经验文档](tools/LOW-MEMORY.md)。 |

`explainer-video` 附带一个完整案例（[examples/gpt-image-2.6](skills/explainer-video/examples/gpt-image-2.6)）：资料汇总、脚本、渲染器和配乐合成代码。成片 92 秒、约 20 MB。

## 安装

把下面这段话发给你的 AI Agent：

```text
请安装这个仓库里的全部 Skills：https://github.com/rayest/ai-video-skills
```

或者手动复制：

```bash
git clone https://github.com/rayest/ai-video-skills
cp -r ai-video-skills/skills/* ~/.claude/skills/
cp ai-video-skills/.env.example ./.env   # 填入你自己的 API Key
```

依赖：Python 3（numpy、Pillow；配乐脚本另需 scipy）、ffmpeg、Noto Sans CJK 字体。

## 用法

直接跟 Agent 说：

- 「XX 模型发布了，核实资料做个讲解视频」
- 「给这个仓库做一个 40 秒的产品宣传片，要配音」

Agent 会先给你看脚本，确认以后才调用要付费的配音和出图接口。

## 设计原则

- **声音是时钟**：画面切换卡在音乐节拍上，元素弹出卡在配音念到那个词的时刻。
- **只说能核实的**：每个数字都有出处，官方说法标注「官方说」。
- **不在片尾打广告**：前 2 秒给结果，结尾留一个可截图保存的要点和一个提问。
- **说清哪些测过、哪些只看过**：交付时报告响度、峰值、时长，也会说明哪几个镜头最弱。

## 许可

MIT
