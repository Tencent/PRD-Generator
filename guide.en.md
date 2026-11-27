# PRD Generator Skill — User Guide (1.0.0)

**English** | [简体中文](guide.md)

> **For**: product managers / senior PMs / associate PMs / product owners
> **Version**: 1.0.0

---

## Highlights

### 1. Interaction and visual quality: what you get is clickable, good-looking and consistent

- **A clickable interactive prototype**: one HTML per page, state and popup, with real copy. The jumps between pages match the flow diagrams one to one; mismatches are found and fixed automatically.
- **4 visual styles + a custom accent colour**: flat / glass / soft / dark. You see a comparison in the IDE preview pane before choosing; just say the colour ("blue", "brand red", "orange"), no colour codes needed, and changing it later is cheap.
- **Fully automatic screenshots and flow diagrams**: 375px mobile and 1440px PC screenshots are embedded in the PRD; chapter-level and overall diagrams are generated and self-checked by the system, never hand-drawn, so text and images do not drift apart.
- **PRD and prototype share one source**: the page list, the "Flow" lines and the screenshots all come from the same registration data, so one change updates everything.

### 2. Workflow: guided steps, each one tells you what is being done, what you do, and what you get

- **Only 3 confirmations**: requirement understanding -> business-flow sequence diagram -> visual style. One screen per step, clearly blocked, always ending with "what happens after you confirm".
- **No idle waiting**: the style comparison is prepared before you choose, and generation starts right after you pick; step 3 already tells you the estimated time and page count.
- **See the result on delivery**: the PRD opens in the editor and the clickable demo opens in the IDE preview pane; every path and address given can be clicked.
- **Demo delivery in one choice**: after delivery you get a numbered menu (package / record an online address / GitHub Pages / not now); everything is done in order without interrupting you again.

### 3. Flexible demo delivery: take it away packaged, host it yourself, or publish to GitHub Pages in one step

- **The core is not tied to any hosting service and needs no account or key**: the whole PRD and prototype generation runs on your machine.
- **PRD links are back-filled automatically**: once you host `prototype/` at any https address, the "Prototype" line of every page and Appendix B are switched to online links in one go; until then the PRD carries no local address.
- **Packaged delivery is the default fallback**: a single `demo.html` (made by `prdkit bundle`) opens by double-clicking, needs no server or network, and is clickable in IDE preview panes and browsers; a `prototype.zip` (multi-file version, unzip and double-click `index.html`, or host it yourself) is attached, and the PRD states how to open them.
- **GitHub Pages in one step is optional**: the site is public and you are asked to confirm before every publish.
- **Optional, skippable, can be added later**: add an address any time and the links switch automatically.

---

## 0. Prerequisites

The core flow only needs: Python 3.8+, the page-screenshot component (Playwright + Chrome / Edge on your system, or the bundled Chromium), and, for Chinese projects only, a CJK font. **No account, token or internal network is needed.**

Ask the AI to run `prdkit doctor` for a check; if something is missing it first tells you the impact and installs only with your consent.

> 🔒 If you use a publisher that needs a token (see `references/publish.md` §3), keep the token in an environment variable. **Never paste a token into the chat or a screenshot**; the skill only reads it, never prints or stores it.

---

## 1. Quick start (up and running in 3 minutes)

### Install

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

**Verify**: open a new chat and type `Write a PRD`; a normal response means it works ✅. To check the environment first, ask the AI to run `prdkit doctor`.

Directory layout:

```
prd-generator-oss/
├── SKILL.md              <- AI execution instructions
├── README.md / guide.md / guide.en.md
├── references/           <- specs read on demand (flow diagrams, style, narrative, semantic checks, gates, revision, publishing)
├── templates/            <- PRD templates, page skeletons, 4 style sheets (templates/en for English projects)
├── scripts/
│   ├── prdkit.py         <- unified command entry (init/shot/flow/check/demo/links ...)
│   └── lib/              <- the engine
├── examples/neighbor-lend/      <- a complete example project (Chinese)
├── examples/neighbor-lend-en/   <- the same example project (English)
└── tests/regress.py             <- regression tests (for maintainers)
```

### Runtime and where files go

- **System**: macOS, Linux (Windows is not supported yet). **Network**: generating a PRD and prototype needs no internet; installing the screenshot component and using hosting / publishers does.
- **Where PRDs are stored**: by default `<workspace>/.codebuddy/docs/prd/<project>/`. To change it, set the environment variable `PRDKIT_PRD_ROOT`, or put a `.prdkit.json` in the workspace (content `{"prd_root": "your directory"}`), or use `prdkit init ... --root <directory>` when creating a project.

### Knowledge base (recommended)

```bash
mkdir -p {WORKSPACE}/.codebuddy/docs/biz-knowledge/{prd,business-rules,meeting-notes}
# put existing PRDs / business documents there; for iteration projects the AI searches and cites them
```

### A 30-second try

```
Write a PRD for a check-in mini program where users earn points every day and redeem gifts, the goal is to raise daily active users
```

---

## 2. Command overview

| Command | When to use | Example |
|---|---|---|
| `Write a PRD for {description}` | A new project / you have a clear idea | `Write a PRD for a quiz mini game on WeChat` |
| `Write a PRD draft for {description}` (or `--draft`) | A complex project: confirm the direction first (stops after the business flow is confirmed, no prototype) | `Write a PRD draft for an enterprise CRM system` |
| `Write only the {chapter} section of the PRD for {description}` (or `--module`) | Only one chapter is needed | `Write only the Points section of the PRD for a quiz game where answering earns points` |
| `Write a PRD based on {file}` / `Turn these notes into a PRD` | Meeting notes / an existing document | `Write a PRD based on /docs/meeting/notes.md` |
| `Update the PRD {project}: {change}` / `Revise` / `Change` / `Adjust the PRD` | Change an existing PRD, handle review feedback | `Update the quiz-game PRD: raise the points cap to 5000` |
| `Publish the demo` / `Host the demo` / `Package the demo` | Handle delivery of the prototype demo | Record an https address you host, or package it |

Quick replies: `confirm` = go to the next step; `start over` = reset; any other text = a change request for the item being confirmed.

The Chinese commands (`PRD生成`, `PRD修改`, `发布在线Demo`) work the same way and run the whole flow in Chinese.

---

## 3. The full flow

The whole chain has only **3 confirmations** plus **one demo-delivery choice** after delivery. Each step opens with "what this step does and what you need to do", then gives the necessary information.

```
Requirements -> Business flow -> Visual style -> Auto-generate prototype & PRD -> Deliver -> 1. confirm PRD -> 2. handle demo (record address / package)
 you confirm     you confirm      you choose     (about 4 + pages x 0.4 min)                  (reply with a number)
```

Before every "you confirm" the system runs the matching quality gate and fixes what it can once, so what you see has already been self-checked.

### 1. Requirement understanding

The AI **infers actively** from your description and the knowledge base and shows its understanding on one screen: positioning, users and scenarios, the main flow, the feature scope (P0 / P1 / P2 / explicitly out), preset values, and at most 2 questions that need your decision. You only judge right or wrong and reply "confirm".

The AI **presets the business values it can** (character limits, time windows, rule numbers and so on) and lists them; once you confirm they take effect and are recorded under "Default values" in PRD Appendix C for traceability. Only what truly cannot be preset (launch date, metric targets) is left as "to be supplemented" and does not block review.

### 2. Business flow

One business sequence diagram. What you confirm is **whether the business logic is right**; you do not review pages one by one. To see the page-flow diagram, say "show the page map".

### 3. Visual style

The AI **opens the style comparison in the IDE preview pane** and gives the image path (click it if the pane does not show it); you pick a number after looking. This message also gives the estimated time and page count, and **replying with a number counts as confirmation, after which generation starts**.

| Style | Character | Good for |
|---|---|---|
| Flat (default) | Solid blocks, no shadows, small corner radius | Tools, admin, dense information |
| Glass | Translucent blur, gradients, large radius | Consumer apps, mood-driven |
| Soft | Large radius, soft coloured shadows | Lifestyle services, community |
| Dark | Dark background, light text, glowing buttons | Tech, tools, night scenes |

Accent colour and style are independent: just say a colour (such as "blue", "brand red", "orange") or give a code (such as `#E5352B`); if you do not, the AI recommends one by the business tone and states why (by colour name, not code). You can change it any time at low cost.

### Prototype / flow diagrams / PRD (automatic)

Generation starts right after you choose the style, and you are told each time a stage finishes.

- Prototype: one HTML per page, state and popup, with real copy; colours all go through design variables.
- Screenshots: taken automatically from the spec into `images/`, 375px for mobile and 1440px for PC.
- Flow diagrams: chapter-level and overall, with an automatic geometry self-check (do lines cross pages, do they hug the edge).
- PRD: every chapter starts with "overview -> chapter flow diagram -> page list", and every page gets its own section (flow line + screenshot + element table + interaction rules).

### After delivery: read the PRD, choose the demo delivery in one go

On delivery the AI **opens the PRD (md)** in the editor, **opens the clickable demo** in the preview pane, gives you the clickable paths (the PRD path and the demo file path), and then a numbered menu:

- 1: Packaged delivery (recommended, most robust). A single `demo.html` opens by double-clicking (IDE preview pane and browser), plus a `prototype.zip` (multi-file version you can host yourself); no internet needed
- 2: Record an online address you already have (send the https address) so reviewers can click through (see §6)
- 3: Publish to GitHub Pages in one step (optional). You get a public link and need your GitHub token; **the site is public**, so do not choose it for unreleased business
- 4: Not now, keep the files local

If you want changes to the PRD, just say so. **The prototype links in the PRD are not written until you handle the demo**; they are filled in all at once afterwards.

---

## 4. Quality assurance: six gates

The aim is for **the output itself to be free of problems**; checks are only the safety net: anything a command can generate (screenshots, flow diagrams, page lists, flow lines, prototype links, Appendix B, the index page, styles) is never hand-written by the AI.

| Gate | When it runs | What it checks (examples) |
|---|---|---|
| env | Before starting | Python, the screenshot component (Chrome / Edge on your machine are preferred), CJK font for Chinese projects |
| map | Before the business flow is shown | Pages fully registered, flows closed, chapter naming |
| style | After the style is confirmed, before generation | Style and accent confirmed, style sheet complete |
| prototype | Before writing the PRD | Hard-coded colours, external links, script errors, failed screenshots |
| flow | Before writing the PRD | Flow-diagram geometry, label rules |
| prd | Before delivery | Structure, text-image consistency, flow lines matching the diagram, leftover comments, local addresses, demo-link consistency |

**Problems come in three levels**:

| Level | Handling |
|---|---|
| Fix directly | Mechanical with a unique result; the AI fixes it |
| Needs judgement | Fixed, then reported in the summary |
| Needs a user decision | Never invented: what can be preset is preset in "requirement understanding" for you to confirm; what truly cannot goes to PRD Appendix C "to be supplemented" |

**Loop and stop-loss**: run the gate -> fix -> rerun, at most 3 rounds; if the same error survives 2 consecutive checks the stop-loss triggers and the AI must step back and re-analyse, and tell you honestly if it still fails. **Only a zero-error result is handed to you.**

Semantic problems (scope matching the prototype, every rule having a matching element, screenshots matching the section title) cannot be found by scripts; the AI checks them **by looking at the images** against `references/qa-semantic.md`.

**Scoring**: machine score minus semantic deductions -> 90+ can go straight to review, 80-89 review after small tweaks, 60-79 needs additions, below 60 redo. Only the conclusion is given on delivery; say "show quality details" for the self-check detail.

---

## 5. Output files

```
{project directory}/
├── {name}-prd.md          the main PRD document
├── images/                page screenshots + flow diagrams (referenced by the PRD)
├── prototype/             clickable prototype (index.html is the entry)
├── spec/                  single source of truth: screens.json (pages/states/style/demo) + flows/ (flows)
├── {name}-{version}-prototype.zip   local fallback package (only when you explicitly choose not to host an online demo)
└── .prdkit/               intermediate output and publish records (ignore)
```

Iteration projects **create a new version directory** by default (such as `xxx-v2`) and keep the old version.

---

## 6. Online demo

A demo has three states and the PRD follows automatically:

| State | When | In the PRD |
|---|---|---|
| Pending (default) | Just delivered, not handled yet | Pages carry **no** prototype address; Appendix B says "preview links for each page will be added here after the online demo is published" |
| Online | You host `prototype/` at an https address and tell the AI | The "Prototype" lines and Appendix B carry the online link and entry |
| Local fallback | You explicitly say you will not host it | Local relative paths; Appendix B says "this version has no online demo", and `prototype.zip` is attached |

**Rules**

- You do the hosting yourself (GitHub Pages, static website on object storage, any web server); requirement: `prototype/index.html` opens at the site root; only `https://` addresses are accepted.
- To package, ask the AI to run `prdkit demo pack` for an archive without screenshots or intermediate output.
- After an address is recorded, the links in the PRD and Appendix B switch over together (the command is idempotent); changing the address or going back to the local fallback works the same way.
- Not hosting never blocks you: use the local fallback and add an address later.
- For "publish in one step" use the GitHub Pages publisher, see §6.1 below.

---

### 6.1 GitHub Pages in one step (optional)

- **The site is public**: anyone with the link can open it, no login needed. Before every publish the AI warns you separately and publishes only after you reply "confirm public"; for unreleased business use packaged delivery.
- **A GitHub token is needed**: keep it only in the environment variable `GITHUB_TOKEN`, never paste it into the chat; if it is not configured the AI first tells you the impact and gives the application steps only with your consent. The steps are in `references/publish.md` §4.
- **Several demos share one repository (default)**: published to the `prd-demos` repository under your account, one sub-directory per demo, with an address like `https://<account>.github.io/prd-demos/<project>-<version>/`.
- **One repository per demo**: tell the AI "give this demo its own repository `your-account/repo-name`" and it is published to the site root of that repository.
- **No accidental overwrite**: if the target sub-directory already has content you are asked first; replacing only replaces this one demo and leaves the others alone.
- **There is a delay**: after pushing it usually takes 1-2 minutes before the site opens, and a 404 in the meantime is normal.
- To take it offline, delete the sub-directory (or the whole repository).

---

## 7. Revising an existing PRD

Trigger: `Update the PRD {project}: {change}`, `Revise the PRD`, `Change the PRD`, `Adjust the PRD`, or paste review comments directly.

Flow: **judge the type of change and tell you the cost -> change the spec first (pages / flows) -> regenerate screenshots, flow diagrams, page lists, flow lines and prototype links -> then edit the body -> pass the gates**. Key points:

- Review feedback is itemised: location, accepted / not accepted, how it was handled; the "Revision Notes" table gets "what changed and why".
- Iteration defaults to a new version directory and keeps the old one; the new version's demo is reset to "pending" so it never points at the old site.
- The summary always carries a **publish reminder**: an online demo already recorded does not follow local edits, so re-host the latest `prototype/`.

---

## 8. Best practices

| ❌ Avoid | ✅ Prefer | Why |
|---|---|---|
| "Build an app" | "A WeChat mini program: answer quizzes to earn points redeemable for coupons, to raise official-account engagement" | Type + feature + goal |
| "A check-in system" | "An H5 check-in page, daily check-in earns points, doubled after 7 days in a row, embedded in the existing app" | Carrier + rules + constraints |

- After a meeting, use `Write a PRD based on {notes file}` directly: more information, fewer rounds.
- For complex projects start with a draft (`Write a PRD draft for …`): confirm only up to the business flow, which is the cheapest time to adjust the scope.
- In step 1 "requirement understanding", glance over every value the AI preset for you: once confirmed they are the definite values in the PRD.
- "To be supplemented" in Appendix C is what needs business data to decide; settle it together in review.

---

## 9. FAQ

**Q1: Do old projects still work?**
An old `flowmap-config.json` can be migrated into a new spec with `prdkit migrate`. For projects with a recorded demo: the old `pages` hosting mode must be changed to `online` with an https address; projects with no record are treated as "pending". Run `prdkit links --apply` once.

**Q2: Will the self-check change my content for me?**
It only changes what is "mechanical with a unique result" (links, table rows, leftover comments). It never changes business values or scope decisions on its own: what can be preset is preset for you to confirm in "requirement understanding", and what truly cannot goes to Appendix C "to be supplemented".

**Q3: Chinese text in the images shows as boxes?**
A CJK font is missing (Chinese projects only). The check stops this early; install one as prompted and rerun.

**Q4: How do I share it with the team?**
```
The PRD for XXX is done:
 📄 PRD: {project directory/{name}-prd.md, or wherever you keep it}
 🌐 Prototype: {online demo link or prototype.zip}
 📊 Quality: {overall score}/100, {K} items still to be supplemented (see Appendix C)
```

---

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| "Write a PRD" gets no response | Check that the skill is installed and enabled in your AI tool, and open a new chat |
| The screenshot component Playwright is missing | The opening check runs automatically and tells you the impact first; reply "install" and the AI installs it (about 1 minute with Chrome / Edge, otherwise about 3 minutes, internet needed); reply "not now" and the flow stops at requirement understanding. On restricted networks set `PRDKIT_PIP_MIRROR` / `PRDKIT_BROWSER_MIRROR`. If the automatic install fails run `python3 -m pip install playwright` in a terminal, then reply "done" |
| A CJK font is missing / Python is too old | Both need system privileges or another Python, so the AI does not install them; reply "guide" for instructions, then rerun after installing |
| A file cannot be found | Check `{WORKSPACE}/.codebuddy/docs/prd/` or ask the AI to run `prdkit where` |
| A gate reports "stop-loss" | The same problem survived two fixes; ask the AI to step back and re-analyse, or report what you see in the repository Issues |
| Reviewers cannot open the online demo | Check the access rights and address of the site you host; `index.html` must open at the site root; right after publishing to GitHub Pages a 404 for 1-2 minutes is normal |
| You want a demo without internet | Use packaged delivery: open the single `demo.html` directly, or unzip `prototype.zip` and double-click `index.html` |
| The local prototype preview does not open | Look at the screenshots instead, or host an online demo and use the link |
| A Mermaid diagram does not render | Use a previewer that supports Mermaid; the AI falls back to a numbered list of steps |

---

> 📮 Feedback and contributions: please open an Issue / Pull Request in the repository, see `CONTRIBUTING.md`.
