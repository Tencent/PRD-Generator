# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""migrate：把旧版 flowmap-config.json 转换为新的 spec（screens.json + flows/all.json）。

旧格式信息量不足（没有章节、没有页面状态、弹窗没有截图），所以转换结果只是“可运行的起点”：
  - page 节点      → screens（kind=page），url 按 prototype/pages/<截图名>.html 推断
  - popup/boundary → 流程图里的 note 节点（旧版本就没有它们的截图）
  - decision       → cond 节点
  - layers         → lanes
转换后请人工补充：章节归属、弹窗/状态的真实截图。
"""
from pathlib import Path

from . import i18n
from .common import dump_json, load_json

COLOR_MAP = {"normal": "normal", "success": "success", "convert": "normal",
             "back": "back", "popup": "popup", "boundary": "boundary"}


def _sides(a, b):
    if a["row"] == b["row"]:
        return ("r", "l") if b["col"] >= a["col"] else ("l", "r")
    return ("b", "t") if b["row"] > a["row"] else ("t", "b")


def convert(proj, force=False):
    legacy = proj.root / "flowmap-config.json"
    if not legacy.exists():
        raise SystemExit(i18n.t(f"未找到旧配置：{legacy}", f"Old config not found: {legacy}"))
    if proj.screens_path.exists() and not force:
        raise SystemExit(i18n.t(f"{proj.screens_path} 已存在。如需覆盖请加 --force。", f"{proj.screens_path} already exists. Add --force to overwrite it."))

    old = load_json(legacy)
    notes = []
    screens, nodes, id_map = [], [], {}
    pc = False

    for n in old.get("nodes", []):
        nid, typ = n["id"], n.get("type", "page")
        row, col = int(n.get("layer", 0)), int(n.get("col", 0))
        if typ == "page":
            shot = n.get("screenshot") or f"{nid}.png"
            stem = Path(shot).stem
            url = f"pages/{stem}.html"
            if not (proj.proto / url).exists():
                notes.append(f"页面 {nid}：未找到 prototype/{url}，请核对 url")
            sc = {"id": nid, "name": n.get("label", nid), "kind": "page", "chapter": "all",
                  "section": "", "url": url, "shot": shot, "full_page": True}
            if n.get("viewport") == 1440:
                sc["viewport"] = {"width": 1440, "height": 900, "dpr": 2}
                pc = True
            screens.append(sc)
            nodes.append({"id": nid, "screen": nid, "col": col, "row": row})
        else:
            kind = "cond" if typ == "decision" else "note"
            nodes.append({"id": nid, "kind": kind, "label": n.get("label", nid), "col": col, "row": row})
            tip = "如需展示真实弹窗，请在 screens 中登记并截图" if typ == "popup" else "按需保留或删除"
            notes.append(f"节点 {nid}（旧类型 {typ}）已降级为 {kind} 说明节点；{tip}")
        id_map[nid] = {"row": row, "col": col}

    edges = []
    for c in old.get("connections", []):
        if c["from"] not in id_map or c["to"] not in id_map:
            notes.append(f"连线 {c['from']}→{c['to']} 引用了不存在的节点，已跳过")
            continue
        fs, ts = _sides(id_map[c["from"]], id_map[c["to"]])
        edges.append({"f": c["from"], "t": c["to"], "label": c.get("label", ""),
                      "kind": COLOR_MAP.get(c.get("color", "normal"), "normal"), "fs": fs, "ts": ts})

    lanes = [{"label": l.get("name", f"层{i}"), "row0": i, "row1": i} for i, l in enumerate(old.get("layers", []))]

    spec = {
        "schema": 1,
        "name": old.get("title", proj.name),
        "version": "",
        "platform": "admin" if pc else "h5",
        "viewport": {"width": 390, "height": 844, "dpr": 2},
        "chapters": [{"id": "all", "title": "全部页面（待按章节拆分）"}],
        "screens": screens,
    }
    flow = {"scope": "all", "title": old.get("title", "整体页面流程图"),
            "thumb_w": 150, "col_w": 230, "lanes": lanes, "nodes": nodes, "edges": edges}
    dump_json(proj.screens_path, spec)
    dump_json(proj.flows_dir / "all.json", flow)
    return len(screens), len(edges), notes
