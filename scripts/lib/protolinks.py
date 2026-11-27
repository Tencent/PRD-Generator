# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""protolinks：原型里“点得到的页面跳转”与 spec 流转是否一致（防止图、文、原型三者各说各话）。

背景：页面里有 <a href>，流程图和 PRD 却没有这条流转，评审时才发现；机器一直查不出。

规则（以“页面文件”为单位，同一 HTML 里的状态/弹窗共享一个文件）：
  PROTO-020 error  原型里有页面间跳转，流转里没有对应连线 → 补连线（再 flow、重生成清单与流转行）或删掉这个链接
  PROTO-021 warn   流转里画了跨页连线，原型对应页面里没有任何能点过去的入口
  PROTO-022 error  链接指向不存在的页面文件（死链）

识别的跳转写法：<a href="x.html">、任意元素的 data-go="x.html"、onclick / <script> 里的 location.href='x.html'。
不要求画进流程图（全局导航，但仍用于 PROTO-021 的“有入口”判断）：返回键（nav-bar__back）、底部 Tab（tab-bar__item）、PC 侧边栏（sidebar__item）与顶栏、面包屑（容器 class 含 breadcrumb）。
显式豁免：在该元素上加 data-flow-ignore 属性（纯示意、不属于业务流转的链接）。
"""
import json
import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path

from .spec import Issue

LOC_RE = re.compile(r"""location(?:\.href)?\s*=\s*['"]([^'"]+)['"]|location\.(?:assign|replace)\(\s*['"]([^'"]+)['"]""")
SKIP_PREFIX = ("javascript:", "#", "http:", "https:", "//", "mailto:", "tel:", "data:")
EXEMPT_CLASSES = ("nav-bar__back", "tab-bar__item", "sidebar__item", "sidebar__logo", "topbar")


class _Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []          # dict(target, exempt, text)
        self._a = None
        self._in_script = False
        self._crumb = 0          # 处在面包屑容器内的嵌套深度

    def _add(self, raw, exempt, text=""):
        if not raw:
            return
        raw = raw.strip()
        if not raw or raw.lower().startswith(SKIP_PREFIX):
            return
        path = re.split(r"[?#]", raw, 1)[0]
        if not path.lower().endswith(".html"):
            return
        self.links.append({"target": path, "exempt": exempt, "text": text})

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self._in_script = True
        cls = (a.get("class") or "")
        if "breadcrumb" in cls and tag != "a":
            self._crumb += 1
            self._crumb_tag = tag
        exempt = "data-flow-ignore" in a or self._crumb > 0 or any(c in cls for c in EXEMPT_CLASSES)
        if tag == "a" and a.get("href") is not None:
            rec_idx = len(self.links)
            self._add(a.get("href"), exempt)
            self._a = rec_idx if len(self.links) > rec_idx else None
        if a.get("data-go"):
            self._add(a.get("data-go"), exempt)
        oc = a.get("onclick") or ""
        for m in LOC_RE.finditer(oc):
            self._add(m.group(1) or m.group(2), exempt)

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False
        if tag == "a":
            self._a = None
        if self._crumb and tag == getattr(self, "_crumb_tag", None):
            self._crumb -= 1

    def handle_data(self, data):
        if self._in_script:
            for m in LOC_RE.finditer(data):
                self._add(m.group(1) or m.group(2), False)
        elif self._a is not None and data.strip():
            self.links[self._a]["text"] = (self.links[self._a]["text"] + data.strip())[:20]


def _file(url):
    return re.split(r"[?#]", url or "", 1)[0]


def _norm(base_file, target):
    """把页面里写的相对路径换算成相对 prototype/ 的路径。"""
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_file), target))


def analyze(proj):
    data = proj.load_screens() if proj.screens_path.exists() else {}
    screens = {s["id"]: s for s in data.get("screens", []) if s.get("url")}
    names = {}
    for s in screens.values():
        f = _file(s["url"])
        if f not in names or s.get("kind") == "page":
            names[f] = s.get("name", f)

    # 流转里的文件级连线
    flow_pairs = set()
    for fp in proj.flow_files():
        try:
            fl = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception:
            continue
        nodes = {n["id"]: n for n in fl.get("nodes", [])}
        for e in fl.get("edges", []):
            a, b = nodes.get(e.get("f")), nodes.get(e.get("t"))
            if not a or not b or a.get("screen") not in screens or b.get("screen") not in screens:
                continue
            fa, fb = _file(screens[a["screen"]]["url"]), _file(screens[b["screen"]]["url"])
            if fa != fb:
                flow_pairs.add((fa, fb))

    issues = []
    reach = set()               # 原型里实际存在的跳转（含返回键/Tab）
    seen = set()
    for f in sorted(names):
        page = proj.proto / f
        if not page.is_file():
            continue
        sc = _Scan()
        sc.feed(page.read_text(encoding="utf-8", errors="ignore"))
        for lk in sc.links:
            g = _norm(f, lk["target"])
            if g == f:
                continue
            if not (proj.proto / g).is_file():
                key = ("022", f, g)
                if key not in seen:
                    seen.add(key)
                    issues.append(Issue("error", "PROTO-022", f"prototype/{f}：链接指向不存在的页面 {lk['target']}",
                                    en=f"prototype/{f}: a link points to a page that does not exist: {lk['target']}"))
                continue
            reach.add((f, g))
            if lk["exempt"] or (f, g) in flow_pairs:
                continue
            key = ("020", f, g)
            if key in seen:
                continue
            seen.add(key)
            via = f"（“{lk['text']}”）" if lk["text"] else ""
            via_en = f' ("{lk["text"]}")' if lk["text"] else ""
            gname = names.get(g, g)
            issues.append(Issue("error", "PROTO-020",
                                f"原型 prototype/{f}（{names.get(f, f)}）有跳转到「{gname}」{via}，但流程图里没有 {names.get(f, f)}→{gname} 的连线",
                                en=f'prototype/{f} ({names.get(f, f)}) jumps to "{gname}"{via_en}, but the flow diagram has no {names.get(f, f)}→{gname} edge'))
    for (fa, fb) in sorted(flow_pairs):
        if (fa, fb) not in reach and (proj.proto / fa).is_file():
            issues.append(Issue("warn", "PROTO-021",
                                f"流程图里有 {names.get(fa, fa)}→{names.get(fb, fb)} 的连线，但原型 prototype/{fa} 里没有能点过去的入口",
                                en=f"the flow diagram has a {names.get(fa, fa)}→{names.get(fb, fb)} edge, but prototype/{fa} has no entry that leads there"))
    return issues
