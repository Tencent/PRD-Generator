# 原型设计规范与视觉风格

原型的作用是让评审者**看得懂页面怎么用**，并产出可截图的页面。规范只保留会影响结果的几条，其余交给判断。

## 1. 绘制要求

| 项 | 要求 |
|---|---|
| 内容 | 用真实、贴合业务的文案和数据（“博世电钻 · 3 栋王姐 · 200 米”），不用 Lorem、“按钮1”、“标题” |
| 颜色 | 一律用 `var(--color-…)` 变量，不写死十六进制色值，否则换风格、换主色时这个页面不会变 |
| 组件 | 优先用基础样式里已有的类，移动端：`nav-bar`、`card`、`btn`、`input`、`tag`、`tab-bar`、`modal-overlay`/`modal-content`、`toast`、`empty-state`；PC 后台：`desktop-frame`、`sidebar`、`topbar`、`breadcrumb`、`page-body`、`panel`、`stat`、`filter-bar`、`select`、`table`、`pagination`、`form-row`、`tabs`、`dialog` |
| 骨架 | 新页面从模板起步：移动端 `templates/page-mobile.html`，PC 后台 `templates/page-desktop.html`（视口 1440，spec 里写 `viewport:{"width":1440,"height":900,"dpr":1}`） |
| 交互 | 页面引用 `../assets/interaction.js`（`style apply` 时自动放入项目），用属性声明交互，不必自己写脚本：`data-open="#id"` 开弹窗、`data-close` 关闭、`data-toast="文案"`、`data-go`、`data-tabs`/`data-tab`/`data-panel` 切页签、`data-state="empty"`/`data-state-not="empty"` 配合 `?s=empty` 呈现状态、`?open=%23id` 直接打开弹窗 |
| 技术栈 | 纯 HTML + CSS + 原生 JS，不引入框架、CDN 和外链图片/字体 |
| 状态 | 业务里有的状态都要能呈现：默认、空态、异常、加载、成功；每个状态都要能被 `spec/screens.json` 触达 |
| 可触达 | 页面状态用 URL 参数切换（`?s=empty`），弹窗用 `actions` 里的 `click` 或 `eval` 触发，保证 `prdkit shot` 能自动截到 |
| 可点击 | 页面间跳转用 `<a href>`，让评审者在浏览器里能点着走一遍 |

项目里的页面不必受限于基础样式：**需要特殊组件或特殊视觉时，直接在页面或项目 `style.css` 里写**，只要仍用变量取色，风格切换就依然有效。

## 2. 视觉风格

### 2.1 内置风格（4 个）

用 `prdkit.py style list` 查看。风格只改表面：颜色、阴影、圆角、边框、背景，不改布局。

| 风格 | 特点 | 适合 |
|---|---|---|
| `flat` 扁平（默认） | 纯色块、无阴影、小圆角 | 工具、后台、信息密集型 |
| `glass` 毛玻璃 | 半透明加模糊、渐变背景、大圆角、内高光 | C 端、重氛围和品质感 |
| `soft` 柔和圆润 | 大圆角、浅色渐变底、柔和彩色阴影 | 生活服务、社区、多数 C 端 |
| `dark` 深色 | 深底浅字、描边卡片、发光按钮 | 科技、工具、夜间场景 |

毛玻璃是 CSS 的静态近似，没有 iOS 26 Liquid Glass 的动态折射和滚动形变。

### 2.2 颜色与风格是两件独立的事

- **风格**管“质感”：扁平、毛玻璃、柔和、深色。内置 4 个，见 2.1。
- **颜色**管“调性”：主色（再加必要的辅色）。**任何风格都可以配任何颜色**，两者互不绑定。
- skill 不内置任何固定配色方案，也不把某种颜色搭配当成默认答案。示例图里的蓝色只是为了展示风格差异的占位色。

主色按下面的优先级确定，高优先级命中就不再往下走：

| 优先级 | 来源 | 做法 |
|---|---|---|
| 1 | 用户明确指定（色值、色名、“黑红”“偏稳重”等描述） | 直接采用，不再追问；描述性要求（如“黑色加红色”）由你落成具体色值，并在方案里写明 |
| 2 | 业务已有的设计：品牌规范、Figma、历史 PRD / 原型、线上产品截图、同系列项目的 `prototype/assets/style.css` 或 `spec/screens.json` 的 `style` | 读取并提取主色、辅色、明暗倾向，沿用；在方案里写明“依据哪份材料”，让用户一眼能纠正 |
| 3 | 都没有 | 根据业务领域、目标用户和产品调性，自己判断并推荐 2-3 个候选主色，每个给一句理由，让用户选；用户说“你定”就用第一推荐 |

要点：

- 推荐要有理由，来自业务本身（行业气质、用户心智、使用场景、对同类产品的认知），不是套表。
- 配色超出“一个主色”的需求（如深色主体加红色点缀、双品牌色），直接让 AI 改项目里的 `prototype/assets/style.css`，不增加 skill 的风格或参数。
- 品牌色接近红色或绿色时，主色会让 `tag--primary` 与表示错误/成功的标签颜色混淆（如红色主色下“配送中”和“已退款”都偏红）。此时让 AI 在项目 `style.css` 里单独调整状态标签的颜色，保证状态一眼可分。
- 选定后用 `--source` 记录依据，写进 spec 的 `style.source`，后续改版或同系列项目可直接继承。
- 给定主色色值后，浅色、深色、浅底会自动派生，无需再选。

### 2.3 视觉确认闸门

```
1. 确定主色（见 2.2），并在方案里写明颜色与依据
2. prdkit.py style preview                                取出 skill 自带的固定对比图（APP 一张、PC 一张），看风格质感
3. 在 IDE 预览窗打开对比图（prdkit view --style 给出 http 地址，用 preview_url 打开）；对话里同时给图片的反引号绝对路径
4. 用户选风格（回复编号即视为确认并开始生成，主色不满意直接说）
5. prdkit.py style apply <风格名> --accent #色值 --source "依据"   应用到项目并写入 spec
6. prdkit.py style preview <风格名> --accent #色值         出真实配色效果图存入项目（不打断用户，不是新的确认关卡）
```

- **必须让用户亲眼看到对比图**：运行 `prdkit view --style`（对比图在项目 `.prdkit/style-preview/`，它会起本机预览服务并打印 http 地址），用 IDE 的 `preview_url` 在预览窗打开；对话里同时给图片的**反引号绝对路径**（单独成行），打不开预览窗时用户点路径也能看。**不要用 `[文字](地址)` 或 `file:///` 链接**（IDE 会转成 vscode-resource 虚拟域名，浏览器打不开）。先展示图，再列风格选项，每个选项只写一行特点。
- 固定对比图是**随 skill 发布的固定文件**（`templates/styles/preview/app.png`、`pc.png`），不现场渲染：同一份示例内容套 4 种风格，用户看的是质感差异。平台是 PC 后台（`platform` 为 `web`/`admin`）时只出 PC 图，移动端平台只出 APP 图，未登记平台则两张都出。
- 第 6 步才是用户真正的配色效果，不要拿固定图里的蓝色当结论。若用户看了不满意，换色成本低（`style apply` 后重跑 `shot`、`flow`，见 `revision.md`）。
- 用户说“你定”“快一点”：跳过 2–4 的选项列表，风格用 `flat`，主色仍按 2.2 的优先级确定，并一句话告知用户所选风格与主色。
- `style apply` 不带 `--accent` 时只是通用蓝色占位，命令会提示确认。
- 项目已有 `spec.style` 时，`prdkit.py style apply`（不带参数）会沿用它重新生成样式。
- 预览文件默认复制到项目的 `.prdkit/style-preview/`，不会混进交付物。
- 应用风格 = 把基础样式、主色、风格拼成项目自己的 `prototype/assets/style.css`，并放入 `interaction.js`。此后项目**不再引用 skill 目录**，所以 skill 装在哪都不影响已生成的原型。
- 维护者改过 `templates/` 下的样式后，运行 `prdkit.py style build-preview` 重新生成固定对比图；`tests/regress.py` 会检查是否过期（`style check-preview`）。

### 2.4 用户对内置风格都不满意

直接让 AI 修改项目里的 `prototype/assets/style.css`，或整体重写，**没有格式限制**。只需要做到：

1. 页面仍用 `var(--color-…)` 取色，方便后续调整。
2. 改完重新运行 `prdkit.py shot` 和 `flow`，截图和流程图自动更新。

改风格不会让截图与流程图不一致，因为它们都是命令按页面实时生成的。

## 3. 完成后自查

- `prdkit.py spec`：页面登记与原型文件一一对应。
- `prdkit.py shot`：全部页面截图成功。
- `prdkit.py check prototype`：原型质量闸门，会同时查写死色值（PROTO-001）、外链（PROTO-002）、是否引用样式（PROTO-003）、页面脚本报错（PROTO-011）。
- 原型里的页面跳转与 spec 流转一致：`check prototype` 会查 `PROTO-020`（原型有跳转、流转没连线，error）、`PROTO-021`（流转有连线、原型没入口，warn）、`PROTO-022`（死链，error）。识别 `<a href>`、`data-go`、`onclick`/脚本里的 `location.href`；返回键、底部 Tab、PC 侧栏/顶栏/面包屑不要求画进图；示意链接加 `data-flow-ignore`。
- `prdkit.py index`：由 spec 生成 `prototype/index.html` 导航页（每个页面文件一个入口，状态和弹窗挂在卡片下）；页面增删后重新运行，不要手改。
- 打开 1-2 张截图，肉眼确认：文字没被遮挡、按钮可读、弹窗与背景有层次。

## 4. 维护者：风格 CSS 的颜色规则

风格里的彩色必须来自主色变量（`var(--color-primary…)` 或 `rgba(var(--color-primary-rgb), a)`），否则换主色后会残留一块固定颜色。允许写字面量的只有：白/黑/灰、状态语义色（橙/红/绿）、`:root` 里对设计令牌的定义、深色风格里的深色表面。

`prdkit.py style check-css` 会扫描；`build-preview` 在发现违规时会拒绝生成，回归也会检查。
