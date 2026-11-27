# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""links：PRD 里“关联原型”行与“附录 B：可交互 Demo 页面”由 spec 生成，不手写。

三种 Demo 状态（spec.demo.mode）：
  pending  尚未发布（缺省）：各页面不写“关联原型”行；附录 B 只写“发布后补充”。托管后一次性回填
  online   已托管在线 Demo（prdkit demo online / 发布器写入）：关联原型写在线链接，附录 B 给出在线预览
  local    用户明确不托管（prdkit demo local 写入）：关联原型写本地相对路径，附录 B 写本地文件并说明“本版未发布在线 Demo”，交付物附 prototype.zip

用法：prdkit links            只预览将要改动的内容
      prdkit links --apply    写回 PRD（幂等，可重复运行；换状态后重跑即可整体切换）
"""
import re
from collections import OrderedDict

from . import i18n

LINE_PREFIX = "**关联原型**："
SECTION_RE = re.compile(r"页面交互说明\s*[—–-]\s*(.+)$")
NOTE_RE = re.compile(r"(（[^）]*）)\s*$")
POPUP_NOTE = "（进入页面后触发弹窗）"
PENDING_MARK = "在线 Demo 发布后"
PENDING_NOTE = f"> {PENDING_MARK}，此处将补充各页面的预览链接；页面效果以文中截图为准。"


def _pending_note():
    if i18n.cur() == "en":
        return (f"> {i18n.W('pending_mark')}, preview links for every page will be added here; "
                "the screenshots in this document are the reference for page appearance.")
    return PENDING_NOTE


def demo_info(data):
    d = data.get("demo") or {}
    return (d.get("mode") or "pending"), d


def _file(url):
    return re.split(r"[?#]", url, 1)[0]


def target(data, screen):
    """某个页面在当前 demo 状态下的访问地址（online：在线链接；local：相对路径；pending：没有）。"""
    mode, d = demo_info(data)
    if mode == "pending":
        return None
    if mode == "online":
        return f"{d['url'].rstrip('/')}/{screen['url']}"
    return f"prototype/{screen['url']}"


def relation_line(data, screen, old_line=""):
    """“关联原型”行；pending 状态下返回 None（该行不应存在）。"""
    mode, _ = demo_info(data)
    t = target(data, screen)
    if t is None:
        return None
    note = ""
    m = i18n.note_re().search(old_line or "")
    if m:
        note = m.group(1)
    elif screen.get("kind") == "popup":
        note = i18n.W("popup_note")
    body = f"[{i18n.W('online_text')}]({t})" if mode == "online" else f"`{t}`"
    return f"{i18n.W('rel_prefix')}{body}{note}"


def _groups(data):
    """按原型文件分组：{文件: [screen...]}，保持 spec 中的先后顺序。"""
    g = OrderedDict()
    for s in data.get("screens", []):
        g.setdefault(_file(s["url"]), []).append(s)
    return g


def appendix_block(data, project_name):
    """返回附录 B 的 Markdown 行（表格 + 说明，不含标题）。"""
    mode, d = demo_info(data)
    if mode == "pending":
        return [_pending_note()]
    online = mode == "online"
    en = i18n.cur() == "en"
    if en:
        rows = [f"| Demo page | PRD section | {'Online preview' if online else 'Local file'} |", "|---|---|---|"]
    else:
        rows = [f"| Demo 页面 | 对应 PRD 章节 | {'在线预览' if online else '本地文件'} |", "|---|---|---|"]
    for f, items in _groups(data).items():
        main = next((x for x in items if x.get("kind") == "page"), items[0])
        extras = [x["name"] for x in items if x is not main]
        if en:
            name = main["name"] + (f" (incl. {', '.join(extras)})" if extras else "")
        else:
            name = main["name"] + (f"（含：{'、'.join(extras)}）" if extras else "")
        secs = " / ".join(x.get("section") or x["chapter"] for x in items)
        cell = f"[{'Open' if en else '打开'}]({target(data, main)})" if online else f"`{target(data, main)}`"
        rows.append(f"| {name} | {secs} | {cell} |")
    if online:
        url = d["url"].rstrip("/")
        note = f"> Online demo entry: [{url}/]({url}/)." if en else f"> 在线 Demo 入口：[{url}/]({url}/)。"
    elif en:
        note = (f"> In this version the {i18n.W('local_mark')}. Use the `{project_name}-prototype.zip` package delivered with this "
                "document: unzip it and open `index.html` in a browser; the screenshots in this document are the reference for page appearance.")
    else:
        note = (f"> 本版未发布在线 Demo。请使用随交付包提供的 `{project_name}-prototype.zip`，解压后用浏览器打开 "
                f"`index.html` 即可体验；各页面效果以文中截图为准。")
    return rows + ["", note]


def _expected_targets(data):
    """附录 B 里应当出现的访问地址（每个原型文件一个）；pending 状态没有。"""
    out = []
    for f, items in _groups(data).items():
        main = next((x for x in items if x.get("kind") == "page"), items[0])
        t = target(data, main)
        if t:
            out.append(t)
    return out


def _appendix_range(lines, heads):
    """返回 (标题行号, 内容起点, 内容终点)；找不到附录 B 返回 None。

    内容 = 标题之后、到下一个标题/分隔线/文末为止的全部内容（表格、“> ”说明、模板注释、空行）。
    本节整体由 links 生成，所以整段替换：这样模板里的占位表格和 AI_INSTRUCTION 注释也会被一并清掉。"""
    for k, (i, lvl, title) in enumerate(heads):
        if i18n.appendix_b_match(title):
            end = len(lines)
            for (j, l2, _t) in heads[k + 1:]:
                if l2 <= lvl:
                    end = j
                    break
            for j in range(i + 1, end):
                if lines[j].strip() == "---":
                    end = j
                    break
            while end > i + 1 and not lines[end - 1].strip():
                end -= 1
            return i, i + 1, end
    return None


def apply(proj, write=False):
    """返回 (新文本, 改动清单)。write=True 时写回 PRD。"""
    from . import lint
    i18n.set_lang(proj.lang)
    md = proj.prd_md()
    if not md:
        raise SystemExit(i18n.t("❌ 未找到 PRD 文件（期望项目目录下有 *-prd.md）", "❌ PRD file not found (expected *-prd.md in the project directory)"))
    data = proj.load_screens()
    text = md.read_text(encoding="utf-8")
    lines, in_code = lint._split(text)
    heads = lint._headings(lines, in_code)
    by_name = {s["name"]: s for s in data.get("screens", [])}
    changes = []

    edits = []   # (行号, "replace"/"insert"/"delete"/"block", 内容)
    for k, (i, lvl, title) in enumerate(heads):
        m = i18n.section_re().search(title)
        if not m:
            continue
        s = by_name.get(m.group(1).strip())
        if not s:
            continue
        end = lint._section_end(heads, k, lines)
        cur = next((j for j in range(i + 1, end) if lines[j].startswith(i18n.W("rel_prefix"))), None)
        if cur is not None:
            new = relation_line(data, s, lines[cur])
            if new is None:
                edits.append((cur, "delete", None))
                changes.append(i18n.t(f"「{s['name']}」关联原型行移除（Demo 尚未发布，发布后统一回填）",
                                      f'Prototype line of "{s["name"]}" removed (demo not published yet; back-filled after publishing)'))
            elif new != lines[cur]:
                edits.append((cur, "replace", new))
                changes.append(i18n.t(f"「{s['name']}」关联原型 → {target(data, s)}", f'Prototype of "{s["name"]}" -> {target(data, s)}'))
        else:
            new = relation_line(data, s)
            if new is None:
                continue
            flow = next((j for j in range(i + 1, end) if lines[j].startswith(i18n.W("transit_key"))), None)
            edits.append(((flow if flow is not None else i), "insert", new))
            changes.append(i18n.t(f"「{s['name']}」补充关联原型行 → {target(data, s)}", f'Prototype line added for "{s["name"]}" -> {target(data, s)}'))

    ap = _appendix_range(lines, heads)
    from .demo import deliver_name
    new_block = [""] + appendix_block(data, deliver_name(proj, data))
    if ap:
        _, s0, e0 = ap
        if lines[s0:e0] != new_block:
            edits.append((s0, "block", (e0, new_block)))
            changes.append(i18n.t("附录 B 按 spec 重新生成", "Appendix B regenerated from the spec"))
    else:
        changes.append(i18n.t("⚠️ 未找到“附录B”标题，附录未生成（请按模板补上标题后重跑）",
                              "⚠️ Heading \"Appendix B\" not found, so the appendix was not generated (add the heading from the template and rerun)"))

    for pos, kind, payload in sorted(edits, key=lambda x: -x[0]):
        if kind == "replace":
            lines[pos] = payload
        elif kind == "insert":
            lines[pos + 1:pos + 1] = ["", payload]
        elif kind == "delete":
            # 连同它前面的一个空行一起删，避免留下两个连续空行
            lo = pos - 1 if pos > 0 and not lines[pos - 1].strip() else pos
            del lines[lo:pos + 1]
        else:
            e0, blk = payload
            lines[pos:e0] = blk
    new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    if write and new_text != text:
        md.write_text(new_text, encoding="utf-8")
    return new_text, changes
