#!/usr/bin/env python3
# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""prdkit —— PRD Generator 统一命令入口。

用法：
  python3 prdkit.py doctor [--brief]                 环境体检；--brief 只给开场巡检用的两行状态
  python3 prdkit.py setup  [--yes]                    安装缺失的截图组件：不加 --yes 只预演；用户明确同意后才加 --yes
  python3 prdkit.py init   <项目目录名> --name 产品名 --platform miniprogram|h5|app|web|admin [--version V1.0]
                                                      新建项目骨架（目录 + 空 spec）
  python3 prdkit.py where  [--project X]              显示解析到的 skill/工作区/项目路径
  python3 prdkit.py spec   [--project X]              校验 spec（页面登记与流转图）
  python3 prdkit.py shot   [--project X] [--only a,b] [--chapter 3.1] [--dpr 2]
                                                      按 spec 对页面状态/弹窗截图 → images/
  python3 prdkit.py migrate [--project X] [--force]   旧 flowmap-config.json → 新 spec

  python3 prdkit.py flow   [--project X] [--scope 3.1] [--check-only] [--table] [--transit] [--draft]
                                                      渲染流程图并自检 / 由流转关系生成页面清单表
  python3 prdkit.py lint   [--project X] [--md file]  PRD 机器校验

  python3 prdkit.py style  list                       列出内置视觉风格
  python3 prdkit.py style  preview [--out DIR]        取出 skill 自带的固定风格对比图（APP + PC 各一张），供用户看图选择
  python3 prdkit.py style  preview <风格名> --accent #色值
                                                      只渲染所选风格 + 真实主色的效果图（几秒），确认配色用
  python3 prdkit.py style  apply [风格名] [--accent #色值] [--source 依据] [--project X]
                                                      应用风格与主色到项目原型，并记录到 spec；省略风格名则沿用 spec 里已确认的 style
  python3 prdkit.py style  build-preview              （维护者）改过样式后重新生成固定对比图
  python3 prdkit.py style  check-css                  （维护者/回归）风格 CSS 的彩色必须来自主色变量
  python3 prdkit.py style  check-preview              （维护者/回归）检查固定对比图是否与当前样式一致
  python3 prdkit.py check  <闸门|all> [--project X]   质量闸门：env/map/style/prototype/flow/prd；
                                                      每个给用户确认的节点前先跑，错误清零才能交给用户
  python3 prdkit.py index  [--project X]              由 spec 生成 prototype/index.html 导航页
  python3 prdkit.py view   [--demo|--style|--bundle] [--stop]  起本机预览服务（127.0.0.1，UTF-8）：默认/--demo 返回交互 Demo 的 http 地址；--style 返回风格对比页；--bundle 返回单文件 Demo 的自动打开地址；--stop 关闭服务
  python3 prdkit.py open   [文件]                     在 IDE 编辑器里打开 PRD（默认项目里的 *-prd.md）；环境不支持时静默降级，只给路径

  python3 prdkit.py bundle [--out 文件] [--no-verify]  把 prototype/ 打成【单文件】<名称>-<版本>-demo.html：不依赖服务/端口/网络，页面切换在文件内完成，IDE 预览窗与浏览器都能点
  python3 prdkit.py demo   pack [--out 文件]          只打包 prototype（排除 screenshots/、.prdkit/）
  python3 prdkit.py demo   local                      用户明确不托管在线 Demo：记录为本地兜底，并打包 prototype.zip 随交付包提供
  python3 prdkit.py demo   online <https 地址>         用户自己托管 prototype/ 后，记录在线 Demo 地址
  python3 prdkit.py demo   reset                      迭代出新版本目录后，把 Demo 重置为“待发布”（不再指向旧站点）
  python3 prdkit.py demo   status                     查看 Demo 状态（待发布 / 在线 / 本地兜底）
  python3 prdkit.py publish github-pages --confirm-public [--repo 用户/仓库] [--path 子目录] [--update] [--dry-run] [--no-wait]
                                                      （可选）一键发布到 GitHub Pages：默认专用仓库 <账号>/prd-demos、每个 Demo 一个子目录；
                                                      --repo 你/某仓库 --path . 即“一个 Demo 一个仓库”；公开站点，每次都必须带 --confirm-public；需要 GITHUB_TOKEN
  python3 prdkit.py links  [--apply]                  由 spec 生成各页面“关联原型”行与附录 B（预览 / 写回 PRD）；Demo 待发布时不写地址

--project 可以是：项目版本目录的路径，或项目名（在 PRD 根目录里搜索）；省略时自当前目录向上寻找。
PRD 根目录可用环境变量 PRDKIT_PRD_ROOT 或工作区下的 .prdkit.json {"prd_root": "..."} 指定。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import common  # noqa: E402
from lib import i18n  # noqa: E402

common.force_utf8()


HELP_EN = {
    "PRD Generator 统一命令入口": "PRD Generator unified command entry",
    "仅用于没有项目的命令（doctor / setup）的输出语言；有项目时以 spec.lang 为准": "Output language for commands without a project (doctor / setup); when a project exists spec.lang wins",
    "项目目录路径或项目名；省略则自当前目录向上寻找": "Project directory path or project name; if omitted, search upwards from the current directory",
    "PRD 根目录（可选，覆盖自动探测）": "PRD root directory (optional, overrides auto-detection)",
    "环境体检": "Environment check",
    "只输出两行机器可读状态（ENV=…、SYSTEM_BROWSER=…），开场巡检用": "Print only two machine-readable lines (ENV=…, SYSTEM_BROWSER=…), used by the opening check",
    "安装缺失的截图组件（不加 --yes 只预演；必须用户同意后才加 --yes）": "Install the missing screenshot components (without --yes it is a dry run; add --yes only after the user agrees)",
    "用户已明确同意安装；没有这个参数绝不安装任何东西": "The user has explicitly agreed to install; nothing is ever installed without this flag",
    "新建项目骨架（目录 + 空 spec）": "Create a project skeleton (directories + empty spec)",
    "项目目录名：小写英文/数字/连字符，如 quiz-challenge": "Project directory name: lowercase letters, digits, hyphens, e.g. quiz-challenge",
    "产品中文名": "Product name",
    "项目语言：zh（默认，中文 PRD）/ en（英文 PRD）。写入 spec.lang，之后所有命令按它输出": "Project language: zh (default, Chinese PRD) / en (English PRD). Written to spec.lang; every later command follows it",
    "PRD 根目录（默认 <工作区>/.codebuddy/docs/prd）": "PRD root directory (default <workspace>/.codebuddy/docs/prd)",
    "显示解析到的路径": "Show the resolved paths",
    "校验 spec": "Validate the spec",
    "按 spec 截图": "Take screenshots from the spec",
    "只截指定页面 id，逗号分隔": "Only these page ids, comma separated",
    "只截某一章": "Only one chapter",
    "像素比，默认取 spec.viewport.dpr（通常 2）": "Pixel ratio; defaults to spec.viewport.dpr (usually 2)",
    "旧 flowmap-config.json → 新 spec": "Legacy flowmap-config.json -> new spec",
    "覆盖已有 spec": "Overwrite an existing spec",
    "PRD 机器校验（格式/结构/图文一致/可交付）": "Machine check of the PRD (format / structure / text-image consistency / deliverability)",
    "指定 PRD 文件（默认取项目目录下的 *-prd.md）": "PRD file to check (default: *-prd.md in the project directory)",
    "同时显示 info 级提示": "Also show info-level hints",
    "渲染页面流转图并自检": "Render the page-flow diagrams and self-check them",
    "只处理某一章（如 3.1）或 all": "Only one chapter (e.g. 3.1) or all",
    "只做几何自检，不输出 PNG": "Only run the geometry self-check, write no PNG",
    "改为打印由流转关系生成的“页面清单”Markdown 表": "Print the Markdown page-list table generated from the flows instead",
    "打印由流转关系生成的各页面“流转”行草稿（PRD 直接引用，避免图文不一致）": "Print the draft \"Flow\" line of every page generated from the flows (use it in the PRD directly to avoid text-image mismatches)",
    "页面地图草案：不要求原型和截图已存在，节点画成“待绘制”，供用户先确认流转": "Page-map draft: no prototype or screenshots required; nodes are drawn as \"to be drawn\" so the user can confirm the flow first",
    "视觉风格：列出 / 预览对比 / 应用": "Visual style: list / compare previews / apply",
    "apply 时的风格名": "Style name for apply",
    "主色（可选，6 位十六进制，如 #E5352B）；不指定则为通用蓝占位。颜色与风格相互独立": "Accent colour (optional, 6-digit hex such as #E5352B); a generic blue placeholder is used otherwise. Colour and style are independent",
    "apply 时记录配色/风格的依据（如“用户指定”“取自品牌规范”“业务调性推荐”）": "Basis of the colour/style recorded by apply (e.g. \"user specified\", \"from the brand guide\", \"recommended for the business tone\")",
    "preview 的输出目录（默认：项目的 .prdkit/style-preview，找不到项目则为 ./style-preview）": "Output directory of preview (default: .prdkit/style-preview of the project, or ./style-preview without a project)",
    "质量闸门：自检并给出分级修复建议": "Quality gate: self-check and give graded fix suggestions",
    "闸门名；all 依次检查，遇到未通过的就停": "Gate name; all checks them in order and stops at the first failure",
    "生成原型导航页 prototype/index.html": "Generate the prototype index page prototype/index.html",
    "起本机预览服务：交互 Demo / 风格对比图（IDE 预览窗和浏览器都能打开）": "Start the local preview server: interactive demo / style comparison (works in IDE preview panes and browsers)",
    "返回交互 Demo（prototype/index.html）的预览地址（默认）": "Return the preview address of the interactive demo (prototype/index.html) (default)",
    "改为展示风格对比图（需先运行 style preview）": "Show the style comparison instead (run style preview first)",
    "返回单文件 Demo（prdkit bundle 生成）的自动打开地址": "Return the auto-open address of the single-file demo (made by prdkit bundle)",
    "关闭本机预览服务": "Stop the local preview server",
    "在 IDE 编辑器里打开 PRD 或指定文件": "Open the PRD or a given file in the IDE editor",
    "要打开的文件；省略则打开项目里的 PRD": "File to open; the project's PRD if omitted",
    "把原型打成单文件 demo.html（不依赖服务，IDE 预览与浏览器通用）": "Pack the prototype into a single demo.html (no server needed; works in IDE previews and browsers)",
    "输出文件（默认：项目目录下 <名称>-<版本>-demo.html）": "Output file (default: <name>-<version>-demo.html in the project directory)",
    "跳过无头浏览器自检": "Skip the headless-browser self-check",
    "Demo 交付状态：打包 / 本地兜底 / 记录在线地址 / 重置": "Demo delivery state: pack / local fallback / record an online address / reset",
    "online 时的 https 在线地址": "https address for online",
    "pack 的输出文件": "Output file of pack",
    "（可选）一键发布到 GitHub Pages：公开站点，需 GITHUB_TOKEN 与 --confirm-public": "(Optional) publish to GitHub Pages in one step: a public site, needs GITHUB_TOKEN and --confirm-public",
    "目标仓库 用户/仓库；省略则用 <你的账号>/prd-demos（不存在会创建为公开仓库）": "Target repository user/repo; defaults to <your account>/prd-demos (created as a public repository if missing)",
    "站点子目录，默认 <项目名>-<版本>；'.' 表示站点根目录（一个 Demo 一个仓库时用）": "Site sub-directory, default <project>-<version>; '.' means the site root (one demo per repository)",
    "用户已明确确认：这是公开站点，任何人拿到链接都能打开。每次发布都必须带": "The user has explicitly confirmed this is a public site that anyone with the link can open. Required on every publish",
    "目标目录已有内容时整目录替换（默认拒绝，防误覆盖）": "Replace the whole target directory when it already has content (refused by default to avoid overwriting)",
    "只做自检与打包，不联网": "Only self-check and pack; no network",
    "不等待站点生效": "Do not wait for the site to go live",
    "由 spec 生成“关联原型”行与附录 B": "Generate the \"Prototype\" lines and Appendix B from the spec",
    "写回 PRD；不加则只预览": "Write back to the PRD; without it only a preview is shown"
}


def _h(zh):
    """argparse 帮助文本：中文为默认，项目语言/--lang 为 en 时取英文。"""
    return i18n.t(zh, HELP_EN.get(zh))


def _project(args):
    try:
        proj = common.resolve_project(args.project, prd_root=getattr(args, "prd_root", None))
    except common.ProjectNotFound as e:
        print(f"❌ {e}")
        raise SystemExit(2)
    i18n.set_lang(proj.lang)
    if proj.note:
        print(f"ℹ️  {proj.note}")
    return proj


def cmd_doctor(args):
    from lib import doctor
    if args.brief:
        return doctor.brief()
    return doctor.run()


def cmd_setup(args):
    from lib import setup
    return setup.run(yes=args.yes)


def cmd_where(args):
    ws = common.find_workspace()
    print(i18n.t(f"skill 目录 : {common.SKILL_DIR}", f"skill dir   : {common.SKILL_DIR}"))
    print(i18n.t(f"工作区     : {ws}", f"workspace   : {ws}"))
    print(i18n.t("PRD 根候选 :", "PRD roots   :"))
    for r in common.prd_roots(ws, args.prd_root):
        print(f"  {'✔' if r.exists() else '·'} {r}")
    try:
        proj = common.resolve_project(args.project, prd_root=args.prd_root)
        print(i18n.t(f"项目目录   : {proj.root}", f"project     : {proj.root}"))
        if i18n.cur() == "en":
            print(f"  spec     : {'yes' if proj.screens_path.exists() else 'no'}    prototype: {'yes' if proj.proto.is_dir() else 'no'}    PRD: {proj.prd_md() or 'none'}")
        else:
            print(f"  spec     : {'有' if proj.screens_path.exists() else '无'}    原型: {'有' if proj.proto.is_dir() else '无'}    PRD: {proj.prd_md() or '无'}")
    except common.ProjectNotFound as e:
        print(i18n.t(f"项目目录   : 未定位（{str(e).splitlines()[0]}）", f"project     : not located ({str(e).splitlines()[0]})"))
    return 0


def cmd_spec(args):
    from lib import spec
    proj = _project(args)
    issues, screens = spec.validate_all(proj)
    for i in issues:
        print(i)
    errs = sum(1 for i in issues if i.level == "error")
    warns = sum(1 for i in issues if i.level == "warn")
    print(i18n.t(f"\n页面 {len(screens)} 个，流程图 {len(proj.flow_files())} 张 —— {errs} 个错误，{warns} 个提醒",
                 f"\n{len(screens)} pages, {len(proj.flow_files())} flow diagrams -- {errs} errors, {warns} warnings"))
    return 1 if errs else 0


def cmd_shot(args):
    from lib import shot
    proj = _project(args)
    only = [x.strip() for x in args.only.split(",")] if args.only else None
    ok, failed = shot.take_shots(proj, only=only, chapter=args.chapter, dpr=args.dpr)
    print(i18n.t(f"\n完成：成功 {ok}，失败 {len(failed)}", f"\nDone: {ok} succeeded, {len(failed)} failed"))
    return 1 if failed else 0


def cmd_migrate(args):
    from lib import migrate
    proj = _project(args)
    n_screens, n_edges, notes = migrate.convert(proj, force=args.force)
    print(i18n.t(f"✅ 已生成 spec：页面 {n_screens} 个，连线 {n_edges} 条 → {proj.spec_dir}",
                 f"✅ Spec generated: {n_screens} pages, {n_edges} edges -> {proj.spec_dir}"))
    for n in notes:
        print(i18n.t(f"  待人工处理：{n}", f"  Needs manual work: {n}"))
    print(i18n.t("下一步：补全 chapters / screens 的章节归属，然后运行 spec 校验。",
                 "Next: fill in the chapter of every chapters / screens entry, then run the spec check."))
    return 0


def cmd_flow(args):
    from lib import flow
    proj = _project(args)
    if args.transit:
        flow.print_transit(proj, scope=args.scope)
        return 0
    if args.table:
        flow.print_tables(proj, scope=args.scope, draft=args.draft)
        return 0
    issues, outs = flow.render_all(proj, scope=args.scope, check_only=args.check_only, draft=args.draft)
    if args.draft and outs:
        print(i18n.t(f"\n页面地图草案已输出到：{proj.state / 'draft'}（请先给用户确认章节、页面与流转，再画原型）",
                     f"\nThe page-map draft was written to: {proj.state / 'draft'} (have the user confirm chapters, pages and flows before drawing the prototype)"))
    errs = sum(1 for i in issues if i.level == "error")
    print(i18n.t(f"\n完成：输出 {len(outs)} 张，{errs} 个错误，{len(issues) - errs} 个提醒",
                 f"\nDone: {len(outs)} image(s) written, {errs} errors, {len(issues) - errs} warnings"))
    return 1 if errs else 0


def cmd_lint(args):
    from lib import lint
    proj = _project(args)
    issues, md = lint.run(proj, md_path=args.md)
    order = {"error": 0, "warn": 1, "info": 2}
    for i in sorted(issues, key=lambda x: (order[x.level], x.code)):
        if i.level == "info" and not args.verbose:
            continue
        print(i)
    sc, errs, warns = lint.score(issues)
    print(i18n.t(f"\nPRD：{md}", f"\nPRD: {md}") if md else "")
    print(i18n.t(f"机器校验得分：{sc}/100 —— {errs} 个错误，{warns} 个提醒（语义类质检需 AI 另行判断，见 references/qa-semantic.md）",
                 f"Machine check score: {sc}/100 -- {errs} errors, {warns} warnings (semantic checks need the AI, see references/qa-semantic.md)"))
    return 1 if errs else 0


def cmd_style(args):
    from lib import style
    if args.action in ("list", "check-preview", "check-css"):         # 这几个动作不需要项目；找得到项目就按项目语言输出
        try:
            i18n.set_lang(common.resolve_project(args.project, prd_root=getattr(args, "prd_root", None)).lang)
        except common.ProjectNotFound:
            pass
    try:
        if args.action == "list":
            return style.cmd_list()
        if args.action == "preview":
            out, platform = args.out, None
            try:
                proj = common.resolve_project(args.project, prd_root=getattr(args, "prd_root", None))
                i18n.set_lang(proj.lang)
                if proj.screens_path.exists():
                    platform = proj.load_screens().get("platform")
                out = out or str(proj.state / "style-preview")
            except common.ProjectNotFound:
                pass
            if args.name or args.accent:
                return style.preview_custom(out or "style-preview", args.name or style.DEFAULT_STYLE, accent=args.accent, platform=platform)
            return style.preview(out or "style-preview", platform=platform)
        if args.action == "build-preview":
            return style.build_preview(lang=i18n.cur())
        if args.action == "check-css":
            bad = style.scan_fixed_colors()
            for st, no, col, text in bad:
                print(i18n.t(f"❌ {st}.css:{no}  固定彩色 {col}  {text}", f"❌ {st}.css:{no}  fixed colour {col}  {text}"))
            print(i18n.t("✅ 风格 CSS 的彩色全部来自主色变量或为允许的固定色", "✅ All colours in the style CSS come from the accent variables or are allowed fixed colours") if not bad
                  else i18n.t(f"共 {len(bad)} 处；彩色应改用 var(--color-primary…) 或 rgba(var(--color-primary-rgb), a)",
                              f"{len(bad)} place(s); use var(--color-primary…) or rgba(var(--color-primary-rgb), a) for colours"))
            return 1 if bad else 0
        if args.action == "check-preview":
            ok, msg = style.preview_status()
            print(("✅ " if ok else "❌ ") + msg)
            return 0 if ok else 1
        if args.action == "apply":
            return style.apply(_project(args), args.name, accent=args.accent, source=args.source)
    except ValueError as e:
        print(f"❌ {e}")
        return 2


def cmd_index(args):
    from lib import index, spec
    proj = _project(args)
    issues, _ = spec.validate_screens(proj, draft=True)
    errs = [i for i in issues if i.level == "error"]
    if errs:
        for i in errs:
            print(i)
        print(i18n.t("spec 存在错误，已中止。", "The spec has errors; aborted."))
        return 1
    out, n = index.build(proj)
    print(i18n.t(f"✅ 已生成 {out.relative_to(proj.root)}（{n} 个页面文件）", f"✅ Generated {out.relative_to(proj.root)} ({n} page files)"))
    return 0


def cmd_view(args):
    from lib import view
    return view.cmd_view(_project(args), style=args.style, demo=args.demo, stop_server=args.stop, bundle=args.bundle)


def cmd_bundle(args):
    from lib import bundle
    return bundle.cmd_bundle(_project(args), out=args.out, do_verify=not args.no_verify)


def cmd_open(args):
    from lib import view
    return view.cmd_open(_project(args), args.file)


def cmd_check(args):
    from lib import check
    if args.stage == "env" and not args.project:
        try:
            proj = common.resolve_project(None, prd_root=getattr(args, "prd_root", None))
        except common.ProjectNotFound:
            proj = None   # 环境闸门在建项目之前运行，不需要项目
        return check.run(proj, "env")
    return check.run(_project(args), args.stage)


def cmd_demo(args):
    from lib import demo
    proj = _project(args)
    act = args.action
    if act == "local":
        return demo.cmd_local(proj)
    if act == "reset":
        return demo.cmd_reset(proj)
    if act == "pack":
        return demo.cmd_pack(proj, out=args.out)
    if act == "online":
        if not args.url:
            print(i18n.t("❌ online 需要在线地址：prdkit.py demo online <https 地址>", "❌ online needs an address: prdkit.py demo online <https address>"))
            return 2
        return demo.cmd_online(proj, args.url)
    return demo.cmd_status(proj)


def cmd_publish(args):
    from publishers import github_pages
    proj = _project(args)
    return github_pages.cmd_publish(proj, repo=args.repo, path=args.path, confirm_public=args.confirm_public,
                                    update=args.update, dry_run=args.dry_run, no_wait=args.no_wait)


def cmd_links(args):
    from lib import links
    proj = _project(args)
    _, changes = links.apply(proj, write=args.apply)
    if not changes:
        print(i18n.t("✅ 关联原型与附录 B 已与 spec 一致，无需改动。", "✅ The prototype lines and Appendix B already match the spec; nothing to change."))
        return 0
    for c in changes:
        print((i18n.t("已写入：", "Written: ") if args.apply else i18n.t("将改动：", "Will change: ")) + c)
    if not args.apply:
        print(i18n.t("\n以上只是预览；确认后加 --apply 写回 PRD。", "\nThis is only a preview; add --apply to write it back to the PRD."))
    return 0


def cmd_init(args):
    from lib import init
    lang = args.lang or getattr(args, "ui_lang", None) or i18n.from_env()
    i18n.set_lang(lang)
    return init.run(args.dir_name, args.name, args.platform, version=args.version, root=args.root, lang=lang)


def main(argv=None):
    _argv = list(sys.argv[1:] if argv is None else argv)
    for _i, _a in enumerate(_argv[:-1]):          # 建 parser 之前先确定语言，--help 才能按语言输出
        if _a == "--lang" and _argv[_i + 1] in ("zh", "en"):
            i18n.set_lang(_argv[_i + 1])
            break
    else:
        i18n.set_lang(i18n.from_env())
    ap = argparse.ArgumentParser(prog="prdkit", description=_h("PRD Generator 统一命令入口"))
    ap.add_argument("--lang", dest="ui_lang", choices=["zh", "en"], help=_h("仅用于没有项目的命令（doctor / setup）的输出语言；有项目时以 spec.lang 为准"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        return sp

    def proj_opts(sp):
        sp.add_argument("--project", "-p", help=_h("项目目录路径或项目名；省略则自当前目录向上寻找"))
        sp.add_argument("--prd-root", help=_h("PRD 根目录（可选，覆盖自动探测）"))

    sp = add("doctor", cmd_doctor, _h("环境体检"))
    sp.add_argument("--brief", action="store_true", help=_h("只输出两行机器可读状态（ENV=…、SYSTEM_BROWSER=…），开场巡检用"))
    sp = add("setup", cmd_setup, _h("安装缺失的截图组件（不加 --yes 只预演；必须用户同意后才加 --yes）"))
    sp.add_argument("--yes", action="store_true", help=_h("用户已明确同意安装；没有这个参数绝不安装任何东西"))
    sp = add("init", cmd_init, _h("新建项目骨架（目录 + 空 spec）"))
    sp.add_argument("dir_name", help=_h("项目目录名：小写英文/数字/连字符，如 quiz-challenge"))
    sp.add_argument("--name", required=True, help=_h("产品中文名"))
    sp.add_argument("--platform", required=True, choices=["miniprogram", "h5", "app", "web", "admin"])
    sp.add_argument("--version", default="V1.0")
    sp.add_argument("--lang", default=None, choices=["zh", "en"], help=_h("项目语言：zh（默认，中文 PRD）/ en（英文 PRD）。写入 spec.lang，之后所有命令按它输出"))
    sp.add_argument("--root", help=_h("PRD 根目录（默认 <工作区>/.codebuddy/docs/prd）"))
    sp = add("where", cmd_where, _h("显示解析到的路径"))
    proj_opts(sp)
    sp = add("spec", cmd_spec, _h("校验 spec"))
    proj_opts(sp)
    sp = add("shot", cmd_shot, _h("按 spec 截图"))
    proj_opts(sp)
    sp.add_argument("--only", help=_h("只截指定页面 id，逗号分隔"))
    sp.add_argument("--chapter", help=_h("只截某一章"))
    sp.add_argument("--dpr", type=int, help=_h("像素比，默认取 spec.viewport.dpr（通常 2）"))
    sp = add("migrate", cmd_migrate, _h("旧 flowmap-config.json → 新 spec"))
    proj_opts(sp)
    sp.add_argument("--force", action="store_true", help=_h("覆盖已有 spec"))
    sp = add("lint", cmd_lint, _h("PRD 机器校验（格式/结构/图文一致/可交付）"))
    proj_opts(sp)
    sp.add_argument("--md", help=_h("指定 PRD 文件（默认取项目目录下的 *-prd.md）"))
    sp.add_argument("-v", "--verbose", action="store_true", help=_h("同时显示 info 级提示"))
    sp = add("flow", cmd_flow, _h("渲染页面流转图并自检"))
    proj_opts(sp)
    sp.add_argument("--scope", help=_h("只处理某一章（如 3.1）或 all"))
    sp.add_argument("--check-only", action="store_true", help=_h("只做几何自检，不输出 PNG"))
    sp.add_argument("--table", action="store_true", help=_h("改为打印由流转关系生成的“页面清单”Markdown 表"))
    sp.add_argument("--transit", action="store_true", help=_h("打印由流转关系生成的各页面“流转”行草稿（PRD 直接引用，避免图文不一致）"))
    sp.add_argument("--draft", action="store_true", help=_h("页面地图草案：不要求原型和截图已存在，节点画成“待绘制”，供用户先确认流转"))
    sp = add("style", cmd_style, _h("视觉风格：列出 / 预览对比 / 应用"))
    proj_opts(sp)
    sp.add_argument("action", choices=["list", "preview", "apply", "build-preview", "check-preview", "check-css"])
    sp.add_argument("name", nargs="?", help=_h("apply 时的风格名"))
    sp.add_argument("--accent", help=_h("主色（可选，6 位十六进制，如 #E5352B）；不指定则为通用蓝占位。颜色与风格相互独立"))
    sp.add_argument("--source", help=_h("apply 时记录配色/风格的依据（如“用户指定”“取自品牌规范”“业务调性推荐”）"))
    sp.add_argument("--out", help=_h("preview 的输出目录（默认：项目的 .prdkit/style-preview，找不到项目则为 ./style-preview）"))
    sp = add("check", cmd_check, _h("质量闸门：自检并给出分级修复建议"))
    proj_opts(sp)
    sp.add_argument("stage", choices=["env", "map", "style", "prototype", "flow", "prd", "all"], help=_h("闸门名；all 依次检查，遇到未通过的就停"))
    sp = add("index", cmd_index, _h("生成原型导航页 prototype/index.html"))
    proj_opts(sp)
    sp = add("view", cmd_view, _h("起本机预览服务：交互 Demo / 风格对比图（IDE 预览窗和浏览器都能打开）"))
    proj_opts(sp)
    sp.add_argument("--demo", action="store_true", help=_h("返回交互 Demo（prototype/index.html）的预览地址（默认）"))
    sp.add_argument("--style", action="store_true", help=_h("改为展示风格对比图（需先运行 style preview）"))
    sp.add_argument("--bundle", action="store_true", help=_h("返回单文件 Demo（prdkit bundle 生成）的自动打开地址"))
    sp.add_argument("--stop", action="store_true", help=_h("关闭本机预览服务"))
    sp = add("open", cmd_open, _h("在 IDE 编辑器里打开 PRD 或指定文件"))
    proj_opts(sp)
    sp.add_argument("file", nargs="?", help=_h("要打开的文件；省略则打开项目里的 PRD"))
    sp = add("bundle", cmd_bundle, _h("把原型打成单文件 demo.html（不依赖服务，IDE 预览与浏览器通用）"))
    proj_opts(sp)
    sp.add_argument("--out", help=_h("输出文件（默认：项目目录下 <名称>-<版本>-demo.html）"))
    sp.add_argument("--no-verify", action="store_true", help=_h("跳过无头浏览器自检"))
    sp = add("demo", cmd_demo, _h("Demo 交付状态：打包 / 本地兜底 / 记录在线地址 / 重置"))
    proj_opts(sp)
    sp.add_argument("action", choices=["local", "online", "pack", "status", "reset"])
    sp.add_argument("url", nargs="?", help=_h("online 时的 https 在线地址"))
    sp.add_argument("--out", help=_h("pack 的输出文件"))
    sp = add("publish", cmd_publish, _h("（可选）一键发布到 GitHub Pages：公开站点，需 GITHUB_TOKEN 与 --confirm-public"))
    proj_opts(sp)
    sp.add_argument("action", choices=["github-pages"])
    sp.add_argument("--repo", help=_h("目标仓库 用户/仓库；省略则用 <你的账号>/prd-demos（不存在会创建为公开仓库）"))
    sp.add_argument("--path", help=_h("站点子目录，默认 <项目名>-<版本>；'.' 表示站点根目录（一个 Demo 一个仓库时用）"))
    sp.add_argument("--confirm-public", action="store_true", help=_h("用户已明确确认：这是公开站点，任何人拿到链接都能打开。每次发布都必须带"))
    sp.add_argument("--update", action="store_true", help=_h("目标目录已有内容时整目录替换（默认拒绝，防误覆盖）"))
    sp.add_argument("--dry-run", action="store_true", help=_h("只做自检与打包，不联网"))
    sp.add_argument("--no-wait", action="store_true", help=_h("不等待站点生效"))
    sp = add("links", cmd_links, _h("由 spec 生成“关联原型”行与附录 B"))
    proj_opts(sp)
    sp.add_argument("--apply", action="store_true", help=_h("写回 PRD；不加则只预览"))

    args = ap.parse_args(argv)
    i18n.set_lang(getattr(args, "ui_lang", None) or i18n.from_env())   # 项目命令会在 _project() 里改按 spec.lang
    if not hasattr(args, "prd_root"):
        args.prd_root = None
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
