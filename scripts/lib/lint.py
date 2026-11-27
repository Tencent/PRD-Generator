# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""lint：PRD 确定性校验。把旧版 SKILL 里由 AI 手写 grep 的 CHECKPOINT / 质检规则脚本化，
并新增“PRD ↔ spec ↔ 截图 ↔ 流程图”的一致性检查。需要人脑判断的语义类规则不在此处（见 references/qa-semantic.md）。

规则编号：L-1xx 格式与残留 | L-2xx 结构完整 | L-3xx 图文一致（依赖 spec） | L-4xx 叙事与可读性 | L-5xx 链接与可交付
级别：error 必须修；warn 建议修；info 供参考。
"""
import re
from pathlib import Path

from . import i18n
from . import spec as specmod
from .flow import flow_out_name, _load as _load_flow

Issue = specmod.Issue

TEMPLATE_MARKS = ("【必填】", "【选填】", "【按需必填】", "【按需】")
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
BOX_CHARS = "┌└┐┘├┤┬┴┼"
REQUIRED_TOP = i18n.WORDS["zh"]["top_required"]      # 中文历史取值；运行时按项目语言取 i18n.W("top_required")
MODULE_PARTS = i18n.WORDS["zh"]["module_parts"]
FLOW_MIN_NODES = 3          # 章内页面+弹窗达到该数量，必须有章级流程图
OVERALL_SCOPES = ("3.0", "all")
LOCAL_URL_RE = re.compile(r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)")
LEFTOVER_RE = re.compile(r"\[TODO\]|\bTBD\b|待补充|\{[^{}\s]{1,16}\}")
LEFTOVER_RE_EN = re.compile(r"\[TODO\]|\bTODO\b|\bFIXME\b|\bTBD\b|\{[^{}\s]{1,16}\}")


def _leftover():
    return LEFTOVER_RE_EN if i18n.cur() == "en" else LEFTOVER_RE


def _split(text):
    """lines 与 in_code：in_code[i] 为 True 表示该行位于围栏代码块（含 mermaid）内。"""
    lines = text.splitlines()
    in_code, flag = [], False
    for ln in lines:
        if ln.lstrip().startswith("```"):
            in_code.append(True)
            flag = not flag
        else:
            in_code.append(flag)
    return lines, in_code


def _headings(lines, in_code):
    out = []
    for i, ln in enumerate(lines):
        if not in_code[i]:
            m = HEAD_RE.match(ln)
            if m:
                out.append((i, len(m.group(1)), m.group(2)))
    return out


def _section_end(heads, k, lines):
    lvl = heads[k][1]
    for (j, l2, _) in heads[k + 1:]:
        if l2 <= lvl:
            return j
    return len(lines)


def _chapter_range(heads, lines, cid):
    pat = re.compile(r"^" + re.escape(cid) + r"(\s|$)")
    for k, (i, lvl, title) in enumerate(heads):
        if pat.match(title):
            return i, _section_end(heads, k, lines)
    return None


def check_format(lines, in_code, heads, md, proj, issues):
    at = lambda i: f"第 {i + 1} 行"
    at_en = lambda i: f"Line {i + 1}"
    prose = [(i, ln) for i, ln in enumerate(lines) if not in_code[i]]
    for i, ln in enumerate(lines):
        if "AI_INSTRUCTION" in ln or "SCREENSHOT_PLACEHOLDER" in ln:
            issues.append(Issue("error", "L-101", f"{at(i)}：残留模板注释（AI_INSTRUCTION / SCREENSHOT_PLACEHOLDER）", en=f"{at_en(i)}: leftover template comment (AI_INSTRUCTION / SCREENSHOT_PLACEHOLDER)"))
    for i, lvl, title in heads:
        if any(m in title for m in TEMPLATE_MARKS):
            issues.append(Issue("error", "L-102", f"{at(i)}：标题含模板标注：{title}", en=f"{at_en(i)}: heading still carries a template mark: {title}"))
    for i, ln in prose:
        if "<img" in ln.lower():
            issues.append(Issue("error", "L-103", f"{at(i)}：PRD 源文件中不得使用 HTML <img>，请用 ![描述](images/xx.png)", en=f"{at_en(i)}: do not use HTML <img> in the PRD source; use ![description](images/xx.png)"))
        if any(c in ln for c in BOX_CHARS):
            issues.append(Issue("error", "L-104", f"{at(i)}：疑似文本线框图 / ASCII art，页面展示必须使用截图", en=f"{at_en(i)}: looks like a text wireframe / ASCII art; pages must be shown with screenshots"))
        if _leftover().search(ln):
            issues.append(Issue("warn", "L-105", f"{at(i)}：残留占位符（TODO/TBD/待补充/{{变量}}）：{ln.strip()[:40]}", en=f"{at_en(i)}: leftover placeholder (TODO/TBD/{{variable}}): {ln.strip()[:40]}"))
    prev = 0
    for i, lvl, title in heads:
        if prev and lvl > prev + 1:
            issues.append(Issue("warn", "L-106", f"{at(i)}：标题层级跳级（h{prev} → h{lvl}）：{title[:30]}", en=f"{at_en(i)}: heading level skipped (h{prev} → h{lvl}): {title[:30]}"))
        prev = lvl

    ref_names = set()
    for i, ln in prose:
        for m in IMG_RE.finditer(ln):
            src = m.group(2)
            if src.startswith("data:image"):
                issues.append(Issue("error", "L-110", f"{at(i)}：不得使用 base64 内嵌图片", en=f"{at_en(i)}: do not embed base64 images"))
            elif re.match(r"^https?://", src):
                issues.append(Issue("error", "L-111", f"{at(i)}：不得使用外部图片链接：{src[:50]}", en=f"{at_en(i)}: do not use external image links: {src[:50]}"))
            else:
                ref_names.add(Path(src).name)
                if not src.startswith("images/"):
                    issues.append(Issue("warn", "L-112", f"{at(i)}：图片路径应以 images/ 开头：{src}", en=f"{at_en(i)}: image path should start with images/: {src}"))
                if not (md.parent / src).exists():
                    issues.append(Issue("error", "L-113", f"{at(i)}：引用的图片文件不存在：{src}", en=f"{at_en(i)}: referenced image file does not exist: {src}"))
    if proj.images.is_dir():
        extra = sorted(p.name for p in proj.images.glob("*.png") if p.name not in ref_names)
        if extra:
            issues.append(Issue("info", "L-114", f"images/ 中有 {len(extra)} 个图片未被 PRD 引用：{', '.join(extra[:6])}{'…' if len(extra) > 6 else ''}", en=f"{len(extra)} image(s) in images/ are not referenced by the PRD: {', '.join(extra[:6])}{'…' if len(extra) > 6 else ''}"))
    return ref_names


def check_structure(text, lines, heads, issues):
    titles = " ".join(t for _, _, t in heads)
    for label, kw in i18n.W("top_required"):
        if kw not in titles:
            issues.append(Issue("error", "L-201", f"缺少必填章节：{label}", en=f"missing required section: {label}"))
    if not any(ln.strip().startswith("sequenceDiagram") for ln in lines):
        issues.append(Issue("error", "L-202", "缺少 Mermaid 时序图（sequenceDiagram）", en="missing Mermaid sequence diagram (sequenceDiagram)"))
    if not any(re.match(r"^\s*(flowchart\b|graph\s)", ln) for ln in lines):
        issues.append(Issue("error", "L-203", "缺少 Mermaid 业务流程图（flowchart）", en="missing Mermaid business flowchart (flowchart)"))
    if not re.search(i18n.W("revision_re"), text):
        issues.append(Issue("warn", "L-204", "未找到“修订说明 / 修订记录”", en=f'no "{i18n.W("revision_label")}" found'))
    nums = [int(m.group(1)) for _, lvl, t in heads if lvl == 2 for m in [re.match(r"^(\d+)[.\s、]", t)] if m]
    for prev, cur in zip(nums, nums[1:]):
        if cur != prev + 1:
            issues.append(Issue("warn", "L-206", f"一级章号不连续（{prev} 之后是 {cur}）；省略可选章节后，后面的章号要顺延", en=f"top-level chapter numbers are not continuous ({cur} follows {prev}); renumber the later chapters after dropping an optional one"))
            break
    br = re.findall(r"^\|\s*(BR-\d+)\s*\|", text, re.M)
    dup = sorted({b for b in br if br.count(b) > 1})
    if dup:
        issues.append(Issue("error", "L-205", f"业务规则编号重复：{', '.join(dup)}（编号全局唯一即可，不要求连续）", en=f"duplicate business rule IDs: {', '.join(dup)} (IDs only need to be globally unique, not consecutive)"))


def check_consistency(proj, lines, heads, ref_names, issues):
    if not proj.screens_path.exists():
        issues.append(Issue("info", "L-300", "未找到 spec/screens.json：已跳过图文一致性检查（旧项目可用 migrate 生成）", en="spec/screens.json not found: consistency checks skipped (legacy projects can use migrate to generate one)"))
        return
    sissues, screens = specmod.validate_all(proj)
    issues += [i for i in sissues if i.level == "error"]
    chapters = proj.load_screens().get("chapters", [])
    for sid, s in screens.items():
        if s["shot"] not in ref_names:
            lvl = "error" if s["kind"] == "page" else "warn"
            issues.append(Issue(lvl, "L-301", f"页面「{s['name']}」（{sid}）的截图 images/{s['shot']} 没有出现在 PRD 中",
                                en=f"screenshot images/{s['shot']} of \"{s['name']}\" ({sid}) does not appear in the PRD"))
        elif not (proj.images / s["shot"]).exists():
            issues.append(Issue("error", "L-302", f"页面「{s['name']}」的截图文件不存在：images/{s['shot']}（先运行 shot）", en=f'screenshot file of "{s["name"]}" does not exist: images/{s["shot"]} (run shot first)'))

    flows = {}
    for fp in proj.flow_files():
        fl = _load_flow(fp)
        flows[str(fl.get("scope"))] = fl
    if len(screens) > 2:
        overall = [sc for sc in OVERALL_SCOPES if sc in flows]
        if not overall:
            issues.append(Issue("error", "L-310", "缺少整体页面流程图（flows/3.0.json 或 flows/all.json）", en="missing overall page-flow diagram (flows/3.0.json or flows/all.json)"))
        else:
            name = flows[overall[0]].get("out") or flow_out_name(overall[0])
            if name not in ref_names:
                issues.append(Issue("error", "L-311", f"整体页面流程图 images/{name} 没有出现在 PRD 中", en=f"overall page-flow diagram images/{name} does not appear in the PRD"))

    last, in_order = -1, True
    for ch in chapters:
        cid = ch["id"]
        rng = _chapter_range(heads, lines, cid)
        if not rng:
            issues.append(Issue("error", "L-320", f"spec 中的章节 {cid}「{ch.get('title', '')}」在 PRD 中找不到对应标题", en=f'chapter {cid} "{ch.get("title", "")}" in the spec has no matching heading in the PRD'))
            continue
        if rng[0] < last:
            in_order = False
        last = rng[0]
        body = lines[rng[0]:rng[1]]
        chunk = "\n".join(body)
        ch_screens = [s for s in screens.values() if s["chapter"] == cid]
        if len(ch_screens) < FLOW_MIN_NODES:
            continue
        fl = flows.get(cid)
        if not fl:
            issues.append(Issue("error", "L-321", f"第 {cid} 章有 {len(ch_screens)} 个页面/弹窗，需要章级流程图（flows/{cid}.json）", en=f"chapter {cid} has {len(ch_screens)} pages/popups and needs a chapter-level flow diagram (flows/{cid}.json)"))
        elif (fl.get("out") or flow_out_name(cid)) not in chunk:
            issues.append(Issue("error", "L-322", f"第 {cid} 章没有引用章级流程图 images/{fl.get('out') or flow_out_name(cid)}", en=f"chapter {cid} does not reference its flow diagram images/{fl.get('out') or flow_out_name(cid)}"))
        if i18n.W("page_list") not in chunk:
            issues.append(Issue("error", "L-323", f"第 {cid} 章缺少“本章页面清单”表", en=f'chapter {cid} is missing its "{i18n.W("page_list")}" table'))
        else:
            firsts = []
            for ln in body:
                if ln.lstrip().startswith("|"):
                    cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                    if cells:
                        firsts.append(cells[0])
            for s in ch_screens:
                if not any(s["name"] in c for c in firsts):
                    issues.append(Issue("error", "L-324", f"第 {cid} 章页面清单缺少「{s['name']}」（清单须覆盖本章全部页面/弹窗）", en=f'the page list of chapter {cid} is missing "{s["name"]}" (it must cover every page/popup in the chapter)'))
    if not in_order:
        issues.append(Issue("warn", "L-420", "PRD 中的章节顺序与 spec.chapters 不一致（章序应按用户旅程）", en="chapter order in the PRD differs from spec.chapters (order chapters by the user journey)"))


def check_narrative(lines, heads, issues):
    at = lambda i: f"第 {i + 1} 行"
    at_en = lambda i: f"Line {i + 1}"
    for k, (i, lvl, title) in enumerate(heads):
        if i18n.section_probe_re().search(title):
            if i18n.W("transit_key") not in "\n".join(lines[i + 1:i + 8]):
                issues.append(Issue("warn", "L-410", f"{at(i)}：「{title[:30]}」缺少首行“**流转**：…”（从哪来、到哪去）", en=f'{at_en(i)}: "{title[:30]}" lacks the first line "{i18n.W("transit_prefix")}…" (where the user comes from / goes next)'))
        if re.match(r"^3\.[1-9]\d*(\s|$)", title):
            chunk = "\n".join(lines[i:_section_end(heads, k, lines)])
            miss = [p for p in i18n.W("module_parts") if p not in chunk]
            if miss:
                issues.append(Issue("warn", "L-411", f"{at(i)}：模块「{title[:20]}」缺少子章节：{'、'.join(miss)}", en=f'{at_en(i)}: module "{title[:20]}" is missing sub-sections: {", ".join(miss)}'))


def _neighbors(proj, screens):
    """所有流程图里，每个页面的相邻页面 {screen_id: {其他 screen_id}}（不分方向、不分章）。"""
    nb = {sid: set() for sid in screens}
    for fp in proj.flow_files():
        fl = _load_flow(fp)
        nmap = {n["id"]: n.get("screen") for n in fl.get("nodes", [])}
        for e in fl.get("edges", []):
            x, y = nmap.get(e["f"]), nmap.get(e["t"])
            if x and y and x in nb and y in nb and x != y:
                nb[x].add(y)
                nb[y].add(x)
    return nb


def check_transit(proj, lines, heads, issues):
    """“流转”行提到的页面，必须与流程图里的相邻页面一致。
    L-412 提到了流程图里不相邻的页面（error）；L-413 漏写了流程图里的相邻页面（warn）；L-414 页面未登记（warn）。"""
    if not proj.screens_path.exists():
        return
    sissues, screens = specmod.validate_all(proj)
    if any(i.level == "error" for i in sissues):
        return
    by_name = {s["name"]: s for s in screens.values()}
    nb = _neighbors(proj, screens)
    for i, lvl, title in heads:
        m = i18n.section_re().search(title)
        if not m:
            continue
        name = m.group(1).strip()
        s = by_name.get(name)
        at = f"第 {i + 1} 行"
        at_en = f"Line {i + 1}"
        if not s:
            issues.append(Issue("warn", "L-414", f"{at}：「{name}」在 spec/screens.json 里没有登记，无法核对流转", en=f'{at_en}: "{name}" is not registered in spec/screens.json, so its flow line cannot be checked'))
            continue
        line = next((ln for ln in lines[i + 1:i + 8] if ln.startswith(i18n.W("transit_key"))), None)
        if not line:
            continue
        mentioned = {o["id"] for o in screens.values() if o["id"] != s["id"] and o["name"] in line}
        extra = mentioned - nb[s["id"]]
        miss = nb[s["id"]] - mentioned
        if extra:
            names = "、".join(screens[x]["name"] for x in sorted(extra))
            issues.append(Issue("error", "L-412", f"{at}：「{name}」的流转行提到了「{names}」，但流程图里它们与本页没有连线（改文字或补连线）", en=f'{at_en}: the flow line of "{name}" mentions "{", ".join(screens[x]["name"] for x in sorted(extra))}", but they are not connected to this page in the flow diagram (edit the text or add the connection)'))
        if miss:
            names = "、".join(screens[x]["name"] for x in sorted(miss))
            issues.append(Issue("warn", "L-413", f"{at}：「{name}」的流转行没有写到流程图里的相邻页面「{names}」", en=f'{at_en}: the flow line of "{name}" does not mention the adjacent page(s) in the diagram: "{", ".join(screens[x]["name"] for x in sorted(miss))}"'))


def check_deliverable(lines, in_code, issues):
    for i, ln in enumerate(lines):
        if not in_code[i] and LOCAL_URL_RE.search(ln):
            issues.append(Issue("error", "L-501", f"第 {i + 1} 行：PRD 中出现本机地址（localhost/127.0.0.1），发布后他人无法打开：{ln.strip()[:50]}", en=f"Line {i + 1}: the PRD contains a local address (localhost/127.0.0.1) that others cannot open: {ln.strip()[:50]}"))


def check_demo(proj, lines, heads, issues):
    """“关联原型”行与附录 B 必须与 spec.demo 的状态一致：
    pending（缺省）=不写原型地址，附录 B 只写“发布后补充”；online=在线链接；local=本地路径+未发布说明。
    这些内容由 prdkit links --apply 生成，不要手写。"""
    if not proj.screens_path.exists():
        return
    from . import links
    sissues, screens = specmod.validate_all(proj)
    if any(i.level == "error" for i in sissues):
        return
    data = proj.load_screens()
    mode, d = links.demo_info(data)
    online = mode == "online"
    pending = mode == "pending"
    by_name = {s["name"]: s for s in screens.values()}
    fix = "运行 prdkit.py links --apply 按 spec 重新生成"
    fix_en = "run prdkit.py links --apply to regenerate from the spec"
    for k, (i, lvl, title) in enumerate(heads):
        m = i18n.section_re().search(title)
        s = by_name.get(m.group(1).strip()) if m else None
        if not s:
            continue
        end = _section_end(heads, k, lines)
        line = next((ln for ln in lines[i + 1:end] if ln.startswith(i18n.W("rel_prefix"))), None)
        at = f"第 {i + 1} 行「{s['name']}」"
        at_en = f'Line {i + 1} "{s["name"]}"'
        if pending:
            if line is not None:
                issues.append(Issue("error", "L-515", f"{at}：Demo 尚未发布，不应写“关联原型”地址（发布在线 Demo 后统一回填）；{fix}", en=f"{at_en}: the demo is not published yet, so no prototype address should be written (it is back-filled after publishing); {fix_en}"))
            continue
        if line is None:
            issues.append(Issue("warn", "L-513", f"{at}缺少“**关联原型**”行（{fix}）", en=f'{at_en} is missing the "{i18n.W("rel_prefix").rstrip(": ")}" line ({fix_en})'))
            continue
        want = links.target(data, s)
        if want not in line:
            if online:
                issues.append(Issue("error", "L-510", f"{at}：已选择在线 Demo，但关联原型不是在线链接（应为 {want}）；{fix}", en=f"{at_en}: an online demo was chosen, but the prototype link is not the online link (expected {want}); {fix_en}"))
            else:
                issues.append(Issue("error", "L-512", f"{at}：未发布在线 Demo（local 模式），关联原型应写本地路径 {want}，不得写在线链接；{fix}", en=f"{at_en}: the online demo is not published (local mode); the prototype line must be the local path {want}, not an online link; {fix_en}"))
    ap = links._appendix_range(lines, heads)
    if ap:
        block = "\n".join(lines[ap[1]:ap[2]])
        miss = [t for t in links._expected_targets(data) if t not in block]
        if miss:
            issues.append(Issue("error", "L-511", f"附录 B 与 spec 的 Demo 方式不一致（缺 {len(miss)} 处：{miss[0]}…）；{fix}", en=f"Appendix B does not match the demo mode in the spec ({len(miss)} item(s) missing, e.g. {miss[0]}…); {fix_en}"))
        elif pending and i18n.W("pending_mark") not in block:
            issues.append(Issue("warn", "L-514", f"附录 B 缺少“在线 Demo 发布后补充”的说明（当前 Demo 尚未发布）；{fix}", en=f'Appendix B lacks the note "{i18n.W("pending_mark")}…" (the demo is not published yet); {fix_en}'))
        elif not online and not pending and i18n.W("local_mark") not in block:
            issues.append(Issue("warn", "L-514", f"附录 B 缺少“本版未发布在线 Demo”及打开方式的说明；{fix}", en=f"Appendix B lacks the note that the online demo is not published, together with how to open the files; {fix_en}"))


def run(proj, md_path=None):
    """返回 (issues, md 路径)。"""
    issues = []
    i18n.set_lang(proj.lang)
    md = Path(md_path) if md_path else proj.prd_md()
    if not md or not md.exists():
        return [Issue("error", "L-000", f"未找到 PRD 文件（期望 {proj.root}/*-prd.md）", en=f"PRD file not found (expected {proj.root}/*-prd.md)")], None
    text = md.read_text(encoding="utf-8")
    lines, in_code = _split(text)
    heads = _headings(lines, in_code)
    ref_names = check_format(lines, in_code, heads, md, proj, issues)
    check_structure(text, lines, heads, issues)
    check_consistency(proj, lines, heads, ref_names, issues)
    check_narrative(lines, heads, issues)
    check_transit(proj, lines, heads, issues)
    check_deliverable(lines, in_code, issues)
    check_demo(proj, lines, heads, issues)
    return issues, md


def score(issues):
    """与旧版一致：error 扣 5，warn 扣 2，满分 100。仅反映机器可判断部分。"""
    errs = sum(1 for i in issues if i.level == "error")
    warns = sum(1 for i in issues if i.level == "warn")
    return max(0, 100 - 5 * errs - 2 * warns), errs, warns
