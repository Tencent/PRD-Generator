# PRD Generator — AI 驱动的 PRD 文档生成器

[English](README.md) | **简体中文**

> 输入“PRD生成”+ 一句话需求，确认 3 步，即可得到 **PRD 文档 + 可点击的交互原型 + 页面截图 + 流程图**，并可把原型整理成在线 Demo 或打包交付。

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](#)
[![Platform](https://img.shields.io/badge/platform-AI_Agent_Skill-green)](#)

---

## 亮点

### 1、交互与视觉升级

可点击的交互原型 + 4 种视觉风格（主色直接说颜色，如“蓝色”“品牌红”）+ 截图与流程图自动生成，图文一致。

### 2、分步引导升级

只需 3 步确认，每一步都告诉你“做什么、要你做什么、确认后得到什么”，交付即可看 PRD 和 Demo。

### 3、Demo 交付灵活

核心不绑定任何托管服务，也不需要任何账号或密钥：

- **打包交付（默认兜底）**：单文件 `demo.html` 双击即可演示，离线可用、不依赖服务（IDE 预览窗和浏览器都能点）；另附 `prototype.zip`（多文件版，可自行托管）。
- **记录在线地址**：把 `prototype/` 托管到任意 https 地址并记录进 PRD。
- **GitHub Pages 一键发布（可选）**：需要你的 GitHub 令牌；站点**公开**，每次发布前都会提示并要你确认。

---

## 快速开始

### 安装（二选一）

**方式一（推荐）：复制下面这段话发给你的 AI 工具，让它自己安装**

```
请帮我安装 PRD 生成 skill（prd-generator-oss）：
1. 下载：打开 https://github.com/Tencent/PRD-Generator ，用 git clone 或页面上的 Download ZIP 取得全部文件。打不开或下载不了，就告诉我，我手动下载后把路径发你。
2. 安装：确认得到的目录里有 SKILL.md，把它放进你（当前这个 AI 工具）的 skills 目录，目录名必须定为 prd-generator-oss（与 SKILL.md 的 name 一致，不要沿用 PRD-Generator 或 PRD-Generator-main）；不确定目录在哪，先问我，不要猜。目标位置如果已有 prd-generator-oss，先改名备份再放入，不要直接覆盖或删除。
3. 自检：运行 scripts/prdkit.py doctor，用一两句话告诉我结果；缺少的可选项只说明影响，先不要让我去配置。
4. 收尾：告诉我装在了哪里，提醒我新开一个对话，输入「PRD生成」试用。
```

**方式二：下载 zip 手动安装**

打开 https://github.com/Tencent/PRD-Generator ，点击 Code → Download ZIP 并解压，把含 `SKILL.md` 的文件夹重命名为 `prd-generator-oss`，放进你的 AI 工具的 skills 目录（需支持 `SKILL.md` 格式的 Skill）。

装好后新开对话，输入 `PRD生成`，正常响应即成功 ✅

### 环境与配置

**运行环境**：Python 3.8+、页面截图组件、中文字体；macOS / Linux。每次开始前 Skill 会先自动巡检，缺了会先告诉你影响，经你回复“安装”后才安装：电脑上有 Chrome 或 Edge 时只装 Playwright（截图组件，约 1 分钟），否则还要下载 Chromium 浏览器（约 3 分钟）。

**无需任何账号或密钥**即可完整生成 PRD 与原型。网络受限时，可用环境变量 `PRDKIT_PIP_MIRROR`、`PRDKIT_BROWSER_MIRROR` 指定下载镜像。

---

## 3 个核心指令

| 指令 | 示例 | 产出 |
|---|---|---|
| **PRD生成** | `PRD生成 做一个签到打卡小程序，用户每天签到获积分兑礼品` | PRD（.md）+ 可点击原型 + 截图 + 流程图 |
| **PRD修改** | `PRD修改 quiz-game 补充积分过期规则` | 新版本 PRD，原型、截图、流程图同步 |
| **发布在线Demo** | `发布在线Demo` | 打包 `prototype.zip`（默认）、记录你的 https 地址，或可选地发布到 GitHub Pages |

---

## 重要提醒

- 配置了多个 Skill 可能存在指令冲突，建议关闭非必要的 Skill。
- GitHub Pages 站点是**公开**的，涉及未发布业务请改用打包交付。
- 如使用 GitHub Pages 发布器，令牌（`GITHUB_TOKEN`）只放环境变量，**不要贴到聊天里**，Skill 不会打印或写入任何文件。

---

## FAQ

**Skill 安装后无响应？** 检查你的 AI 工具里 Skill 是否已安装并启用，并新开对话；之前装过其他同名目录的，请先改名备份，否则两个同时存在会抢同一批指令；在新的 Chat 窗口单独输入指令。

**提示缺少截图组件 Playwright 怎么办？** 回复“安装”即可，AI 会自动安装（有 Chrome 或 Edge 约 1 分钟，没有约 3 分钟，需要联网）。不想装可回复“先不安装”，但只能做到需求理解，生成不了流程图和原型截图。自动安装失败时，在终端执行 `python3 -m pip install playwright`，再回复“好了”。

**必须发布在线 Demo 吗？** 不必须。默认打包 `prototype.zip`：解压后用浏览器双击 `index.html` 即可演示，PRD 里会写明打开方式，之后可随时补在线地址。

**评审人打不开在线 Demo？** 检查你托管的站点：访问权限是否开放、地址是否正确、站点根路径能否打开 `index.html`。

**支持哪些产品类型？** 小程序、H5、App、后台系统、API/服务（API 类没有页面，自动跳过原型与流程图）。

---

## 贡献与反馈

欢迎通过 Issue 反馈问题、通过 Pull Request 贡献代码，详见 [CONTRIBUTING.md](CONTRIBUTING.md)；安全问题请见 [SECURITY.md](SECURITY.md)；参与社区请遵守 [行为准则](CODE_OF_CONDUCT.md)。

## 许可

本项目基于 [MIT 协议](LICENSE) 开源。

- 使用指南详细版：`guide.md`（中文）、`guide.en.md`（English）
- AI 执行指令：`SKILL.md`
