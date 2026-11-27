# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""spec 模块：页面登记（screens.json）与流转（flows/*.json）的格式定义与校验。

screens.json 是整个 PRD 的“页面单一事实源”：
  截图 / 流程图 / 页面清单表 / 附录 B 的 Demo 表 / 关联原型链接，都由它派生。

{
  "schema": 1,
  "name": "产品名", "version": "V1.0",
  "platform": "miniprogram | h5 | app | web | admin",
  "style": {"name": "flat", "accent": "#1677FF", "source": "用户指定"},   # 可选；由 prdkit style apply 写入；source 记录配色依据
  "demo": {"mode": "online", "url": "https://example.github.io/my-demo-v1-0"},
                                         # 可选；Demo 展示方式。online=已托管的在线 Demo（由 prdkit demo online 或发布器写入）；
                                         # local=用户明确不托管，PRD 里写本地路径并随交付包附 prototype.zip（由 prdkit demo local 写入）；
                                         # pending=尚未处理（缺省）：PRD 里不写原型地址，附录 B 只写“发布后补充”，托管后由 links --apply 统一回填
  "viewport": {"width": 390, "height": 844, "dpr": 2},
  "chapters": [{"id": "3.1", "title": "登录与协议"}],
  "screens": [{
      "id": "login",                  # 全局唯一，英文/数字/连字符
      "name": "登录页",
      "kind": "page | state | popup | native",
      "chapter": "3.1",               # 所属章
      "section": "3.1.3.1",           # 对应 PRD 小节号（可选，流程图副标题用）
      "url": "pages/login.html?s=a",  # 相对 prototype/，状态通过 query 参数可达
      "actions": [{"click": "#btn"}, {"eval": "openSheet()"}, {"wait": 300}, {"fill": ["#phone", "138"]}],
      "shot": "login.png",            # 输出到 images/
      "full_page": true,              # false 时只截一屏
      "selector": null,               # 只截某个元素
      "viewport": null                # 覆盖全局视口（PC 页用 1440）
  }]
}

flows/<scope>.json（scope = 章号或 all）：
{
  "scope": "3.1", "title": "3.1 登录与协议：页面流转总览",
  "thumb_w": 140, "col_w": 290,
  "lanes": [{"label": "入口", "row0": 0, "row1": 0}],
  "nodes": [{"id": "n1", "screen": "login", "col": 0, "row": 0},
            {"id": "start", "kind": "start", "label": "打开小程序", "sub": "", "col": 0, "row": 0}],
  "edges": [{"f": "n1", "t": "n2", "label": "点击登录", "kind": "normal",
             "fs": "r", "ts": "l", "fo": 0, "to": 0, "mid": 0, "route": "", "lx": 0, "ly": 0}]
}
"""
import re
from pathlib import Path

from . import i18n

SCREEN_KINDS = {"page", "state", "popup", "native"}
NODE_KINDS = {"start", "cond", "note"}          # 非页面节点
EDGE_KINDS = {"normal", "popup", "success", "boundary", "back"}
SIDES = {"l", "r", "t", "b"}
ROUTES = {"", "over", "under"}
PLATFORMS = {"miniprogram", "h5", "app", "web", "admin"}
ACTION_KEYS = {"click", "eval", "wait", "fill", "hover"}
DEMO_MODES = {"online", "local", "pending"}

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")


class Issue:
    def __init__(self, level, code, msg, en=None):
        # msg = 中文（历史文案，不改）；en = 对应的英文，项目语言为 en 时输出
        self.level, self.code, self.msg, self.en = level, code, msg, en

    def text(self):
        return i18n.t(self.msg, self.en)

    def __str__(self):
        icon = {"error": "❌", "warn": "⚠️ ", "info": "ℹ️ "}[self.level]
        return f"{icon} [{self.code}] {self.text()}"


def _strip_url(url):
    return re.split(r"[?#]", url, 1)[0]


def validate_screens(proj, draft=False):
    """返回 (issues, screens_dict)。screens_dict 供 flows 校验使用。"""
    issues = []
    try:
        data = proj.load_screens()
    except Exception as e:
        return [Issue("error", "SPEC-001", str(e), en=str(e))], {}

    if data.get("schema") != 1:
        issues.append(Issue("error", "SPEC-002", "screens.json 缺少 schema=1", en="screens.json is missing schema=1"))
    if "lang" in data and i18n.normalize(data.get("lang")) is None:
        issues.append(Issue("error", "SPEC-021", f"lang 只能是 {list(i18n.LANGS)} 之一，当前：{data.get('lang')!r}",
                            en=f"lang must be one of {list(i18n.LANGS)}, got: {data.get('lang')!r}"))
    if data.get("platform") not in PLATFORMS:
        issues.append(Issue("warn", "SPEC-003", f"platform 应为 {sorted(PLATFORMS)} 之一，当前：{data.get('platform')!r}", en=f"platform should be one of {sorted(PLATFORMS)}, got: {data.get('platform')!r}"))
    vp = data.get("viewport") or {}
    if not isinstance(vp.get("width"), int) or not isinstance(vp.get("height"), int):
        issues.append(Issue("error", "SPEC-004", "viewport 需包含整数 width/height", en="viewport must contain integer width/height"))

    st = data.get("style")
    if st is not None:
        if not isinstance(st, dict) or not st.get("name"):
            issues.append(Issue("warn", "SPEC-006", "style 应为 {\"name\": \"flat\", \"accent\": \"#1677FF\"}（accent 可省略）", en='style should look like {"name": "flat", "accent": "#1677FF"} (accent is optional)'))
        elif st.get("accent") and not re.match(r"^#[0-9A-Fa-f]{6}$", str(st["accent"])):
            issues.append(Issue("warn", "SPEC-007", f"style.accent 需为 #RRGGBB，当前：{st['accent']!r}", en=f"style.accent must be #RRGGBB, got: {st['accent']!r}"))

    dm = data.get("demo")
    if dm is not None:
        if not isinstance(dm, dict) or dm.get("mode") not in DEMO_MODES:
            issues.append(Issue("error", "SPEC-008", f"demo.mode 应为 {sorted(DEMO_MODES)} 之一", en=f"demo.mode should be one of {sorted(DEMO_MODES)}"))
        elif dm["mode"] == "online" and not re.match(r"^https://[A-Za-z0-9][A-Za-z0-9\-.]*(:\d+)?(/\S*)?$", str(dm.get("url", ""))):
            issues.append(Issue("error", "SPEC-009", f"demo.mode=online 时 demo.url 需为 https:// 开头的网址，当前：{dm.get('url')!r}", en=f"with demo.mode=online, demo.url must be an https:// address, got: {dm.get('url')!r}"))

    chapters = {c.get("id"): c for c in data.get("chapters", []) if isinstance(c, dict)}
    if not chapters:
        issues.append(Issue("warn", "SPEC-005", "chapters 为空：流程图与页面清单无法按章生成", en="chapters is empty: chapter-level flow diagrams and page lists cannot be generated"))

    screens, shots = {}, {}
    for i, s in enumerate(data.get("screens", [])):
        sid = s.get("id", "")
        where = f"screens[{i}]({sid or '?'})"
        if not ID_RE.match(sid or ""):
            issues.append(Issue("error", "SPEC-010", f"{where}: id 只能含字母/数字/下划线/连字符", en=f"{where}: id may only contain letters, digits, underscores and hyphens"))
            continue
        if sid in screens:
            issues.append(Issue("error", "SPEC-011", f"{where}: id 重复", en=f"{where}: duplicate id"))
            continue
        screens[sid] = s
        if not s.get("name"):
            issues.append(Issue("error", "SPEC-012", f"{where}: 缺少 name", en=f"{where}: name is missing"))
        if s.get("kind") not in SCREEN_KINDS:
            issues.append(Issue("error", "SPEC-013", f"{where}: kind 应为 {sorted(SCREEN_KINDS)} 之一", en=f"{where}: kind should be one of {sorted(SCREEN_KINDS)}"))
        if s.get("chapter") not in chapters:
            issues.append(Issue("error", "SPEC-014", f"{where}: chapter={s.get('chapter')!r} 未在 chapters 中登记", en=f"{where}: chapter={s.get('chapter')!r} is not registered in chapters"))
        url = s.get("url")
        if not url:
            issues.append(Issue("error", "SPEC-015", f"{where}: 缺少 url", en=f"{where}: url is missing"))
        elif not draft and not (proj.proto / _strip_url(url)).exists():
            issues.append(Issue("error", "SPEC-016", f"{where}: 原型文件不存在 prototype/{_strip_url(url)}", en=f"{where}: prototype file does not exist: prototype/{_strip_url(url)}"))
        shot = s.get("shot")
        if not shot or not str(shot).endswith(".png"):
            issues.append(Issue("error", "SPEC-017", f"{where}: shot 需为 .png 文件名", en=f"{where}: shot must be a .png file name"))
        else:
            if shot in shots:
                issues.append(Issue("error", "SPEC-018", f"{where}: shot 与 {shots[shot]} 重名", en=f"{where}: shot has the same name as {shots[shot]}"))
            shots[shot] = sid
            if "/" in shot or "\\" in shot:
                issues.append(Issue("error", "SPEC-019", f"{where}: shot 只能是文件名，不含目录", en=f"{where}: shot must be a file name without a directory"))
        for j, a in enumerate(s.get("actions", []) or []):
            if not isinstance(a, dict) or len(a) != 1 or next(iter(a)) not in ACTION_KEYS:
                issues.append(Issue("error", "SPEC-020", f"{where}: actions[{j}] 必须是仅含 {sorted(ACTION_KEYS)} 之一的对象", en=f"{where}: actions[{j}] must be an object with exactly one of {sorted(ACTION_KEYS)}"))
    return issues, screens


def validate_flow(proj, flow, screens, fname):
    issues = []
    scope = flow.get("scope")
    if not scope:
        issues.append(Issue("error", "FLOW-001", f"{fname}: 缺少 scope", en=f"{fname}: scope is missing"))
    if not flow.get("title"):
        issues.append(Issue("error", "FLOW-002", f"{fname}: 缺少 title", en=f"{fname}: title is missing"))

    nodes, used_screens = {}, set()
    for i, n in enumerate(flow.get("nodes", [])):
        nid = n.get("id", "")
        where = f"{fname} nodes[{i}]({nid or '?'})"
        if not ID_RE.match(nid or ""):
            issues.append(Issue("error", "FLOW-010", f"{where}: id 不合法", en=f"{where}: invalid id"))
            continue
        if nid in nodes:
            issues.append(Issue("error", "FLOW-011", f"{where}: id 重复", en=f"{where}: duplicate id"))
            continue
        nodes[nid] = n
        if not isinstance(n.get("col"), int) or not isinstance(n.get("row"), int):
            issues.append(Issue("error", "FLOW-012", f"{where}: col/row 需为整数", en=f"{where}: col/row must be integers"))
        if n.get("screen"):
            if n["screen"] not in screens:
                issues.append(Issue("error", "FLOW-013", f"{where}: 引用了不存在的页面 {n['screen']!r}", en=f"{where}: refers to a page that does not exist: {n['screen']!r}"))
            else:
                used_screens.add(n["screen"])
        else:
            if n.get("kind") not in NODE_KINDS:
                issues.append(Issue("error", "FLOW-014", f"{where}: 非页面节点的 kind 应为 {sorted(NODE_KINDS)} 之一", en=f"{where}: kind of a non-page node should be one of {sorted(NODE_KINDS)}"))
            if not n.get("label"):
                issues.append(Issue("error", "FLOW-015", f"{where}: 非页面节点需要 label", en=f"{where}: a non-page node needs a label"))

    for i, e in enumerate(flow.get("edges", [])):
        where = f"{fname} edges[{i}]"
        for end in ("f", "t"):
            if e.get(end) not in nodes:
                issues.append(Issue("error", "FLOW-020", f"{where}: {end}={e.get(end)!r} 不是已定义的节点", en=f"{where}: {end}={e.get(end)!r} is not a defined node"))
        if e.get("kind", "normal") not in EDGE_KINDS:
            issues.append(Issue("error", "FLOW-021", f"{where}: kind 应为 {sorted(EDGE_KINDS)} 之一", en=f"{where}: kind should be one of {sorted(EDGE_KINDS)}"))
        for key in ("fs", "ts"):
            if e.get(key, "r" if key == "fs" else "l") not in SIDES:
                issues.append(Issue("error", "FLOW-022", f"{where}: {key} 应为 l/r/t/b", en=f"{where}: {key} should be l/r/t/b"))
        if e.get("route", "") not in ROUTES:
            issues.append(Issue("error", "FLOW-023", f"{where}: route 应为空/over/under", en=f"{where}: route should be empty/over/under"))
        if not e.get("label"):
            issues.append(Issue("warn", "FLOW-024", f"{where}: 连线没有文字说明（读者看不出触发条件）", en=f"{where}: the edge has no text (readers cannot tell what triggers it)"))
        else:
            lab = str(e["label"]).strip()
            tgt = nodes.get(e.get("t")) or {}
            tname = (screens.get(tgt.get("screen")) or {}).get("name") or tgt.get("label")
            if tname and lab == tname:
                issues.append(Issue("warn", "FLOW-025", f"{where}: 标签「{lab}」与目标页面同名，读起来像重复；标签应写用户动作（如“点…”“发送…”）", en=f"{where}: label \"{lab}\" is the same as the target page name and reads like a repeat; write the user action (e.g. \"Tap ...\", \"Send ...\")"))
            if len(lab) > i18n.label_limit():
                issues.append(Issue("warn", "FLOW-026", f"{where}: 标签「{lab}」超过 14 字，渲染时会折行；请缩短",
                                    en=f"{where}: label \"{lab}\" is longer than {i18n.label_limit()} characters and will wrap when rendered; shorten it"))

    linked = {x for e in flow.get("edges", []) for x in (e.get("f"), e.get("t"))}
    for nid in nodes:
        if nid not in linked and len(nodes) > 1:
            issues.append(Issue("warn", "FLOW-030", f"{fname}: 节点 {nid} 没有任何连线（孤立节点）", en=f"{fname}: node {nid} has no edges (isolated node)"))

    if scope and scope != "all":
        must = {sid for sid, s in screens.items() if s.get("chapter") == scope}
        missing = sorted(must - used_screens)
        if missing:
            issues.append(Issue("warn", "FLOW-031", f"{fname}: 属于第 {scope} 章但未出现在本章流程图中：{', '.join(missing)}", en=f"{fname}: belongs to chapter {scope} but does not appear in the chapter flow diagram: {', '.join(missing)}"))
    return issues, used_screens


def validate_all(proj, draft=False):
    issues, screens = validate_screens(proj, draft=draft)
    all_used = set()
    for fp in proj.flow_files():
        try:
            import json
            flow = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as e:
            issues.append(Issue("error", "FLOW-000", f"{fp.name}: JSON 解析失败：{e}", en=f"{fp.name}: JSON parse failed: {e}"))
            continue
        fi, used = validate_flow(proj, flow, screens, fp.name)
        issues += fi
        all_used |= used
    if screens and proj.flow_files():
        orphans = sorted(set(screens) - all_used)
        if orphans:
            issues.append(Issue("warn", "FLOW-040", f"以下页面未出现在任何流程图中：{', '.join(orphans)}", en=f"these pages do not appear in any flow diagram: {', '.join(orphans)}"))
    return issues, screens
