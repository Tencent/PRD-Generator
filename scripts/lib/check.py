# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""check：质量闸门。把分散的校验（环境/spec/流程图/原型/PRD）收成“每个闸门一条命令”。

设计要点：
  - 每个要给用户确认的节点之前，先跑对应闸门；有问题先修，再重跑，直到通过才交给用户。
  - 每条问题带“修复分级”和“怎么修”：
      auto  机械可修、结果唯一（直接改，改完重跑）
      judge 需要判断但 AI 能自行判断（改完重跑，汇报改了什么）
      user  需要用户/业务决策（不要编造，列入“待确认”交给用户）
  - 止损：同一条错误连续两次检查仍未消失，退出码 3，要求停止盲目重试、退一层重新分析。
  - 闸门通过（0 错误）才会打印“可以交给用户确认”。
"""
import contextlib
import io
import json
import re
import time
from pathlib import Path

from . import i18n
from . import spec as specmod
from .spec import Issue

STAGES = ["env", "map", "style", "prototype", "flow", "prd"]
STAGE_TITLE = {
    "env": "环境（开始前）",
    "map": "页面地图（给用户确认流转之前）",
    "style": "风格与配色（给用户确认之前）",
    "prototype": "原型（给用户评审之前）",
    "flow": "流程图（给用户评审之前）",
    "prd": "PRD 成稿（交付之前）",
}

# 需要用户决策的：AI 不得自行编造
USER_CODES = {"STYLE-002", "PEND-001"}
# 机械可修、结果唯一的
AUTO_CODES = {"L-101", "L-102", "L-103", "L-105", "L-106", "L-110", "L-111", "L-112", "L-113", "L-206",
              "L-302", "L-311", "L-322", "L-323", "L-324", "L-412", "L-413", "L-501", "PROTO-002", "PROTO-003", "PROTO-022",
              "L-510", "L-511", "L-512", "L-513", "L-514", "L-515"}

HINT = {
    "L-510": "运行 prdkit.py links --apply：把关联原型和附录 B 切换为在线链接",
    "L-511": "运行 prdkit.py links --apply：按 spec 重新生成附录 B",
    "L-512": "运行 prdkit.py links --apply：local 模式下关联原型改写为本地路径（不得写在线链接）",
    "L-513": "运行 prdkit.py links --apply：补上缺失的“关联原型”行",
    "L-514": "运行 prdkit.py links --apply：补上附录 B 的 Demo 说明",
    "L-515": "运行 prdkit.py links --apply：Demo 尚未发布时 PRD 里不写原型地址，发布后统一回填",
    "PEND-001": "这是第 1 步里无法预设、也没拿到的取值：保持标记，交付时只告诉用户“有 N 项待补充、见附录 C”，不要逐条列出",
    "L-101": "删除残留的 AI_INSTRUCTION / SCREENSHOT_PLACEHOLDER 注释；占位符换成真实截图引用",
    "L-102": "标题里去掉【必填】等模板标注",
    "L-103": "把 <img> 改成 ![描述](images/xx.png)",
    "L-206": "章号顺延，保持 1、2、3… 连续（同时改文内交叉引用）",
    "L-302": "运行 prdkit.py shot 生成缺失截图",
    "L-311": "把整体流程图 images/flow-*.png 引用到 3.0 章",
    "L-322": "把章级流程图引用到本章开头",
    "L-323": "运行 prdkit.py flow --table 生成页面清单，粘贴到本章开头",
    "L-324": "重新运行 prdkit.py flow --table，用生成结果整表替换",
    "L-412": "流转行提到了流程图里没有的连线：运行 prdkit.py flow --transit，用草稿覆盖该行（或补连线）",
    "L-413": "流转行漏写相邻页面：运行 prdkit.py flow --transit，用草稿覆盖该行",
    "L-501": "把 localhost / 127.0.0.1 地址换成相对路径或已发布地址",
    "FLOW-025": "边标签改写成用户动作（如“点…”“发送…”），不要和目标页面同名",
    "FLOW-026": "缩短边标签到 14 字以内",
    "FLOWGEO-01": "去掉手写的 fs/ts/route 让引擎自动选；或把节点挪位",
    "FLOWGEO-05": "调大 fo/to（≥38）把线挪开，或改走 route:\"under\"",
    "FLOWGEO-14": "缩短边标签",
    "PROTO-020": "判断后二选一：这条跳转是业务流转 → 在 spec/flows 补连线，再 prdkit flow、flow --table、flow --transit 并更新 PRD 清单与流转行；不是业务流转（示意链接）→ 删掉链接，或加 data-flow-ignore",
    "PROTO-021": "判断后二选一：流转确实存在 → 给原型补上入口；原型不需要这个入口 → 删掉这条连线并重新生成图、清单、流转行",
    "PROTO-022": "链接指向的页面文件不存在：改成正确文件名，或补上该页面（并登记到 spec）",
    "PROTO-001": "把写死的色值改成 var(--color-…)，保证换风格、换主色后页面同步变化",
    "PROTO-002": "去掉外链（CDN/外部图片字体），改用本地资源或纯 CSS",
    "PROTO-003": "页面补上 <link rel=\"stylesheet\" href=\"../assets/style.css\">",
    "PROTO-010": "修复页面报错/不可达的状态，再重新运行 shot",
    "PROTO-011": "页面脚本有报错，修复后重新运行 shot",
    "STYLE-001": "先让用户确认风格，再运行 prdkit.py style apply <风格> --accent <色值> --source <依据>",
    "STYLE-002": "按“用户指定 > 已有设计 > 业务调性推荐”确定主色并让用户确认（见 references/design-guide.md 2.2）",
    "STYLE-003": "apply 时补 --source，写明配色依据",
    "STYLE-004": "运行 prdkit.py style apply 生成 prototype/assets/style.css",
}

STAGE_TITLE_EN = {
    "env": "Environment (before starting)",
    "map": "Page map (before the user confirms the flow)",
    "style": "Style and colour (before the user confirms)",
    "prototype": "Prototype (before the user reviews it)",
    "flow": "Flow diagrams (before the user reviews them)",
    "prd": "PRD draft (before delivery)",
}

HINT_EN = {
    "L-510": "Run prdkit.py links --apply: switch the prototype lines and Appendix B to the online links",
    "L-511": "Run prdkit.py links --apply: regenerate Appendix B from the spec",
    "L-512": "Run prdkit.py links --apply: in local mode the prototype lines become local paths (never online links)",
    "L-513": "Run prdkit.py links --apply: add the missing prototype line",
    "L-514": "Run prdkit.py links --apply: add the demo note to Appendix B",
    "L-515": "Run prdkit.py links --apply: while the demo is unpublished the PRD carries no prototype address; it is back-filled after publishing",
    "PEND-001": "This is a value that could not be pre-set in step 1 and was not provided: keep the mark and, on delivery, only tell the user \"N items are pending, see Appendix C\"; do not list them one by one",
    "L-101": "Delete the leftover AI_INSTRUCTION / SCREENSHOT_PLACEHOLDER comments; replace placeholders with real screenshot references",
    "L-102": "Remove template marks such as [Required] from headings",
    "L-103": "Change <img> into ![description](images/xx.png)",
    "L-206": "Renumber the chapters so they stay continuous 1, 2, 3… (and update in-text cross references)",
    "L-302": "Run prdkit.py shot to generate the missing screenshots",
    "L-311": "Reference the overall flow diagram images/flow-*.png in chapter 3.0",
    "L-322": "Reference the chapter flow diagram at the start of the chapter",
    "L-323": "Run prdkit.py flow --table to generate the page list and paste it at the start of the chapter",
    "L-324": "Rerun prdkit.py flow --table and replace the whole table with the generated one",
    "L-412": "The flow line mentions a connection that is not in the flow diagram: run prdkit.py flow --transit and overwrite the line with the draft (or add the connection)",
    "L-413": "The flow line omits an adjacent page: run prdkit.py flow --transit and overwrite the line with the draft",
    "L-501": "Replace localhost / 127.0.0.1 addresses with relative paths or published addresses",
    "FLOW-025": "Rewrite the edge label as a user action (e.g. \"Tap ...\", \"Send ...\"); do not reuse the target page name",
    "FLOW-026": "Shorten the edge label to 28 characters or fewer",
    "FLOWGEO-01": "Remove the hand-written fs/ts/route so the engine picks them; or move the node",
    "FLOWGEO-05": "Increase fo/to (>= 38) to move the line away, or use route:\"under\"",
    "FLOWGEO-14": "Shorten the edge label",
    "PROTO-020": "Decide, then pick one: if this jump is a business flow -> add the edge in spec/flows, rerun prdkit flow, flow --table, flow --transit and update the PRD list and flow lines; if it is not (an illustrative link) -> delete the link or add data-flow-ignore",
    "PROTO-021": "Decide, then pick one: if the flow really exists -> add the entry to the prototype; if the prototype does not need it -> delete the edge and regenerate the diagram, list and flow lines",
    "PROTO-022": "The link points to a page file that does not exist: fix the file name, or add the page (and register it in the spec)",
    "PROTO-001": "Replace hard-coded colours with var(--color-…) so pages follow a style or accent change",
    "PROTO-002": "Remove external resources (CDN / external images or fonts); use local assets or pure CSS",
    "PROTO-003": "Add <link rel=\"stylesheet\" href=\"../assets/style.css\"> to the page",
    "PROTO-010": "Fix the page error / unreachable state, then rerun shot",
    "PROTO-011": "The page script reports errors; fix them and rerun shot",
    "STYLE-001": "Have the user confirm a style first, then run prdkit.py style apply <style> --accent <hex> --source <basis>",
    "STYLE-002": "Decide the accent colour by \"user specified > existing design > recommended for the business tone\" and have the user confirm it (see references/design-guide.md 2.2)",
    "STYLE-003": "Pass --source to apply and state the basis of the colour",
    "STYLE-004": "Run prdkit.py style apply to generate prototype/assets/style.css",
}


def hint_of(code):
    h = HINT_EN.get(code) if i18n.cur() == "en" else HINT.get(code)
    return h if h is not None else HINT.get(code)


HEX_RE = re.compile(r"(?<![\w&#/])#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})\b|:\s*#[0-9A-Fa-f]{3}\b")
EXT_RE = re.compile(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//|url\(\s*["']?\s*(?:https?:)?//""", re.I)


assert set(HINT) == set(HINT_EN), sorted(set(HINT) ^ set(HINT_EN))


def classify(i):
    if i.code in USER_CODES:
        return "user"
    if i.code in AUTO_CODES:
        return "auto"
    return "judge"


# ───────────────────────── 各闸门 ─────────────────────────
def _quiet(fn, *a, **k):
    """调用会往 stdout 打印的函数，吞掉输出；把 SystemExit 变成结果。"""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return fn(*a, **k), None
    except SystemExit as e:
        return None, str(e) if e.code not in (0, None) else None


def stage_env(proj):
    from . import doctor
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = doctor.run()
    if code:
        return [Issue("error", "ENV-001", "环境体检未通过：运行 prdkit.py doctor 查看缺项（含中文字体、Chromium）",
                       en="Environment check failed: run prdkit.py doctor to see what is missing (Chromium, Playwright, Python version)")]
    return []


def stage_map(proj):
    from . import flow
    i18n.set_lang(proj.lang)
    issues, _ = specmod.validate_all(proj, draft=True)
    if any(i.level == "error" for i in issues):
        return issues
    res, err = _quiet(flow.render_all, proj, draft=True)
    if err:
        return issues + [Issue("error", "MAP-001", err, en=err)]
    return issues + res[0]


def stage_style(proj):
    out = []
    data = proj.load_screens() if proj.screens_path.exists() else {}
    st = data.get("style")
    if not st or not st.get("name"):
        out.append(Issue("error", "STYLE-001", "项目还没有确认风格（spec.style 为空）", en="No style has been confirmed for the project (spec.style is empty)"))
        return out
    if not (proj.proto / "assets" / "style.css").exists():
        out.append(Issue("error", "STYLE-004", "缺少 prototype/assets/style.css", en="prototype/assets/style.css is missing"))
    if not st.get("accent"):
        out.append(Issue("warn", "STYLE-002", "还没有确认主色，当前是通用蓝色占位；请按业务调性或已有设计让用户确认",
                         en="No accent colour has been confirmed; a generic blue placeholder is in use. Have the user confirm one from the business tone or an existing design"))
    elif not st.get("source"):
        out.append(Issue("warn", "STYLE-003", f"主色 {st['accent']} 没有记录依据（spec.style.source）", en=f"The accent {st['accent']} has no recorded basis (spec.style.source)"))
    return out


def stage_prototype(proj):
    from . import shot
    issues, _ = specmod.validate_all(proj)
    if any(i.level == "error" for i in issues):
        return issues
    pages = [p for p in (proj.proto / "pages").rglob("*.html")] if (proj.proto / "pages").is_dir() else []
    for p in pages:
        text = p.read_text(encoding="utf-8", errors="ignore")
        rel = p.relative_to(proj.root)
        hexes = sorted(set(m.group(0).lstrip(": ") for m in HEX_RE.finditer(text)))
        if hexes:
            issues.append(Issue("warn", "PROTO-001", f"{rel}：有 {len(hexes)} 处写死的色值（{', '.join(hexes[:4])}…），应改用 var(--color-…)",
                                en=f"{rel}: {len(hexes)} hard-coded colour(s) ({', '.join(hexes[:4])}…); use var(--color-…) instead"))
        if EXT_RE.search(text):
            issues.append(Issue("error", "PROTO-002", f"{rel}：引用了外部资源（CDN/外链图片或字体），导出后可能打不开",
                                en=f"{rel}: references external resources (CDN / external images or fonts) that may not open after export"))
        if "assets/style.css" not in text:
            issues.append(Issue("error", "PROTO-003", f"{rel}：没有引用 assets/style.css", en=f"{rel}: does not reference assets/style.css"))
    from . import protolinks
    issues += protolinks.analyze(proj)
    res, err = _quiet(shot.take_shots, proj)
    if err:
        return issues + [Issue("error", "PROTO-010", err, en=err)]
    ok, failed = res
    for sid, msg in failed:
        issues.append(Issue("error", "PROTO-010", f"页面 {sid} 截图失败：{msg}", en=f"Screenshot of page {sid} failed: {msg}"))
    mf = proj.state / "shots.json"
    if mf.exists():
        for sid, info in json.loads(mf.read_text(encoding="utf-8")).items():
            if info.get("js_errors"):
                issues.append(Issue("error", "PROTO-011", f"页面 {sid} 有脚本报错：{info['js_errors'][0]}", en=f"Page {sid} has a script error: {info['js_errors'][0]}"))
    return issues


def stage_flow(proj):
    from . import flow
    res, err = _quiet(flow.render_all, proj)
    if err:
        return [Issue("error", "FLOW-900", err, en=err)]
    return res[0]


def stage_prd(proj):
    from . import lint
    issues, md = lint.run(proj)
    issues = [i for i in issues if i.level != "info"]
    md = proj.prd_md()
    if md and md.exists():
        for n, ln in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if "[待确认" in ln or "[TBC" in ln:
                issues.append(Issue("warn", "PEND-001", f"第 {n} 行有待用户确认的内容：{ln.strip()[:50]}",
                                    en=f"Line {n} has content pending the user's confirmation: {ln.strip()[:50]}"))
    return issues


RUNNERS = {"env": stage_env, "map": stage_map, "style": stage_style,
           "prototype": stage_prototype, "flow": stage_flow, "prd": stage_prd}


# ───────────────────────── 止损计数 ─────────────────────────
def _state_path(proj):
    return proj.state / "check-state.json"


def _load_state(proj):
    p = _state_path(proj)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def _save_state(proj, st):
    p = _state_path(proj)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def update_streaks(proj, stage, issues):
    """返回 {签名: 连续出现次数}。问题消失即清零；整个闸门通过时清空该闸门的记录。"""
    st = _load_state(proj)
    prev = st.get(stage, {}).get("streak", {})
    now = {}
    for i in issues:
        sig = f"{i.code}|{i.msg}"
        now[sig] = prev.get(sig, 0) + 1
    if issues:
        st[stage] = {"streak": now, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    else:
        st.pop(stage, None)
    _save_state(proj, st)
    return now


# ───────────────────────── 输出 ─────────────────────────
def report(stage, issues, streaks):
    en = i18n.cur() == "en"
    title = (STAGE_TITLE_EN if en else STAGE_TITLE)[stage]
    errs = [i for i in issues if i.level == "error"]
    warns = [i for i in issues if i.level == "warn"]
    print(f"══ Gate \"{stage}\": {title} ══" if en else f"══ 闸门「{stage}」{title} ══")
    if not issues:
        print("✅ Passed, no issues found. It can go to the user for confirmation." if en else "✅ 通过，没有发现问题。可以交给用户确认。")
        return 0
    groups = {"auto": [], "judge": [], "user": []}
    for i in issues:
        groups[classify(i)].append(i)
    label = ({"auto": "Fix directly (mechanical, unique result)", "judge": "Needs your judgement before editing",
              "user": "Needs a user decision (do not invent; list under \"to be confirmed\")"} if en else
             {"auto": "可直接修复（机械、结果唯一）", "judge": "需要你判断后修改", "user": "需要用户决策（不要自行编造，列入“待确认”）"})
    stuck = []
    for k in ("auto", "judge", "user"):
        if not groups[k]:
            continue
        print(f"\n【{label[k]}】")
        for i in groups[k]:
            n = streaks.get(f"{i.code}|{i.msg}", 1)
            tail = ((f" (still present after {n} consecutive checks)" if en else f"（已连续 {n} 次检查仍存在）") if n >= 2 and k != "user" else "")
            print(f"  {i}{tail}")
            if i.code in HINT:
                print(f"      {'Fix: ' if en else '修复：'}{hint_of(i.code)}")
            if i.level == "error" and n >= 2 and k != "user":
                stuck.append(i)
    print(f"\n{len(errs)} errors, {len(warns)} warnings." if en else f"\n共 {len(errs)} 个错误、{len(warns)} 个提醒。")
    if stuck:
        print("⛔ Stop-loss: the errors below survived 2 consecutive checks; do not retry the same way. Step back and re-analyse the root cause (another fix? an upstream file?) before continuing:" if en
              else "⛔ 止损：以下错误连续 2 次检查仍未消失，不要再用同样的办法重试。请退一层重新分析根因（别的修法？上游文件？），再继续：")
        for i in stuck:
            print(f"   - [{i.code}] {i.text()[:80]}")
        return 3
    if errs:
        print("➡ Fix the errors first, then rerun the same command; it can go to the user only when errors are zero." if en
              else "➡ 请先修复错误，再重新运行同一条命令；错误清零后才能交给用户。")
        return 1
    if groups["user"]:
        print("✅ No errors. Some warnings need a user decision; list them under \"to be confirmed\" on delivery." if en
              else "✅ 无错误。提醒中有需要用户决策的事项，交付时请列入“待确认”。")
    else:
        print("✅ No errors; mention the warnings in your report. It can go to the user for confirmation." if en
              else "✅ 无错误，提醒可在汇报里说明。可以交给用户确认。")
    return 0


def run(proj, stage):
    if proj is not None:
        i18n.set_lang(proj.lang)
    stages = STAGES if stage == "all" else [stage]
    worst = 0
    for st in stages:
        issues = RUNNERS[st](proj)
        streaks = update_streaks(proj, st, [i for i in issues if i.level in ("error", "warn")]) if proj is not None else {}
        code = report(st, [i for i in issues if i.level in ("error", "warn")], streaks)
        print()
        worst = max(worst, code)
        if code and stage == "all":
            print("(Checking gate by gate: the previous gate failed, so the later gates are not run)" if i18n.cur() == "en" else "（逐关检查：前一关未通过，后面的闸门先不跑）")
            break
    return worst
