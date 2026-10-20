# MakerSkill

我自己在用的 AI 技能（Skill）合集，开源免费，持续更新。

每个顶层目录就是一个独立技能：一份 `SKILL.md`，加上它用到的参考资料和脚本。复制到本地技能目录，AI 就会在合适的时候自动调用。文档都是中文。

## 什么是技能

技能是一份写给 AI 的作业指导书。它不是提示词模板，而是把一套做事流程固定下来：什么时候该用、按什么顺序做、每一步的质量标准是什么、做完产出什么。你提的需求和技能描述对得上，AI 就会加载它，按里面的流程执行。

## 技能清单

### 写作与文案

| 技能 | 作用 | 怎么叫它 |
|---|---|---|
| [meeting-digest](meeting-digest/) 会议精华稿 | 把会议、咨询、沟通的录音转写，提炼成结论导向、按主题归纳的精华稿 | 「做会议精华稿」「提炼会议要点」 |
| [wechat-moments-writer](wechat-moments-writer/) 朋友圈文案 | 按七步流程写朋友圈，支持生活、产品、认知、复盘等 10 种类型 | 「写朋友圈」「把这段包装成朋友圈」 |
| [product-launch-letter](product-launch-letter/) 产品发售信 | 为课程、训练营、社群、会员写第一人称的长篇发售信 | 「写发售信」「帮我卖课的文案」 |
| [video-structure-polish](video-structure-polish/) 口播稿结构润色 | 你说了一大段，它只做轻度润色，再给出结构上的表达优化建议 | 「帮我轻润色」「我说了一段话你帮我整理」 |
| [prompt-designer](prompt-designer/) 提示词设计 | 对话收集需求，产出角色、任务、流程、示例齐全的结构化提示词 | 「设计提示词」「帮我写个 prompt」 |

### 演示与页面

| 技能 | 作用 | 怎么叫它 |
|---|---|---|
| [mckinsey-deck](mckinsey-deck/) 麦肯锡演示页 | 把逐字稿改造成结论先行的 9:16 竖版 HTML 演示页，适合录屏讲解 | 「把逐字稿做成演示」「麦肯锡风格页面」 |
| [product-detail-page](product-detail-page/) 知识产品详情页 | 先写营销文案，再生成可预览的 HTML 详情页 | 「做详情页」「课程落地页」 |
| [course-ppt-writer](course-ppt-writer/) 课件文案 | 给零基础学员写授课型 PPT 文案，一个概念讲不清就拆成多页 | 「写课件」「把课程做成 PPT 文案」 |

### 视频

| 技能 | 作用 | 怎么叫它 |
|---|---|---|
| [web-frame-video](web-frame-video/) 网页逐帧视频 | 把产品介绍、功能演示写成网页，逐帧截图出 MP4，文字零错字 | 「做产品演示视频」「网页录屏式动画」 |
| [ai-concept-video](ai-concept-video/) AI 科普讲解视频 | 只写分镜脚本，配音决定节奏，自动排画面和字幕 | 「讲清 MCP 是什么，做成视频」 |
| [podcast-video](podcast-video/) 播客解读视频 | 两位主持人一问一答，竖屏音频海报画面，声波跟着人声起伏 | 「把这本书做成播客视频」 |

视频技能需要 Node 18+ 和 ffmpeg。配音读环境变量 `TTS_BASE_URL` 和 `TTS_API_KEY`，填任何提供 MiniMax `speech-2.8-hd` 的 OpenAI 兼容服务即可。网页逐帧视频不配音也能出片，另外两个必须配。

### 开发

| 技能 | 作用 | 怎么叫它 |
|---|---|---|
| [code-coach](code-coach/) 代码教练 | 先扫描仓库再开口，把技术栈、架构、全链路和学习路径讲给你听 | 「讲解这个仓库」「带我熟悉这个项目」 |

## 安装

克隆之后，把需要的技能目录复制到本地技能目录：

```bash
git clone https://github.com/zxmio/MakerSkill.git
cp -r MakerSkill/meeting-digest ~/.claude/skills/
```

不同工具的技能目录：

| 工具 | 目录 |
|---|---|
| Claude Code（用户级） | `~/.claude/skills/` |
| Claude Code（项目级） | `<项目>/.claude/skills/` |
| Codex | `~/.codex/skills/` |
| Antigravity / Gemini | `~/.gemini/config/skills/` |

项目级安装只在该仓库内生效，适合把技能随仓库一起分发给团队。

## 关于作者

张轩铭，MakerOS 创始人。市场营销专业的文科生，不懂代码，2024 年起全职做 AI 创业，把想法一个个做成了能用的产品。公众号、视频号、小红书都叫「张轩铭AI」。

技能用着有问题，欢迎提 Issue。

## 许可

[MIT](LICENSE)
