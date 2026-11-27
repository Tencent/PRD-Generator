# User-facing messages (English)

This file holds every message the skill says to the user when the conversation is in English (see `SKILL.md` §0.5). It mirrors `references/messages.zh.md` block for block: same ids, same structure, same placeholders. The flow, conditions and rules stay in `SKILL.md`; only the wording lives here.

How to use: read this file **once** at the start of the conversation, then send the block that the "message block" pointers in `SKILL.md` name, replacing only the curly-brace placeholders. Do not paraphrase from memory.

Reply words the user may type (English projects), matched by intent rather than exact text: agree to install = `install` / `yes` / `ok` / `go ahead`; decline = `not now` / `skip` / `no`; instructions = `guide` / `how`; finished installing = `done`; confirm a step = `confirm` / `ok` / `yes` / `looks good` / `go ahead`; reset = `start over` / `redo`; package = `package`. **Publishing publicly accepts only `confirm public`**: `ok` / `yes` do not count, because it is an irreversible public action. Treat the Chinese reply words as equivalent.

## M-A  Template A: ask for the requirement

```
Sure, just tell me what you want to build, one or two sentences is enough, for example:

- Build a pet-clinic booking mini program: users pick a doctor and a time slot, the clinic manages schedules
- Build an operations back office: support staff look up orders and start refunds, managers read the refund report
- Turn these meeting notes into a PRD: /path/notes.md

The more specific you are, the fewer questions I need to ask. Anything critical that is missing I will confirm with you in the next step.
```

## M-B  Template B: reminder block (appended after template A)

```
---

**One more thing: generating the prototype and flow diagrams needs the screenshot component Playwright**

Your computer is missing Playwright (the component that takes screenshots of the prototype and flow diagrams); without it I cannot produce the prototype screenshots or flow diagrams.

- {detected line}
- {install line}
- Impact: only adds component files, nothing already installed on your computer is changed

👉 Reply "install" and I will install it; you can send your requirement together with "install". If you would rather not install it now, reply "not now".
```

## M-C  Template C: short reminder when a description was given

```
**Install the screenshot component Playwright first, then I will organise your requirement**

Your computer is missing Playwright (the component that takes screenshots of the prototype and flow diagrams); without it I cannot produce the prototype screenshots or flow diagrams.

- {detected line}
- {install line}
- Impact: only adds component files, nothing already installed on your computer is changed

👉 Reply "install" and I will install it and then start organising your requirement right away; if you would rather not install it now, reply "not now".
```

## M-MANUAL  Reminder block for items the user must handle (old Python / missing CJK font)

```
**One more thing: the environment for generating the prototype and flow diagrams is not complete yet**

{OLD_PYTHON: The Python on your computer is too old (3.8 or newer is required), so Playwright cannot be installed. | NO_FONT (Chinese projects only): your computer has no CJK font (such as Noto Sans CJK), so Chinese text in screenshots and flow diagrams would show as boxes and cannot be delivered.}

This one needs you to act yourself, and I can tell you how.

👉 Reply "guide" for the instructions; if you would rather not handle it now, reply "not now".
```

## M-INSTALLED  Two-line confirmation after a successful install

```
- ✅ Playwright installed{when a browser was downloaded, add a line: ✅ Chromium browser downloaded}
- ✅ Verified that screenshots work
```

## M-E  Template E: the install failed

````
{Playwright / The Chromium browser} was not installed: {reason: network download failed / the install command failed / the system forbids installing directly}.

You can run the command below in your own terminal (only in your own terminal):

```
{manual install command}
```

Once it is installed, reply "done" and I will check again.
````

## M-D  Template D: the user chose not to install

```
Okay, not installing for now.

Without this component I can only help you with the requirement understanding (step 1); the business-flow diagram, prototype screenshots and flow diagrams cannot be produced.

If you want to continue, reply "install" any time.
```

## M-STEP1  Step 1: requirement understanding

```
**[Step 1 of 3] Requirement understanding**

I organised my understanding of the product from your description.

👉 Please check whether I got anything wrong: reply "confirm" if it is fine, otherwise tell me what is off.

**① Positioning**

What the product is and whose problem it solves (1-2 sentences)

**② Users and scenarios**

Who uses it, in what situation (1-2 sentences)

**③ Main flow**

Enter → … → done (3-5 steps)

**④ Feature scope**

- P0 must-have: …
- P1 should-have: … (at most 5, merged into one line)
- Explicitly out of scope: …

**⑤ Values I preset for you** (change them directly if wrong)

- Platform and viewport: …
- Success metrics: north star + how it is measured
- Accent colour: {colour description, e.g. brand blue / blue / orange} ({basis})
- Key values: such as time windows, character limits, validity periods
- Other assumptions: …

**⑥ Needs your decision** (at most 2, each with my recommendation; omit this block if there are none)

1. …

▶ After you confirm: I will first lay out a business-flow diagram for you to confirm (about 1 minute); then you pick a visual style; after that I generate the complete PRD automatically (page interaction specs, business rules, data fields, tracking events), a clickable interactive prototype and flow diagrams.
```

## M-STEP2  Step 2: business flow

```
**[Step 2 of 3] Business flow**

I laid out the business flow below from your requirement (who does what, and when).

👉 Please confirm the flow is right: reply "confirm" if it is, otherwise tell me what to change.

(Mermaid sequence diagram)

▶ After you confirm: we move on to choosing the visual style (a few seconds; the comparison opens in the preview pane and you just pick a number). Once chosen, I generate the interactive prototype, flow diagrams and the complete PRD automatically, and you do not need to do anything while it runs.
```

## M-STEP3  Step 3: visual style

```
**[Step 3 of 3] Visual style**

The style comparison is open in the preview pane on the right. This step decides the overall look of the prototype and the PRD screenshots.

If you do not see it, click the path below to view it (image file):

`{image absolute path}`

👉 Reply with a style number (to change the accent colour just name a colour, such as "blue", "brand blue", "brand red" or "orange"); reply "you decide" and I follow my recommendation.

**① Styles**

1. Flat: solid blocks, clean and crisp (tools, admin)
2. Glass: translucent texture (consumer products that stress atmosphere)
3. Soft: large radius, gentle (lifestyle services, community)
4. Dark: dark base with light text (tech, night-time scenarios)

**② My recommendation**

No. {number} with accent {colour description, e.g. brand blue / orange}. {one-sentence reason}.

**③ After you reply I will generate automatically** (about {T} minutes, no action needed from you)

- Interactive prototype: {N} pages (including popups and states), clickable
- Page screenshots: {N}, embedded in the PRD
- Business flow diagrams: chapter-level + overall
- The complete PRD: background, business rules, data fields, page interaction specs, tracking events, exception handling and more

▶ When done: I open the PRD in the editor, open the clickable interactive demo in the preview pane, and give you both paths; after you confirm you can record an online demo address or package it for delivery.
```

## M-PROGRESS  Progress lines during generation

```
- ✅ Interactive prototype: {N} pages drawn, screenshots checked
- ✅ Flow diagrams generated
- 🔄 Writing the PRD (about {y} minutes)
```

## M-DELIVER  Delivery message

```
**✅ The PRD and prototype are ready** (took {X} minutes)

The PRD is open in the editor and the interactive demo is open in the preview pane.

**PRD (this file is the source of truth)**

`{PRD absolute path}`

**Interactive demo** (a single file; click the path to click through it in the IDE preview pane)

`{project directory absolute path}/{name}-{version}-demo.html`

To share it: send this one file; the recipient double-clicks it in a browser (for a remote IDE, download the file to your machine first).

👉 Please read the PRD first and tell me what to change (for example: "change the points cap to 5000"). If it is fine, reply with a number below to handle the demo (say it all at once; I will do it in order without interrupting you):

- 1 Packaged delivery (recommended, most robust): the demo.html above works offline as a single file; plus a prototype.zip (multi-file version you can host yourself); no internet needed
- 2 I already have an online address (attach the https address): recorded in the PRD so reviewers can click through
- 3 Publish to GitHub Pages in one step (optional): gives a public link and needs your GitHub token; the site is public, so do not choose it for unreleased business
- 4 Not now, keep the files local

For example reply: "1" or "2 https://example.com/my-demo"

▶ After handling: the online address or the local way of opening it is filled into every page of the PRD and Appendix B.

{When there are C-type open items, add one paragraph: {K} more items need business data, see PRD Appendix C.}
```

## M-PUBLIC  Public confirmation (when option 3 is chosen)

```
This demo will be published to GitHub Pages, which is a **public site**: anyone with the link can open it, no login needed.

The page copy, business rules and interface design in the PRD prototype will be visible. For unreleased business or confidential information, I recommend packaged delivery instead.

👉 To publish publicly, reply "confirm public"; to switch to packaged delivery, reply "package".
```

## M-DONE  Handling finished

```
**✅ Done**

**Local delivery package** (unzip it and open index.html in a browser to demo)

`{project directory absolute path}/{name}-prototype.zip`

**Online demo**

https://{address}

**Note**: this is a public address; anyone with the link can open it.

▶ To change the PRD later, just tell me what to change, for example "update the PRD: change the points cap to 5000"; after the change I will remind you to handle the demo again.
```

## M-QUALITY  Quality details

```
📊 Quality details: machine {score}/100 · semantic {K} issues → overall {score}/100 ({grade})
Self-check: found {N} → fixed automatically {M} → awaiting your confirmation {K}
Fixed: …
To be supplemented: … (see Appendix C)
```

## M-REVISE  One-line judgement before changing a PRD

```
I judge this to be a "{type}" change that touches {files / pages}, about {x} minutes. {For an iteration: I suggest saving it as a new version {name}-v{n} and keeping the old one.} Is that okay?
```

## S-LINES  Values for {detected line} / {install line} (by the two status lines of the opening check)

| `ENV` | `SYSTEM_BROWSER` | {detected line} | {install line} |
|---|---|---|---|
| `NO_PLAYWRIGHT` | contains `chrome` or `msedge` | Detected: {Chrome / Edge} is on your computer and will be used for screenshots, so no extra browser download is needed | Needs installing: Playwright (a Python library), about 1 minute, internet required |
| `NO_PLAYWRIGHT` | `none` | Chrome or Edge was not detected; the Chromium browser also needs to be downloaded | Needs installing: Playwright plus the Chromium browser, about 150MB, about 3 minutes, internet required |
| `NO_BROWSER` | any | Playwright is installed, but there is no usable browser | Needs installing: the Chromium browser, about 150MB, about 3 minutes, internet required |

Name what is missing directly and say in one sentence what it does; **never put install commands in the reminder block** (give them only when the user asks). Do not show internal command names (`doctor`, `setup`, `pip`) to the user.

## S-REPLY  How to handle the user's reply

| User reply | What to do |
|---|---|
| "install" (or a clear yes such as "ok", "yes", "go ahead") | Run `prdkit --lang en setup --yes`, after first sending: `Got it, installing the screenshot component first (about 1 minute).` If the tool needs network permission, request it, then run |
| "install" + a requirement | Same; once installed go straight into step 1 and **do not ask for the requirement again** |
| "not now" | Send template D. If a requirement was already given, go straight into step 1 right after (step 1 does not need this component) |
| No answer about installing, only a requirement | Treat it as **not agreed; never install**. Go into step 1; after step 1 is confirmed and before step 2 starts, ask once more with one line: `To draw the flow diagram next I need the screenshot component first; reply "install" and it takes about 1 minute.` |
| "guide" | Run `prdkit --lang en setup` (without `--yes`) and paraphrase the fix it prints in plain language |
| The user asks for the command ("what is the command", "I'll install it myself") | Only now give the manual install command (the "Manual install" line of the `prdkit --lang en setup` dry run) and ask them to run it in their own terminal; reply "done" and you check again. Do not volunteer it |

After a successful install, when the user did not send a requirement, add: `All set, now tell me what you want to build, one or two sentences is enough.`; if they did send one, go straight into step 1.

If the user declined but already gave a requirement, template D ends with: `Then I will organise the requirement understanding first.`, followed by step 1.

## S-DELIVERY-REPLY  Replies after delivery

| User reply | What to do |
|---|---|
| Change requests | Read `references/revision.md` and follow SKILL.md §7; afterwards go back to "Please take another look; reply with a number if it is fine" and add only one line of menu hint |
| A number (with an address) | Go to §4.2 |
| Only "publish the demo" or a similar request (no choice) | Send the **whole menu** of the delivery message once |
| "not now" / 4 / only "confirm" | Reply `Okay, the files stay local. To handle the demo later, say "publish the demo" any time.` Keep the demo state "pending"; run `prdkit view --stop` silently |

If information is missing, ask **only for the missing item** in one sentence: chose 2 without an address -> ask for the https address.

## S-FALLBACK  Step 3 when the preview pane cannot open the style comparison

- A side-panel tool (such as `present_files`) opened the image: call the pane the "right-hand panel", and replace the "If you do not see it" and path lines with one sentence: `Tell me if you do not see it.`
- No such tool or it failed: change the first sentence to `The preview pane could not open automatically; please click the link below to view it`, and replace the two path lines with one text link (link text `Click to view the style comparison`, target the absolute image path wrapped in angle brackets, path not shown). If the user says it will not open, give the path in backticks instead.
- At delivery, when the preview pane cannot open: change the sentence to `The preview pane could not open automatically; please click the file path below`, and give the paths as usual.

## S-BLOCKING  Step 1: the one question you must ask, and the iteration line

- A missing product type must be asked about; offer the options: `Mini program / H5 / App / Admin system / API service`. Nothing else blocks.
- For an iteration project add one line: `Version strategy: save as a new version {name}-v{n}, the old one is kept.`

## S-TOKEN-GUIDE  The GitHub token guide (after the user replies "guide")

Four steps, in this order. Every page the user must open carries a direct link on its own line, without backticks, so it is clickable in the IDE. Every command the user must copy is a fenced code block on its own, copied verbatim: never turn it into inline code, never split it.

**Step 1. Create the repository `prd-demos` first** (skip it if your account already has one). A token limited to one repository can only select a repository that already exists:

https://github.com/new?name=prd-demos&visibility=public

Keep the name `prd-demos` and **choose Public**: a GitHub Pages site is public anyway, and GitHub Free can only publish Pages from a public repository (Pro, Team and Enterprise are needed for a private one). With a private repository, publishing can still fail at the step that turns Pages on.

**Step 2. Create the token**, open this page while signed in to GitHub:

https://github.com/settings/personal-access-tokens/new

(A classic token also works: https://github.com/settings/tokens/new , tick `public_repo` for a public repository; a private repository needs `repo` and a paid plan.)

- Expiration: 30 days or less
- Resource owner: **the personal account that owns the repository** (not an organization, otherwise the token cannot see it)
- Repository access: **Only select repositories**, choose `prd-demos` only
- Repository permissions: **Contents: Read and write**, **Pages: Read and write**, Metadata: Read

If a link does not open: avatar (top right) -> Settings -> Developer settings -> Personal access tokens -> Fine-grained tokens -> Generate new token.

**Step 3. Save the token as `GITHUB_TOKEN`** (never paste the token into this chat, a screenshot or a project file):

```bash
echo 'export GITHUB_TOKEN="your-token-here"' >> ~/.bashrc
```

If your shell is zsh, use `~/.zshrc` instead of `~/.bashrc`. Replace `your-token-here` with the real token.

**Step 4. Reply "done"**, and I check it and publish.

If publishing later says the token cannot create repositories, it means `prd-demos` does not exist yet: do Step 1, then reply "done".

## S-PENDING  The marker for open items in an English PRD

Write `[TBC - PM to supply]` where a value truly cannot be preset, and list all of them in Appendix C. On delivery tell the user only the count and point to Appendix C.
