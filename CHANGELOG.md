# Changelog / 更新日志

This file records the main changes of each public release. 本文件记录对外发布版本的主要变化。

## [1.0.0]

First public release. 首个对外发布版本。

**English**

- **Language dimension (English / Chinese)**: a project has a language (`spec.lang`, default `zh`; create one with `prdkit init --lang en`, or pass `--lang` for commands without a project). Everything user-visible follows it: quality-check messages and hints, command output, `--help`, flow-diagram text, the PRD and page templates (`templates/en/`), style-comparison pages, the opening environment check and the GitHub Pages publisher. The Chinese output is unchanged and is guarded by a golden baseline (`tests/golden/zh/`).
- English projects do not require a CJK font, so an English user's clean machine is no longer blocked at the opening check.
- **The skill follows the user's language**: the language of the first message decides it (English triggers such as `Generate PRD` / `Revise PRD` / `Publish demo` switch the whole flow to English: English guidance, `prdkit init --lang en`, English templates, an English PRD). Mixed or unclear first messages default to Chinese. All user-visible messages moved out of `SKILL.md` into `references/messages.zh.md` (verbatim, unchanged) and the new `references/messages.en.md`; `SKILL.md` keeps the flow and rules plus a language-routing section.
- New English example project `examples/neighbor-lend-en`, English `README.md` and `guide.en.md` (the Chinese versions are `README.zh-CN.md` and `guide.md`), and bilingual community files.
- Single-file demo delivery: new `prdkit bundle` packs the prototype into one `demo.html` that needs no server, port or network and is clickable in IDE preview panes and browsers; `prdkit view --bundle` is only used to auto-open the preview pane on delivery. Fixed the "Back" button not responding inside the single file.
- Step 2 no longer opens the preview pane; the style comparison is shown in step 3 instead.
- The style comparison opens with a fallback chain by host capability: preview-pane tool, side-panel tool, text link.
- The opening environment reminder names exactly what is missing (Playwright, Chromium, CJK font, Python version); install commands are only given when the user asks, and the user's consent is still required first.
- `SKILL.md` header: trigger scenarios moved into `description`, the top-level `triggers` field removed.

**中文**

- **语言维度（英文 / 中文）**：项目有了语言属性（`spec.lang`，缺省 `zh`；`prdkit init --lang en` 新建英文项目，没有项目的命令用全局 `--lang`）。质检提示、命令输出、`--help`、流程图文字、PRD 与页面模板（`templates/en/`）、风格对比页、开场环境巡检、GitHub Pages 发布器都跟随语言；**中文输出不变**，由黄金基线（`tests/golden/zh/`）守护。
- **Skill 跟随用户语言**：以用户第一条消息的语言为准，英文触发词（`Generate PRD` 等）整条链路切英文；中英混杂或拿不准默认中文。全部用户可见话术从 `SKILL.md` 移到 `references/messages.zh.md`（逐字不变）与新增的 `references/messages.en.md`。
- 英文项目不要求中文字体；新增英文示例 `examples/neighbor-lend-en`、英文 `README.md` 与 `guide.en.md`（中文版为 `README.zh-CN.md`、`guide.md`）、中英双语社区文件。

- Demo 单文件交付：新增 `prdkit bundle`，把原型打成不依赖服务、端口和网络的单个 `demo.html`，在 IDE 预览窗和浏览器里都能点；`prdkit view --bundle` 仅用于交付时自动打开预览窗。修复单文件里“返回”按钮点击不生效的问题。
- 第 2 步明确不打开预览窗，风格对比图改在第 3 步展示。
- 风格对比图按宿主能力降级打开：预览窗工具、侧边面板打开工具、文字链。
- 开场环境提醒直接写出缺少的组件（Playwright、Chromium、中文字体、Python 版本）；安装命令只在用户主动要求时给出，仍须先征得同意。
- `SKILL.md` 头部：触发场景并入 `description`，去掉 `triggers` 顶层字段。

## [5.2.0] - 开源首发

首个开源版本，基于内部 V5.2 能力整理：

- 一句话需求 → PRD 文档 + 可点击的 HTML 交互原型 + 页面截图 + 流程图 + 质量自检。
- 3 个确认点的分步引导；4 种视觉风格与自定义主色。
- 质量闸门（env / map / style / prototype / flow / prd）与 `prdkit lint`。
- Demo 交付：打包 `prototype.zip`（解压后用浏览器打开 `index.html` 即可演示）、记录在线地址（`prdkit demo online`）。
- 可选发布器：`prdkit publish github-pages`（公开站点，每次发布需显式确认）。
- 核心流程不需要任何账号、令牌或内部网络环境。
