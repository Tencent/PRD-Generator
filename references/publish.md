# Demo 交付与发布

交付时让用户**一次选完** Demo 的交付方式，之后一次做完、中途不再打断。对话话术见 `SKILL.md` §3.7、§4；本文是命令、规则和出错处理。

核心（prdkit）只负责**打包与记录在线地址**。核心不内置任何托管服务，也不需要任何凭证。

Demo 有三种去处，**打包交付是默认兜底**，任何情况下都可用：

| 去处 | 怎么做 | 需要什么 | 谁能看 |
|---|---|---|---|
| 打包交付（默认兜底） | `prdkit bundle` + `prdkit demo local` | 无 | 单文件 `demo.html` 双击即开，离线可用；另有 zip，解压后用浏览器双击 `index.html` |
| 自己的在线地址 | 自己托管后 `prdkit demo online <地址>` | 无 | 取决于你的托管方式 |
| GitHub Pages（可选） | `prdkit publish github-pages` | GitHub 令牌 | **任何人**（公开站点） |

## 0. Demo 的三种状态

`spec.demo.mode` 决定 PRD 里的“关联原型”和附录 B 怎么写，全部由 `prdkit links --apply` 生成：

| 状态 | 什么时候 | PRD 里 |
|---|---|---|
| `pending` 待发布（缺省） | 刚生成完，用户还没处理 Demo | **各页面不写“关联原型”行**；附录 B 只写“在线 Demo 发布后，此处将补充各页面的预览链接” |
| `online` 已托管 | 用户把 `prototype/` 托管到某个 https 地址后 | 关联原型写在线链接；附录 B 列各页面链接和在线入口 |
| `local` 本地兜底 | 用户**明确**说不托管 | 关联原型写本地相对路径；附录 B 写“本版未发布在线 Demo”，附 `prototype.zip` |

要点：

- 用户没表态就是 `pending`，**不要替用户选 `local`**，也不要在 PRD 里写本地路径。
- `links --apply` 幂等，随时可在三种状态间切换，PRD 会整体跟着变。
- `lint` 与 `links` 双向保证一致：`pending` 下写了原型地址报 `L-515`；`online` 下仍是本地路径报 `L-510`；`local` 下出现在线链接报 `L-512`。换状态后重跑 `links --apply` 即可。
- 迭代出新版本目录（复制自旧版本）时，先 `prdkit demo reset` 回到 `pending`，再 `links --apply`，避免 PRD 指向旧站点。

顺序固定：**确认 PRD → 处理 Demo（记录在线地址或明确打包）→ `links --apply` → `check prd` 通过**。

## 1. 记录在线 Demo（用户自己托管）

```bash
# 打包 prototype/（排除 screenshots/、.prdkit/），交给用户去托管
python3 scripts/prdkit.py demo pack

# 用户托管完成后，记录地址（必须是 https://，且先做自检：spec 无错误、页面无外链资源）
python3 scripts/prdkit.py demo online https://example.com/my-demo

# 回填 PRD：关联原型 / 附录 B 切换为在线链接（幂等）
python3 scripts/prdkit.py links --apply
python3 scripts/prdkit.py check prd
```

托管要求：

| 要求 | 说明 |
|---|---|
| 入口 | 站点根路径要能打开 `prototype/index.html`（需先运行 `prdkit index` 生成导航页） |
| 内容 | 把 `prototype/` 目录**整个**放上去；各页面通过相对路径互相跳转 |
| 外链 | 原型必须是自包含的，引用 CDN/外链图片字体会被 `check prototype` 报 `PROTO-002` |
| 地址 | 只接受 `https://` 开头的地址；`http://` 会被拒绝 |

可以托管的地方（示例，不限于此）：GitHub Pages、对象存储的静态网站功能、任意带静态目录的 Web 服务器。

### 出错处理

| 现象 | 处理 |
|---|---|
| `demo online` 提示地址需为 https | 让用户换成 `https://` 地址 |
| 提示页面引用了外部资源 | 把外链资源改成本地资源后重试 |
| 提示 `prototype/index.html` 不存在 | 先运行 `prdkit index` |
| zip 超过 100MB | 精简原型里的大文件 |
| 用户暂时没地方托管 | 不阻断：走 §2 本地兜底，之后随时补地址并 `links --apply` |

## 2. 本地兜底（用户明确不托管在线 Demo）

```bash
python3 scripts/prdkit.py demo local       # 记录 spec.demo.mode=local，并打包 <项目名>-<版本>-prototype.zip
python3 scripts/prdkit.py links --apply    # 关联原型写本地路径；附录 B 写本地文件与打开方式
```

PRD 里的呈现：

- 各页面“关联原型”：`` `prototype/pages/list.html` ``（本地相对路径，不是链接）。
- 附录 B：表格列出本地文件，并写明“本版未发布在线 Demo，使用随交付包提供的 `…-prototype.zip`，解压后用浏览器打开 `index.html`”（无需联网、无需服务器，双击即可演示）。
- 页面效果以文中截图为准（截图本来就是 PRD 的主依据，不依赖 Demo 能否打开）。
- 交付给用户时，把 zip 的路径一并告知。

之后用户想补在线 Demo：托管后 `demo online <地址>`，再 `links --apply`，PRD 会整体切到在线链接。

## 3. GitHub Pages 发布器（可选）

一键把 `prototype/` 发布到 GitHub Pages，得到 `https://<账号>.github.io/<仓库>/<子目录>/`。**不是必经路径**；不用它，§1、§2 完整可用。

```bash
python3 scripts/prdkit.py publish github-pages --dry-run                 # 只自检与打包，不联网
python3 scripts/prdkit.py publish github-pages --confirm-public          # 发布（默认专用仓库 + 项目子目录）
python3 scripts/prdkit.py links --apply                                   # 回填 PRD
python3 scripts/prdkit.py check prd
```

### 3.1 公开站点：每次发布都必须确认

GitHub Pages 的站点是**公开**的（免费账号无法限制访问），任何拿到链接的人都能打开。原型里的页面文案、业务规则、界面设计都会被看到。

- 命令级强制：**不带 `--confirm-public` 一律拒绝并打印提示，不联网**。确认不会被记忆，下一次发布还要再带。
- 对话级强制：执行前由 AI 单独发一条公开提示，用户回复“确认公开”后才带这个参数（话术见 `SKILL.md` §4.3）。
- 涉及未发布的业务、需要保密的内容：不要发布，改用打包交付。

### 3.2 仓库与子目录（灵活处理）

| 场景 | 命令 | 结果 |
|---|---|---|
| 默认：多个 Demo 共用一个专用仓库 | `publish github-pages --confirm-public` | 仓库 `<账号>/prd-demos`（不存在就创建为公开仓库），每个 Demo 一个子目录 `<项目名>-<版本>/`，地址 `…/prd-demos/<项目名>-<版本>/` |
| 自定义子目录名 | `--path demo-b` | 同一仓库里多一个子目录，其他 Demo 不受影响 |
| 共用别的仓库 | `--repo 你的账号/别的仓库` | 同上，换一个仓库 |
| 一个 Demo 一个仓库 | `--repo 你的账号/某仓库 --path .` | 文件在站点根目录，地址 `https://<账号>.github.io/某仓库/` |

- 仓库不存在时，只会在**你自己的账号**下自动创建；别人名下的仓库不会创建，请先建好并授权令牌。
- 发布用独立的 `gh-pages` 分支，不动仓库的默认分支；会自动加 `.nojekyll`。
- 如果该仓库的 Pages 已开启但发布源不是 `gh-pages`，命令不会擅自改动现有设置，只会提醒你去 Settings → Pages 调整。

### 3.3 约束（代码已内置，不要绕开）

1. 发布前自检：spec 无错误、页面无外链资源、有 `index.html` 与 `assets/style.css`；不通过则拒绝发布。
2. 目标子目录已有内容时**默认拒绝**；加 `--update` 才会整目录替换，且**只替换这一个子目录**，不动其他 Demo。用根目录模式（`--path .`）加 `--update` 会清除整个 `gh-pages` 分支，AI 不要擅自使用。
3. 令牌只读环境变量 `GITHUB_TOKEN`（或 `GH_TOKEN`），只放请求头，不打印、不写入任何文件。
4. 令牌无效（401）立即停止，不重试。
5. 只请求 `https://api.github.com`；不依赖 `git` 命令或第三方库。
6. 失败不阻断主流程：回退到 §2 打包交付，并如实说明原因。

### 3.4 体验提示

- 推送成功后站点通常要 1~2 分钟才生效，期间链接显示 404 属正常；命令会等待最多 2 分钟，超时会如实提示。
- 地址记录进 PRD 之后，评审人点链接即可体验。想下线，删除仓库里对应子目录或整个仓库即可；但链接可能已被保存或被搜索引擎收录。

### 3.5 自己写发布器

发布器放在 `scripts/publishers/`，把“打包好的原型”推到某个托管服务，成功后调用 `lib.demo.record_online()` 写回地址。约定：

1. 凭证只从环境变量读取，不打印、不写入 spec、日志、`.prdkit/` 或 PRD。
2. 默认不覆盖已有站点；覆盖必须由用户明确选择。
3. 发布前先过 `demo.precheck()`，失败则拒绝发布。
4. 失败不阻断主流程：回退到打包交付，并如实说明原因。
5. 站点公开与否要对用户讲清楚，必要时同样加“确认”参数。

## 4. 凭证：缺失时先告知，征得同意再指引

**只在用户选用 GitHub Pages 发布器时才检测**，开场和生成阶段不要提。检测用 `prdkit doctor`（只显示“已配置/未配置”，不显示内容）。

缺失时按这个顺序说，**同意前不要贴申请步骤**：

1. 说明缺什么、对应什么功能（一键发布到 GitHub Pages）。
2. 说明没有它的影响（不能一键发布；可以改用打包交付，评审人解压后双击 `index.html` 即可演示）。
3. 问用户“要我告诉你怎么申请吗？”并给预估耗时（约 3 分钟）。
4. 用户同意后，再给下面的步骤；用户不同意就走打包交付，不反复劝。

### 申请 GitHub 令牌（推荐顺序：先建仓库，再建令牌）

**给用户指引时，每一步需要打开的页面都必须带直达链接**（每个链接单独成行，不加反引号，IDE 里才能直接点；需要先登录 GitHub），不要让用户自己去找 GitHub。**凡是让用户复制的命令，一律用独占一行的代码块**，命令本身逐字照搬，不要改成行内代码，也不要拆开。

**第 1 步：先建好专用仓库 `prd-demos`**（账号下已有就跳过）。令牌只授权单个仓库时，GitHub 界面里只能选到已经存在的仓库，所以要先建：

https://github.com/new?name=prd-demos&visibility=public

名称保持 `prd-demos`，**必须选公开（Public）**：GitHub Pages 站点本来就是公开的，而且 GitHub Free 账号只能为公开仓库开启 Pages（官方文档原文：GitHub Free 仅支持公开仓库，Pro / Team / Enterprise 才支持私有仓库）。选了私有，令牌即使授权了它，发布时也可能在开启 Pages 那一步失败。

**第 2 步：创建令牌**

- 细粒度令牌（推荐）：https://github.com/settings/personal-access-tokens/new
- 经典令牌：https://github.com/settings/tokens/new

| 项 | 建议 |
|---|---|
| 有效期 | 30 天或更短（用完可作废） |
| Resource owner | **仓库所在的个人账号**（不要选组织；选错了令牌看不到这个仓库） |
| 仓库范围 | **只授权 `prd-demos` 这一个仓库**（Only select repositories） |
| Repository permissions | **Contents: Read and write**、**Pages: Read and write**、Metadata: Read |

用经典令牌也可以：仓库是公开的，勾选 `public_repo` 即可；仓库是私有的，必须勾选 `repo`（并且账号要是付费套餐，才能为私有仓库发布 Pages）。

**说明**：仓库已存在时发布器直接使用；仓库不存在且令牌有创建权限时会自动创建；令牌没有创建权限时，发布器会提示“先建好仓库再重试”，并给出上面的建仓链接。创建个人仓库所需的确切权限名尚未核实，所以不要求用户额外授予“创建仓库”类权限，也不要求选 All repositories。

英文会话里这些步骤的措辞见 `references/messages.en.md` 的 `S-TOKEN-GUIDE`。

**第 3 步：把令牌配置到运行命令的那台机器上**（**不要把令牌发到聊天、截图或写进项目文件**）：

```bash
echo 'export GITHUB_TOKEN="你的令牌"' >> ~/.bashrc
```

使用 zsh 的话，把命令里的 `~/.bashrc` 换成 `~/.zshrc`。

**第 4 步**：配好后回复“好了”，我检查并发布。

- AI 通过非交互 shell 执行时不会自动加载 `~/.bashrc`；prdkit 会以纯文本方式读取其中的 `export` 行（不执行文件），所以配好即可用。
- 同一变量重复 export 时以最后一行为准；`doctor` 会提示重复，建议清理旧行。
- 令牌一旦暴露（贴到聊天、截图、提交到仓库），立刻到 GitHub 作废并重新申请。
- prdkit 不会把令牌写入 spec、日志、`.prdkit/` 或 PRD。
