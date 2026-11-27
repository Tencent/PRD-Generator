# PRD Generator — an AI skill that writes PRDs

**English** | [简体中文](README.zh-CN.md)

> Say "Write a PRD for …" plus a one-line requirement, confirm 3 steps, and get a **PRD document + a clickable interactive prototype + page screenshots + flow diagrams**. The prototype can then be packaged for delivery or turned into an online demo.

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](#)
[![Platform](https://img.shields.io/badge/platform-AI_Agent_Skill-green)](#)

---

## Highlights

### 1. Interaction and visual quality

A clickable prototype, 4 visual styles (just name the accent colour, e.g. "blue" or "brand red"), and screenshots and flow diagrams that are generated automatically so text and images always agree.

### 2. Guided steps

Only 3 confirmations. Every step tells you what is being done, what you need to do, and what you get once you confirm. On delivery you can open the PRD and the demo right away.

### 3. Flexible demo delivery

The core is not tied to any hosting service and needs no account or key:

- **Packaged delivery (default fallback)**: a single `demo.html` that works offline by double-clicking, with no server needed (clickable in IDE preview panes and browsers), plus a `prototype.zip` (multi-file version you can host yourself).
- **Record an online address**: host `prototype/` at any https address and record it in the PRD.
- **GitHub Pages in one step (optional)**: needs your GitHub token; the site is **public** and you are asked to confirm before every publish.

### 4. English and Chinese

The skill follows the language you start with. Open the conversation in English and the whole flow, the generated screenshots and the PRD are in English; open it in Chinese and everything stays in Chinese.

---

## Quick start

### Install (pick one)

**Option 1 (recommended): copy the text below and send it to your AI tool so it installs the skill itself**

```
Please install the PRD generator skill (prd-generator-oss) for me:
1. Download: open https://github.com/Tencent/PRD-Generator and get all the files with `git clone` or the Download ZIP button on that page. If you cannot open it or the download fails, tell me and I will download it myself and send you the path.
2. Install: make sure the folder you got contains SKILL.md, and put it into the skills directory of the AI tool you are running in, naming the folder exactly prd-generator-oss (it must match the name in SKILL.md; do not keep PRD-Generator or PRD-Generator-main). If you are not sure where that directory is, ask me first; do not guess. If a prd-generator-oss already exists at the target, rename it as a backup before putting the new one in; do not overwrite or delete it.
3. Self-check: run scripts/prdkit.py doctor and tell me the result in a sentence or two; for missing optional items only explain the impact and do not ask me to configure anything yet.
4. Wrap up: tell me where it was installed and remind me to open a new chat and type "Write a PRD" to try it.
```

**Option 2: download the zip and install it by hand**

Open https://github.com/Tencent/PRD-Generator, click Code → Download ZIP and unzip it. Rename the folder that contains `SKILL.md` to `prd-generator-oss`, and put it into the skills directory of your AI tool (the tool must support skills in the `SKILL.md` format).

After installing, open a new chat and type `Write a PRD`. A normal response means it works ✅

### Environment and configuration

**Runtime**: Python 3.8+, the page-screenshot component, macOS / Linux. A CJK font is needed only for Chinese projects. Before each start the skill checks the environment automatically; if something is missing it first tells you the impact and installs only after you reply "install": if Chrome or Edge is present only Playwright (the screenshot component, about 1 minute) is installed, otherwise the Chromium browser is downloaded too (about 3 minutes).

**No account or key is needed** to generate a complete PRD and prototype. On restricted networks, set `PRDKIT_PIP_MIRROR` and `PRDKIT_BROWSER_MIRROR` to use download mirrors.

---

## The 3 core commands

| Command | Example | Output |
|---|---|---|
| **Write a PRD** | `Write a PRD for a check-in mini program where users earn points every day and redeem gifts` | PRD (.md) + clickable prototype + screenshots + flow diagrams |
| **Revise a PRD** | `Update the quiz-game PRD: add a points-expiry rule` | A new PRD version with prototype, screenshots and flow diagrams kept in sync |
| **Publish the demo** | `Publish the demo` | A packaged `prototype.zip` (default), a recorded https address, or an optional GitHub Pages site |

Phrasing is flexible: "Draft a PRD for …", "I need a PRD for …", "Turn these notes into a PRD", "Generate PRD" all work. The Chinese commands (`PRD生成`, `PRD修改`, `发布在线Demo`) work too and switch the whole flow to Chinese.

---

## Important notes

- Having several skills configured can cause instruction conflicts; turn off the ones you do not need.
- A GitHub Pages site is **public**; for unreleased business content use packaged delivery instead.
- If you use the GitHub Pages publisher, keep the token (`GITHUB_TOKEN`) in an environment variable and **never paste it into the chat**; the skill never prints it or writes it to any file.

---

## FAQ

**The skill does not respond after installing?** Check that it is installed and enabled in your AI tool and open a new chat. If another directory with the same name was installed earlier, rename it as a backup first; two of them at once compete for the same instructions. Type the command alone in a fresh chat window.

**It says the screenshot component Playwright is missing?** Reply "install" and the AI installs it (about 1 minute with Chrome or Edge, about 3 minutes without, internet needed). If you do not want to install it, reply "not now"; the flow then stops at requirement understanding and cannot produce flow diagrams or prototype screenshots. If the automatic install fails, run `python3 -m pip install playwright` in a terminal and reply "done".

**Do I have to publish an online demo?** No. By default a single `demo.html` is delivered together with a `prototype.zip`; the PRD states how to open them, and you can add an online address any time later.

**Reviewers cannot open the online demo?** Check the site you host: that access is open, the address is correct, and `index.html` opens at the site root.

**Which product types are supported?** Mini programs, H5, apps, admin systems and API / services (API products have no pages, so the prototype and flow diagrams are skipped automatically).

---

## Contributing and feedback

Issues and pull requests are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md). For security problems see [SECURITY.md](SECURITY.md). Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) when taking part.

## License

Released under the [MIT License](LICENSE).

- Detailed usage guide: `guide.en.md` (English), `guide.md` (中文)
- AI execution instructions: `SKILL.md`
