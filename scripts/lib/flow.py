# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""flow：按 spec/flows/*.json 渲染页面流转图（PNG），并做几何自检；同时可由流转关系生成“页面清单”表。

设计要点（来自本项目实战中效果最好的做法）：
- 页面、状态、弹窗、系统原生弹窗都用真实截图作节点，带角标；副标题放 PRD 小节号，图文可互相对照
- 每条边显式语义：普通 / 弹窗 / 成功 / 异常 / 返回；标签为白底胶囊，放在最长的一段上
- 端口自动错开、同行被挡自动绕行、over/under 绕行线自动分层，减少手工调参
- 渲染后做自检：连线穿过节点、标签压住节点或互相压住、连线重叠、交叉过多
- 浏览器渲染：无字体路径依赖，无外部服务依赖
"""
import html as htmllib
from pathlib import Path

from . import i18n
from . import spec as specmod
from .shot import _Server

COLORS = {"normal": "#1C1C1E", "popup": "#2F6FEB", "success": "#1E9E5A", "boundary": "#E07B00", "back": "#8A4FD8"}
LEGEND = [("普通跳转", "normal"), ("弹窗/浮层", "popup"), ("成功/完成", "success"), ("异常/边界", "boundary"), ("返回/循环", "back")]
DASHED = {"popup", "boundary", "back"}
LEGEND_EN = ["Normal transition", "Popup / overlay", "Success / done", "Exception / boundary", "Back / loop"]
KIND_LABEL = {"page": "页面", "state": "页面状态", "popup": "弹窗"}
LABEL_BLOCK = 44          # 缩略图下方名称区高度
ROW_GAP = 92
PAD_X = 60
TOP = 130
FONT_STACK = "'MiSans','PingFang SC','HarmonyOS Sans SC','Noto Sans CJK SC','Source Han Sans SC','Microsoft YaHei','WenQuanYi Micro Hei',sans-serif"


def flow_out_name(scope):
    return "flow-" + str(scope).replace(".", "-") + ".png"


def _native_label(platform):
    if i18n.cur() == "en":
        return i18n.W("native_wechat") if platform == "miniprogram" else i18n.W("native_system")
    return "微信原生" if platform == "miniprogram" else "系统原生"


def _tag(s, platform):
    k = s["kind"]
    en = i18n.cur() == "en"
    if k == "popup":
        return ("Popup" if en else "弹窗"), "pop"
    if k == "native":
        return _native_label(platform), "nat"
    if k == "state":
        return ("State" if en else "状态"), "st"
    return "", ""


def display_name(n, screens):
    return screens[n["screen"]]["name"] if n.get("screen") else n.get("label", n["id"])


# ───────────────────────── 布局 ─────────────────────────
def _layout(flow, screens, base_vp, platform, widen=True, measure_nodes=None):
    tw = flow.get("thumb_w", 150)
    col_w = flow.get("col_w", tw + 150)
    nodes = {}
    for n in flow["nodes"]:
        d = dict(n)
        d["_screen"] = screens.get(n.get("screen")) if n.get("screen") else None
        if d["_screen"]:
            s = d["_screen"]
            vp = s.get("viewport") or base_vp
            aspect = vp["height"] / vp["width"]
            if vp["width"] >= 900:           # PC 宽屏
                d["w"] = tw * 2.2
                d["h"] = d["w"] * aspect
            else:
                d["w"] = tw
                d["h"] = min(tw * aspect, tw * 2.2)
            d["ext"] = LABEL_BLOCK
            d["_txt"] = (n.get("label", s["name"]), n.get("sub", s.get("section", "")))
        else:
            d["w"] = max(col_w - 60, 150)
            d["h"] = 64
            d["ext"] = 0
        nodes[d["id"]] = d

    if measure_nodes:
        hs = measure_nodes([(n["_txt"][0], n["_txt"][1], n["w"]) for n in nodes.values() if n.get("_txt")])
        for n in nodes.values():
            if n.get("_txt"):
                n["ext"] = hs[(n["_txt"][0], n["_txt"][1], round(n["w"]))]
    ncols = max(n["col"] for n in nodes.values()) + 1
    nrows = max(n["row"] for n in nodes.values()) + 1
    colw = [col_w] * ncols
    for n in nodes.values():
        colw[n["col"]] = max(colw[n["col"]], n["w"] + 70)
    if widen:   # 同行相邻两页之间的横向连线：按标签实测宽度自动撑开列距
        for _ in range(2):
            for e in flow["edges"]:
                a, b = nodes.get(e["f"]), nodes.get(e["t"])
                if not a or not b or not e.get("label") or a["row"] != b["row"] or e.get("route"):
                    continue
                if abs(a["col"] - b["col"]) != 1 or e.get("fs", "r") not in "lr" or e.get("ts", "l") not in "lr":
                    continue
                lo, hi = (a, b) if a["col"] < b["col"] else (b, a)
                need = _label_size(e["label"])[0] + 36 + lo["w"] / 2 + hi["w"] / 2
                have = (colw[lo["col"]] + colw[hi["col"]]) / 2
                if have < need:
                    colw[lo["col"]] += 2 * (need - have) / 1.0 * 0.5 + 0.0
    rowh_core = [64.0] * nrows
    for n in nodes.values():
        rowh_core[n["row"]] = max(rowh_core[n["row"]], n["h"])
    row_ext = [LABEL_BLOCK] * nrows
    for n in nodes.values():
        if n["ext"]:
            row_ext[n["row"]] = max(row_ext[n["row"]], n["ext"])
    rowh = [h + row_ext[i] + ROW_GAP for i, h in enumerate(rowh_core)]

    colx, acc = [], PAD_X
    for w in colw:
        colx.append(acc + w / 2)
        acc += w
    rowtop, acc = [], TOP
    for h in rowh:
        rowtop.append(acc)
        acc += h
    W = int(2 * PAD_X + sum(colw))
    H = int(acc - ROW_GAP + 90 + (46 if flow.get("lanes") else 0))
    for n in nodes.values():
        n["cx"] = colx[n["col"]] + n.get("dx", 0)
        n["cy"] = rowtop[n["row"]] + rowh_core[n["row"]] / 2 + n.get("dy", 0)
    return nodes, W, H, rowtop, rowh


def _fit_canvas(nodes, edges, H, rowtop, flow):
    """按连线实际范围撑开画布：上方绕行线不顶到标题，下方绕行线不压图例。"""
    ys = [y for e in edges for _, y in e["pts"]]
    shift = 0
    if ys and min(ys) < 74:
        shift = 74 - min(ys)
    if shift:
        for n in nodes.values():
            n["cy"] += shift
        for e in edges:
            e["pts"] = [(x, y + shift) for x, y in e["pts"]]
        rowtop = [t + shift for t in rowtop]
    bottoms = [n["cy"] + n["h"] / 2 + n["ext"] for n in nodes.values()] + [y for e in edges for _, y in e["pts"]]
    need = max(bottoms) + 70
    return int(max(H + shift, need)), rowtop


def _port(n, side, off):
    cx, cy, w, h = n["cx"], n["cy"], n["w"], n["h"]
    if side == "r":
        return cx + w / 2, cy + off
    if side == "l":
        return cx - w / 2, cy + off
    if side == "t":
        return cx + off, cy - h / 2
    return cx + off, cy + h / 2 + n["ext"]


def _auto_sides(a, b):
    if a["row"] == b["row"]:
        return ("r", "l") if b["col"] >= a["col"] else ("l", "r")
    return ("b", "t") if b["row"] > a["row"] else ("t", "b")


def _blocked_same_row(a, b, nodes):
    if a["row"] != b["row"]:
        return False
    lo, hi = sorted((a["col"], b["col"]))
    return any(n["row"] == a["row"] and lo < n["col"] < hi for n in nodes.values())


def _fix_direction(e, nodes):
    """出入口方向与目标位置矛盾时（折回穿过自身），自动改走上下方向。"""
    a, b = nodes[e["f"]], nodes[e["t"]]
    fs, ts = e["fs"], e["ts"]
    if fs in "lr" and ts in "tb":
        x2 = b["cx"] + e.get("to", 0)
        left, right = a["cx"] - a["w"] / 2, a["cx"] + a["w"] / 2
        if (fs == "r" and x2 < right + 6) or (fs == "l" and x2 > left - 6):
            e["fs"] = "b" if b["cy"] > a["cy"] else "t"
            e.pop("fo", None)
            e["_fixed"] = True
    elif ts in "lr" and fs in "tb":
        x1 = a["cx"] + e.get("fo", 0)
        left, right = b["cx"] - b["w"] / 2, b["cx"] + b["w"] / 2
        if (ts == "l" and x1 > left - 6) or (ts == "r" and x1 < right + 6):
            e["ts"] = "t" if a["cy"] < b["cy"] else "b"
            e.pop("to", None)
            e["_fixed"] = True


def _stagger_fanout(edges, nodes):
    """同一页面同一侧扇出多条折线时，按目标远近分层：近的深、远的浅，避免共线与交叉。"""
    groups = {}
    for e in edges:
        if "mid" in e or e.get("route"):
            continue
        fs, ts = e["fs"], e["ts"]
        if fs in "tb" and ts in "tb":
            groups.setdefault((e["f"], fs, "tb"), []).append(e)
        elif fs in "lr" and ts in "lr":
            groups.setdefault((e["f"], fs, "lr"), []).append(e)
    for (nid, fs, axis), items in groups.items():
        a = nodes[nid]
        for sign in (-1, 1):
            if axis == "tb":
                side = [e for e in items if (nodes[e["t"]]["cx"] - a["cx"]) * sign > 1]
                dist = lambda e: abs(nodes[e["t"]]["cx"] - a["cx"])
            else:
                side = [e for e in items if (nodes[e["t"]]["cy"] - a["cy"]) * sign > 1]
                dist = lambda e: abs(nodes[e["t"]]["cy"] - a["cy"])
            if len(side) < 2:
                continue
            side.sort(key=dist, reverse=True)           # 远的在前（最浅）
            n = len(side)
            for idx, e in enumerate(side):
                e["mid"] = (idx - (n - 1) / 2) * 16 * (1 if fs in "br" else -1)


def _resolve_edges(flow, nodes):
    """补全端口、绕行方式、偏移；返回带 pts 的边列表。"""
    edges = []
    for i, e in enumerate(flow["edges"]):
        e = dict(e)
        a, b = nodes[e["f"]], nodes[e["t"]]
        if "fs" not in e and "ts" not in e and "route" not in e and _blocked_same_row(a, b, nodes):
            e["fs"], e["ts"], e["route"] = "t", "t", "over"
        auto = _auto_sides(a, b)
        e.setdefault("fs", auto[0])
        e.setdefault("ts", auto[1])
        e["_i"] = i
        edges.append(e)

    for e in edges:
        _fix_direction(e, nodes)

    groups = {}
    for e in edges:
        for end, side_key, off_key, other in (("f", "fs", "fo", "t"), ("t", "ts", "to", "f")):
            if off_key in e:
                continue
            groups.setdefault((e[end], e[side_key]), []).append((e, off_key, other))
    for (nid, side), items in groups.items():
        k = len(items)
        if k < 2:
            continue
        n = nodes[nid]
        if side in ("l", "r"):
            items.sort(key=lambda it: nodes[it[0][it[2]]]["cy"])
            span = max(min(n["h"] - 24, 22 * (k - 1)), 8)
        else:
            items.sort(key=lambda it: nodes[it[0][it[2]]]["cx"])
            span = max(min(n["w"] - 24, 34 * (k - 1)), 8)
        for idx, (e, off_key, _) in enumerate(items):
            e[off_key] = -span / 2 + span * idx / (k - 1)

    _stagger_fanout(edges, nodes)

    lane_count = {}
    for e in edges:
        if e.get("route") in ("over", "under") and "mid" not in e:
            key = (nodes[e["f"]]["row"], e["route"])
            idx = lane_count.get(key, 0)
            lane_count[key] = idx + 1
            e["mid"] = -18 * idx if e["route"] == "over" else 18 * idx

    for e in edges:
        a, b = nodes[e["f"]], nodes[e["t"]]
        fs, ts = e["fs"], e["ts"]
        p1 = _port(a, fs, e.get("fo", 0))
        p2 = _port(b, ts, e.get("to", 0))
        (x1, y1), (x2, y2) = p1, p2
        mid, route = e.get("mid", 0), e.get("route", "")
        pts = [p1]
        if route == "over":
            ym = min(y1, y2) - 34 + mid
            pts += [(x1, ym), (x2, ym)]
        elif route == "under":
            ym = max(y1, y2) + 30 + mid
            pts += [(x1, ym), (x2, ym)]
        elif fs in "lr" and ts in "lr":
            if abs(y1 - y2) > 1:
                xm = (x1 + x2) / 2 + mid
                pts += [(xm, y1), (xm, y2)]
        elif fs in "tb" and ts in "tb":
            if abs(x1 - x2) > 1:
                ym = (y1 + y2) / 2 + mid
                pts += [(x1, ym), (x2, ym)]
        elif fs in "lr" and ts in "tb":
            pts += [(x2, y1)]
        else:
            pts += [(x1, y2)]
        pts.append(p2)
        e["pts"] = pts
    return edges


# ───────────────────────── HTML ─────────────────────────
def _build_html(proj, flow, nodes, edges, W, H, rowtop, rowh, platform, missing_imgs, draft=False):
    out_lane, out_node, svg, labels = [], [], [], []
    for ln in flow.get("lanes", []):
        y0 = rowtop[ln["row0"]] - 34
        y1 = rowtop[ln["row1"]] + rowh[ln["row1"]] - 30
        out_lane.append(f'<div class="lane" style="left:20px;top:{y0}px;width:{W - 40}px;height:{y1 - y0}px"><span>{htmllib.escape(ln["label"])}</span></div>')

    for n in nodes.values():
        x, y = n["cx"] - n["w"] / 2, n["cy"] - n["h"] / 2
        s = n["_screen"]
        if s:
            tag, cls = _tag(s, platform)
            tg = f'<i class="tg">{tag}</i>' if tag else ""
            sub = n.get("sub", s.get("section", ""))
            if n["id"] in missing_imgs:
                inner = f'<div class="miss">{i18n.t("待绘制" if draft else "缺少截图", "To be drawn" if draft else "Screenshot missing")}</div>'
            else:
                inner = f'<img src="../images/{htmllib.escape(s["shot"])}">'
            out_node.append(
                f'<div class="nd" style="left:{x:.1f}px;top:{y:.1f}px;width:{n["w"]:.1f}px">'
                f'<div class="th {cls}" style="height:{n["h"]:.1f}px">{inner}{tg}</div>'
                f'<div class="lb">{htmllib.escape(n.get("label", s["name"]))}</div>'
                f'<div class="sb2">{htmllib.escape(sub)}</div></div>')
        else:
            out_node.append(
                f'<div class="bx {n["kind"]}" style="left:{x:.1f}px;top:{y:.1f}px;width:{n["w"]:.1f}px;height:{n["h"]:.1f}px">'
                f'<div><b>{htmllib.escape(n["label"])}</b><small>{htmllib.escape(n.get("sub", ""))}</small></div></div>')

    for e in edges:
        kind = e.get("kind", "normal")
        c = COLORS[kind]
        dash = ' stroke-dasharray="7 5"' if kind in DASHED else ""
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in e["pts"])
        svg.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="2.2" stroke-linejoin="round"{dash} marker-end="url(#ar_{kind})"/>')
        if e.get("label") and e.get("_lab"):
            lx, ly, _, _ = e["_lab"]
            labels.append(f'<div class="el" data-i="{e["_i"]}" style="left:{lx:.0f}px;top:{ly:.0f}px;color:{c};border-color:{c}">{htmllib.escape(e["label"])}</div>')

    marks = "".join(
        f'<marker id="ar_{k}" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L9,4.5 L0,9 z" fill="{c}"/></marker>'
        for k, c in COLORS.items())
    legend = "".join(
        f'<span><i style="background:{COLORS[k]}"></i>{t}</span>' for t, k in ([(LEGEND_EN[i], k) for i, (_, k) in enumerate(LEGEND)] if i18n.cur() == "en" else LEGEND))
    css = f"""body{{margin:0;background:#fff;font-family:{FONT_STACK}}}
#c{{position:relative;width:{W}px;height:{H}px;background:#fff;overflow:hidden}}
.ttl{{position:absolute;left:0;right:0;top:20px;text-align:center;font-size:26px;font-weight:600;color:#1C1C1E}}
.lg{{position:absolute;left:0;right:0;bottom:16px;justify-content:center;font-size:12px;color:#555;display:flex;gap:14px}}
.lg i{{display:inline-block;width:18px;height:3px;margin-right:5px;vertical-align:middle;border-radius:2px}}
.lane{{position:absolute;background:#F6F7F9;border:1px solid #E3E6EA;border-radius:14px}}
.lane span{{position:absolute;left:14px;top:8px;font-size:15px;color:#8A9099;font-weight:500}}
.nd{{position:absolute;text-align:center}}
.th{{position:relative;border-radius:14px;border:1.5px solid #CBD0D6;background:#eee;box-shadow:0 4px 14px rgba(0,0,0,.1)}}
.th img{{width:100%;height:100%;object-fit:cover;object-position:top;display:block;border-radius:12px}}
.th.pop{{border-color:#2F6FEB}}.th.nat{{border-color:#07C160}}.th.st{{border-style:dashed;border-color:#8A9099}}
.miss{{height:100%;display:flex;align-items:center;justify-content:center;color:#999;font-size:13px}}
.tg{{position:absolute;left:4px;top:-23px;font-style:normal;font-size:11px;line-height:16px;color:#fff;background:#2F6FEB;border-radius:8px;padding:1px 7px;z-index:2}}
.nat .tg{{background:#07C160}}.st .tg{{background:#6B7280}}
.lb{{font-size:14px;font-weight:600;color:#1C1C1E;margin-top:7px;line-height:1.3}}
.sb2{{font-size:12px;color:#7A808A;margin-top:1px;line-height:1.3}}
.bx{{position:absolute;display:flex;align-items:center;justify-content:center;text-align:center;border-radius:14px;font-size:13px;line-height:1.35;padding:4px 8px;box-sizing:border-box}}
.bx b{{display:block;font-weight:600}}.bx small{{display:block;color:inherit;opacity:.75;font-size:12px;margin-top:2px;font-weight:400}}
.bx.note{{background:#FFF8E8;border:1.5px dashed #E0A93B;color:#7A5200}}
.bx.cond{{background:#EEF3FF;border:1.5px solid #2F6FEB;color:#1B3F94;border-radius:32px}}
.bx.start{{background:#1C1C1E;color:#fff;border-radius:32px}}
.el{{position:absolute;transform:translate(-50%,-50%);background:#fff;border:1px solid;border-radius:9px;padding:2px 8px;font-size:12px;text-align:center;line-height:1.35;font-weight:500;width:max-content;max-width:210px}}
svg{{position:absolute;left:0;top:0}}"""
    html_open = '<html lang="en">' if i18n.cur() == "en" else "<html>"      # 中文保持原样：加 lang 会让 Chrome 换汉字字形，截图字节就变了
    return (f'<!DOCTYPE html>{html_open}<head><meta charset="utf-8"><style>{css}</style></head><body><div id="c">'
            f'<div class="ttl">{htmllib.escape(flow["title"])}</div><div class="lg">{legend}</div>'
            f'{"".join(out_lane)}<svg width="{W}" height="{H}"><defs>{marks}</defs>{"".join(svg)}</svg>'
            f'{"".join(out_node)}{"".join(labels)}</div></body></html>')


# ───────────────────────── 几何自检 ─────────────────────────
def _segs(pts):
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _seg_hits_rect(p, q, r, eps=1.0):
    (x1, y1), (x2, y2) = p, q
    l, t, rr, b = r
    if abs(y1 - y2) < 0.5:
        return t + eps < y1 < b - eps and max(min(x1, x2), l + eps) < min(max(x1, x2), rr - eps)
    if abs(x1 - x2) < 0.5:
        return l + eps < x1 < rr - eps and max(min(y1, y2), t + eps) < min(max(y1, y2), b - eps)
    return False


def _rects_overlap(a, b, pad=0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def _geometry_check(nodes, edges, W, H):
    issues = []
    name = lambda n: n.get("label") or (n["_screen"]["name"] if n.get("_screen") else n["id"])
    block, thumb = {}, {}
    for nid, n in nodes.items():
        l, t = n["cx"] - n["w"] / 2, n["cy"] - n["h"] / 2
        thumb[nid] = (l, t, l + n["w"], t + n["h"])
        block[nid] = (l, t, l + n["w"], t + n["h"] + n["ext"])
    for e in edges:
        segs = _segs(e["pts"])
        for si, (p, q) in enumerate(segs):
            for nid in nodes:
                own_f, own_t = nid == e["f"], nid == e["t"]
                if own_f and si == 0:
                    continue
                if own_t and si == len(segs) - 1:
                    continue
                rect = thumb[nid] if (own_f or own_t) else block[nid]
                if _seg_hits_rect(p, q, rect):
                    issues.append(specmod.Issue("error", "FLOWGEO-01",
                        f"连线「{e['f']}→{e['t']}（{e.get('label', '')}）」穿过节点「{name(nodes[nid])}」；调整 fs/ts/route/mid，或把节点挪位",
                        en=f"edge \"{e['f']}→{e['t']} ({e.get('label', '')})\" crosses node \"{name(nodes[nid])}\"; adjust fs/ts/route/mid or move the node"))
                    break
    cross = {i: 0 for i in range(len(edges))}
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            for (p, q) in _segs(edges[i]["pts"]):
                for (r, s) in _segs(edges[j]["pts"]):
                    hv = abs(p[1] - q[1]) < 0.5, abs(r[1] - s[1]) < 0.5
                    if hv[0] == hv[1]:
                        k = 1 if hv[0] else 0          # 同向：比较共线并求重叠长度
                        c1, c2 = (p[k] + q[k]) / 2, (r[k] + s[k]) / 2
                        o = 1 - k
                        ov = min(max(p[o], q[o]), max(r[o], s[o])) - max(min(p[o], q[o]), min(r[o], s[o]))
                        if abs(c1 - c2) < 1.0 and ov > 8:
                            issues.append(specmod.Issue("warn", "FLOWGEO-02",
                                f"连线「{edges[i]['f']}→{edges[i]['t']}」与「{edges[j]['f']}→{edges[j]['t']}」有 {ov:.0f}px 重叠；用 fo/to 或 mid 错开",
                                en=f"edges \"{edges[i]['f']}→{edges[i]['t']}\" and \"{edges[j]['f']}→{edges[j]['t']}\" overlap by {ov:.0f}px; separate them with fo/to or mid"))
                    else:
                        h, v = ((p, q), (r, s)) if hv[0] else ((r, s), (p, q))
                        hx1, hx2 = sorted((h[0][0], h[1][0]))
                        vy1, vy2 = sorted((v[0][1], v[1][1]))
                        if hx1 + 2 < v[0][0] < hx2 - 2 and vy1 + 2 < h[0][1] < vy2 - 2:
                            cross[i] += 1
                            cross[j] += 1
    for i, c in cross.items():
        if c >= 3:
            e = edges[i]
            issues.append(specmod.Issue("warn", "FLOWGEO-03", f"连线「{e['f']}→{e['t']}（{e.get('label', '')}）」与其他线交叉 {c} 次，建议改路由",
                                    en=f"edge \"{e['f']}→{e['t']} ({e.get('label', '')})\" crosses other edges {c} time(s); consider re-routing"))
    for e in edges:
        for x, y in e["pts"]:
            if x < 0 or y < 0 or x > W or y > H:
                issues.append(specmod.Issue("error", "FLOWGEO-04", f"连线「{e['f']}→{e['t']}」超出画布，请调整 mid 或增加行列",
                                    en=f"edge \"{e['f']}→{e['t']}\" runs outside the canvas; adjust mid or add rows/columns"))
                break
    for e in edges:                                   # FLOWGEO-05：连线贴着节点边缘走（视觉上像压在节点边框上）
        hit = None
        for (p, q) in _segs(e["pts"]):
            for nid, b in block.items():
                if abs(p[0] - q[0]) < 0.5:
                    y1, y2 = sorted((p[1], q[1]))
                    if min(abs(p[0] - b[0]), abs(p[0] - b[2])) < 7 and min(y2, b[3]) - max(y1, b[1]) > 12:
                        hit = nid
                elif abs(p[1] - q[1]) < 0.5:
                    x1, x2 = sorted((p[0], q[0]))
                    if min(abs(p[1] - b[1]), abs(p[1] - b[3])) < 7 and min(x2, b[2]) - max(x1, b[0]) > 12:
                        hit = nid
                if hit:
                    break
            if hit:
                break
        if hit:
            issues.append(specmod.Issue("warn", "FLOWGEO-05",
                f"连线「{e['f']}→{e['t']}（{e.get('label', '')}）」贴着节点「{name(nodes[hit])}」的边缘走线；用 fo/to 把线移开一些，或换 fs/ts",
                en=f"edge \"{e['f']}→{e['t']} ({e.get('label', '')})\" runs along the edge of node \"{name(nodes[hit])}\"; move it with fo/to or change fs/ts"))
    return issues, block


def _label_check(label_rects, edges, block, fixed=()):
    issues = []
    byi = {e["_i"]: e for e in edges}
    items = list(label_rects.items())
    for i, r in items:
        e = byi[i]
        tag = f"标签「{e.get('label', '')}」（{e['f']}→{e['t']}）"
        tag_en = f"label \"{e.get('label', '')}\" ({e['f']}→{e['t']})"
        if r[3] - r[1] > 27:
            issues.append(specmod.Issue("warn", "FLOWGEO-14", f"{tag}折成了多行；缩短标签文字（建议 ≤ 14 字）",
                                         en=f"{tag_en} wraps onto several lines; shorten the label text (recommended ≤ 28 characters)"))
        for nid, b in block.items():
            if _rects_overlap(r, b, pad=-1):
                issues.append(specmod.Issue("error", "FLOWGEO-10", f"{tag}压住了节点 {nid}；用 lx/ly 平移，或加大 col_w",
                                             en=f"{tag_en} covers node {nid}; shift it with lx/ly or increase col_w"))
                break
        for o in fixed:
            if _rects_overlap(r, o, pad=0):
                issues.append(specmod.Issue("warn", "FLOWGEO-13", f"{tag}压住了泳道标题；用 lx/ly 平移",
                                             en=f"{tag_en} covers a lane title; shift it with lx/ly"))
                break
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            if _rects_overlap(items[a][1], items[b][1], pad=2):
                ea, eb = byi[items[a][0]], byi[items[b][0]]
                issues.append(specmod.Issue("error", "FLOWGEO-11",
                    f"标签「{ea.get('label', '')}」与「{eb.get('label', '')}」互相重叠；用 lx/ly 错开",
                    en=f"labels \"{ea.get('label', '')}\" and \"{eb.get('label', '')}\" overlap; separate them with lx/ly"))
    return issues



# ───────────────────────── 标签摆放（避让） ─────────────────────────
_MEASURED = {}


def _measure_labels(page, texts):
    """用真实浏览器测量标签尺寸（含换行），避免估算误差。"""
    todo = [t for t in dict.fromkeys(texts) if t not in _MEASURED]
    if not todo:
        return
    css = (f"body{{font-family:{FONT_STACK}}}.el{{position:absolute;left:0;top:0;border:1px solid;border-radius:9px;padding:2px 8px;"
           "font-size:12px;text-align:center;line-height:1.35;font-weight:500;width:max-content;max-width:210px}")
    items = "".join(f'<div class="el">{htmllib.escape(t)}</div>' for t in todo)
    page.set_content(f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{items}</body></html>")
    page.wait_for_timeout(150)
    sizes = page.evaluate("() => Array.from(document.querySelectorAll('.el')).map(e => {const r = e.getBoundingClientRect(); return [r.width, r.height]})")
    for t, (w, h) in zip(todo, sizes):
        _MEASURED[t] = (w, h)


def make_node_measurer(page):
    """返回函数：[(label, sub, 节点宽)] → {(label, sub, round(宽)): 文字区高度}。"""
    def run(specs):
        specs = list(dict.fromkeys((a, b, round(w)) for a, b, w in specs))
        css = (f"body{{font-family:{FONT_STACK};margin:0}}.nd{{position:absolute;left:0;top:0;text-align:center}}"
               ".lb{font-size:14px;font-weight:600;margin-top:7px;line-height:1.3}"
               ".sb2{font-size:12px;margin-top:1px;line-height:1.3}")
        items = "".join(f'<div class="nd" style="width:{w}px"><div class="lb">{htmllib.escape(a)}</div><div class="sb2">{htmllib.escape(b)}</div></div>' for a, b, w in specs)
        page.set_content(f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{items}</body></html>")
        page.wait_for_timeout(120)
        hs = page.evaluate("() => Array.from(document.querySelectorAll('.nd')).map(e => e.getBoundingClientRect().height)")
        return {k: h + 6 for k, h in zip(specs, hs)}
    return run


def _label_size(text):
    if text in _MEASURED:
        return _MEASURED[text]
    w = sum(13 if ord(c) > 255 else 7 for c in text) + 20
    lines = 1
    if w > 125:
        lines = -(-w // 117)
        w = 125
    return w, 22 + 16 * (lines - 1)


def _rect_of(cx, cy, w, h):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _place_labels(edges, block, W, H, fixed=()):
    """沿整条连线寻找不压节点、不压其他标签、不压别的连线的位置。返回仍有冲突的提醒。"""
    placed, issues = [], []
    for e in edges:
        if not e.get("label"):
            continue
        w, h = _label_size(e["label"])
        pts = e["pts"]
        segs = sorted(((abs(pts[j + 1][0] - pts[j][0]) + abs(pts[j + 1][1] - pts[j][1]), j) for j in range(len(pts) - 1)), reverse=True)
        best = None
        for length, j in segs:
            if length < 18:
                continue
            vertical = abs(pts[j + 1][0] - pts[j][0]) < 0.5
            for side in (0, 1, -1):
                for frac in (0.5, 0.35, 0.65, 0.22, 0.78, 0.12, 0.88):
                    cx = pts[j][0] + (pts[j + 1][0] - pts[j][0]) * frac + e.get("lx", 0)
                    cy = pts[j][1] + (pts[j + 1][1] - pts[j][1]) * frac + e.get("ly", 0)
                    if side:
                        if vertical:
                            cx += side * (w / 2 + 9)
                        else:
                            cy += side * (h / 2 + 8)
                    r = _rect_of(cx, cy, w, h)
                    pen = 0
                    if r[0] < 4 or r[1] < 4 or r[2] > W - 4 or r[3] > H - 4:
                        pen += 800
                    for b in block.values():
                        if _rects_overlap(r, b, pad=-2):
                            pen += 1000
                    for o in placed:
                        if _rects_overlap(r, o, pad=5):
                            pen += 500
                    for o in fixed:
                        if _rects_overlap(r, o, pad=4):
                            pen += 700
                    for other in edges:
                        if other is e and side:
                            continue
                        if other is e:
                            continue
                        for (p, q) in _segs(other["pts"]):
                            if _seg_hits_rect(p, q, r, eps=-2):
                                pen += 120
                    pen += (0 if (frac == 0.5 and length == segs[0][0]) else 6) + (3 if side else 0)
                    if best is None or pen < best[0]:
                        best = (pen, cx, cy, r)
                    if pen <= 9:
                        break
                if best and best[0] <= 9:
                    break
            if best and best[0] <= 9:
                break
        if best is None:
            mid = pts[len(pts) // 2]
            best = (2000, mid[0], mid[1], _rect_of(mid[0], mid[1], w, h))
        e["_lab"] = (best[1], best[2], w, h)
        placed.append(best[3])
        if best[0] >= 100:
            issues.append(specmod.Issue("warn", "FLOWGEO-12",
                f"标签「{e['label']}」（{e['f']}→{e['t']}）找不到不压线的位置；加大 col_w/行距，或改用 lx/ly 手动放置",
                en=f"no free spot for label \"{e['label']}\" ({e['f']}→{e['t']}); increase col_w / row gap, or place it manually with lx/ly"))
    return issues


# ───────────────────────── 对外接口 ─────────────────────────
def render_all(proj, scope=None, check_only=False, draft=False):
    """渲染（或仅检查）所有流程图。返回 (issues, 输出文件列表)。
    draft=True：页面地图草案——不要求原型和截图已存在，节点画成“待绘制”占位，输出到 .prdkit/draft/，不写入 images/。"""
    from playwright.sync_api import sync_playwright
    from . import browser as _browser

    i18n.set_lang(proj.lang)
    sissues, screens = specmod.validate_all(proj, draft=draft)
    errs = [i for i in sissues if i.level == "error"]
    for i in sissues:
        print(i)
    if errs:
        raise SystemExit(i18n.t("spec 存在错误，已中止。先修复上面的问题。", "The spec has errors; aborted. Fix the issues above first."))
    from . import fontcheck
    fontcheck.require()

    data = proj.load_screens()
    platform, base_vp = data.get("platform", ""), data["viewport"]
    files = [f for f in proj.flow_files()]
    if scope:
        files = [f for f in files if str(_load(f).get("scope")) == str(scope)]
        if not files:
            raise SystemExit(i18n.t(f"未找到 scope={scope} 的流程图定义", f"No flow definition found for scope={scope}"))
    proj.state.mkdir(parents=True, exist_ok=True)
    all_issues, outputs = [], []

    with _Server(proj.root) as srv, sync_playwright() as p:
        browser = _browser.launch(p)
        for fp in files:
            flow = _load(fp)
            missing = {n["id"] for n in flow["nodes"] if n.get("screen") and (draft or not (proj.images / screens[n["screen"]]["shot"]).exists())}
            mp = browser.new_page()
            _measure_labels(mp, [e["label"] for e in flow["edges"] if e.get("label")])
            mp.close()
            mp = browser.new_page()
            nodes, W, H, rowtop, rowh = _layout(flow, screens, base_vp, platform, measure_nodes=make_node_measurer(mp))
            mp.close()
            edges = _resolve_edges(flow, nodes)
            H, rowtop = _fit_canvas(nodes, edges, H, rowtop, flow)
            issues, block = _geometry_check(nodes, edges, W, H)
            lane_rects = [(34, rowtop[ln["row0"]] - 34 + 4, 34 + 15 * len(ln["label"]) + 12, rowtop[ln["row0"]] - 34 + 34) for ln in flow.get("lanes", [])]
            issues += _place_labels(edges, block, W, H, fixed=lane_rects)
            for nid in sorted([] if draft else missing):
                issues.append(specmod.Issue("error", "FLOWGEO-00", f"节点 {nid} 的截图 images/{screens[nodes[nid]['screen']]['shot']} 不存在，请先运行 shot",
                                            en=f"screenshot images/{screens[nodes[nid]['screen']]['shot']} of node {nid} does not exist; run shot first"))
            if draft:
                flow = dict(flow, title=flow["title"] + i18n.W("draft_suffix"))
            html = _build_html(proj, flow, nodes, edges, W, H, rowtop, rowh, platform, missing, draft=draft)
            scope_name = str(flow["scope"])
            html_path = proj.state / ("flow-" + scope_name.replace(".", "-") + ".html")
            html_path.write_text(html, encoding="utf-8")
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.6)
            page.goto(f"http://127.0.0.1:{srv.port}/{proj.state.name}/{html_path.name}", wait_until="load")
            page.wait_for_timeout(500)
            rects = page.evaluate("() => Array.from(document.querySelectorAll('.el')).map(e => {const r = e.getBoundingClientRect(); return [parseInt(e.dataset.i), r.left, r.top, r.right, r.bottom]})")
            issues += _label_check({r[0]: tuple(r[1:]) for r in rects}, edges, block, fixed=lane_rects)
            out_name = flow.get("out") or flow_out_name(scope_name)
            if not check_only:
                if draft:
                    (proj.state / "draft").mkdir(parents=True, exist_ok=True)
                    page.locator("#c").screenshot(path=str(proj.state / "draft" / out_name))
                else:
                    page.locator("#c").screenshot(path=str(proj.images / out_name))
                outputs.append(out_name)
            page.close()
            nerr = sum(1 for i in issues if i.level == "error")
            nwarn = len(issues) - nerr
            if i18n.cur() == "en":
                print(f"{'✅' if not nerr else '❌'} {fp.name:<14} nodes {len(nodes)}  edges {len(edges)}  canvas {W}x{H}  → {out_name if not check_only else '(check only)'}   errors {nerr}  warnings {nwarn}")
            else:
                print(f"{'✅' if not nerr else '❌'} {fp.name:<14} 节点 {len(nodes)}  连线 {len(edges)}  画布 {W}x{H}  → {out_name if not check_only else '(仅检查)'}   错误 {nerr}  提醒 {nwarn}")
            for i in issues:
                print("    ", i)
            all_issues += issues
        browser.close()
    return all_issues, outputs


def _load(fp):
    import json
    return json.loads(Path(fp).read_text(encoding="utf-8"))


# ───────────────────────── 页面清单表 ─────────────────────────
def page_table(proj, flow, screens):
    """由流转关系生成“本章页面清单”Markdown 表（单一事实源，避免图文不一致）。"""
    data = proj.load_screens()
    platform = data.get("platform", "")
    nodes = {n["id"]: n for n in flow["nodes"]}
    scope = str(flow["scope"])
    en = i18n.cur() == "en"
    rows = [i18n.W("table_head"), "|---|---|---|---|---|"]
    for n in flow["nodes"]:
        s = screens.get(n.get("screen")) if n.get("screen") else None
        if not s:
            continue
        kind = _native_label(platform) + i18n.W("native_popup_suffix") if s["kind"] == "native" else i18n.W("kind_label")[s["kind"]]
        if scope not in ("all", "3.0") and s["chapter"] != scope:
            kind += i18n.W("other_chapter")
        enters, exits = [], []
        for e in flow["edges"]:
            if e["t"] == n["id"]:
                src = nodes[e["f"]]
                enters.append(e.get("label", "") if src.get("kind") == "start" else f"{display_name(src, screens)}{': ' if en else '：'}{e.get('label', '')}")
            if e["f"] == n["id"]:
                exits.append(f"{e.get('label', '')}→{display_name(nodes[e['t']], screens)}")
        other = scope not in ("all", "3.0") and s["chapter"] != scope
        end = i18n.W("end_other").format(ch=s["chapter"]) if other else i18n.W("end_final")
        sep = "; " if en else "；"
        rows.append(f"| {s['name']} | {s.get('section') or s['chapter']} | {kind} | {sep.join(enters) or '—'} | {sep.join(exits) or end} |")
    return "\n".join(rows)


_VERB = {"popup": "弹出", "back": "回到"}


def transit_lines(proj, screens):
    """由流转关系生成每个页面的“**流转**：…”行草稿（单一事实源，PRD 直接引用，不手写）。

    口径与 lint 的 L-412/413 一致：合并所有流程图里与本页相邻的页面，既不多写也不漏写。
    返回 [(页面名, 小节号, 流转行文本)]，按 screens 登记顺序。
    """
    ins, outs = {}, {}
    seen = set()
    flows = sorted((_load(fp) for fp in proj.flow_files()), key=lambda f: (str(f["scope"]) in ("all", "3.0"), str(f["scope"])))
    for flow in flows:
        nodes = {n["id"]: n for n in flow["nodes"]}
        for e in flow["edges"]:
            a, b = nodes[e["f"]], nodes[e["t"]]
            lab = (e.get("label") or "").strip()
            if b.get("screen") and a.get("kind") == "start" and not a.get("screen"):
                key = ("start", b["screen"], lab)
                if key not in seen:
                    seen.add(key)
                    ins.setdefault(b["screen"], []).append(lab)
                continue
            if not (a.get("screen") and b.get("screen")) or a["screen"] == b["screen"]:
                continue
            key = (a["screen"], b["screen"], lab, e.get("kind", "normal"))
            if key in seen:
                continue
            seen.add(key)
            ins.setdefault(b["screen"], []).append(f"{screens[a['screen']]['name']}{': ' if i18n.cur() == 'en' else ' '}{lab}")
            verb = i18n.W("verbs").get(e.get("kind", "normal"), i18n.W("verb_default"))
            if i18n.cur() == "en":
                outs.setdefault(a["screen"], []).append(f"{lab}: {verb} \"{screens[b['screen']]['name']}\"")
            else:
                outs.setdefault(a["screen"], []).append(f"{lab}{verb}“{screens[b['screen']]['name']}”")
    rows = []
    for sid, s_ in screens.items():
        if sid not in ins and sid not in outs:
            continue
        sep = "; " if i18n.cur() == "en" else "；"
        head = sep.join(ins.get(sid, [])) or i18n.W("no_upstream")
        tail = sep.join(outs.get(sid, [])) or i18n.W("page_is_end")
        rows.append((s_["name"], s_.get("section") or "", f"{i18n.W('transit_prefix')}{head} → {i18n.W('this_page')} → {tail}"))
    return rows


def print_transit(proj, scope=None):
    issues, screens = specmod.validate_all(proj)
    if any(i.level == "error" for i in issues):
        for i in issues:
            print(i)
        raise SystemExit(i18n.t("spec 存在错误，无法生成流转行。", "The spec has errors; cannot generate the flow lines."))
    print(i18n.t("# “流转”行草稿（由 spec 生成；贴到各页面小节的首行，再按需润色动作措辞，但不要增删页面名）\n",
                 "# Draft of the \"Flow\" lines (generated from the spec; paste each one as the first line of its page section, polish the wording if needed, but do not add or remove page names)\n"))
    for name, section, line in transit_lines(proj, screens):
        print(f"##### {section} {i18n.W('sec_page')} — {name}".replace("  ", " "))
        print(line + "\n")


def print_tables(proj, scope=None, draft=False):
    issues, screens = specmod.validate_all(proj, draft=draft)
    if any(i.level == "error" for i in issues):
        for i in issues:
            print(i)
        raise SystemExit(i18n.t("spec 存在错误，无法生成清单。", "The spec has errors; cannot generate the page list."))
    for fp in proj.flow_files():
        flow = _load(fp)
        if scope and str(flow["scope"]) != str(scope):
            continue
        print(f"### {flow['title']}\n")
        print(page_table(proj, flow, screens))
        print()
