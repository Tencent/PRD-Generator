# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""index：由 spec/screens.json 生成 prototype/index.html（原型入口导航页）。

- 按章节分组，每个 HTML 文件一张卡片（同一文件的多个状态/弹窗挂在卡片下，避免重复链接）
- 样式取项目自己的 assets/style.css（没有就用页内最小样式），不依赖 skill 目录
- 纯派生物：页面增删后重新运行即可，不要手改
"""
import html as htmllib
import re
from collections import OrderedDict

from . import i18n

KIND_LABEL = {"page": "页面", "state": "状态", "popup": "弹窗", "native": "原生"}
KIND_LABEL_EN = {"page": "Page", "state": "State", "popup": "Popup", "native": "Native"}


def _file(url):
    return re.split(r"[?#]", url, 1)[0]


def build(proj):
    i18n.set_lang(proj.lang)
    en = i18n.cur() == "en"
    popup_tip = "Opens after a tap on the page" if en else "进入页面后点击触发"
    colon = ": " if en else "："
    kind_label = KIND_LABEL_EN if en else KIND_LABEL
    data = proj.load_screens()
    chapters = OrderedDict((c["id"], c["title"]) for c in data.get("chapters", []))
    by_chapter = OrderedDict((cid, OrderedDict()) for cid in chapters)
    for s in data["screens"]:
        by_chapter.setdefault(s["chapter"], OrderedDict()).setdefault(_file(s["url"]), []).append(s)

    esc = htmllib.escape
    has_css = (proj.proto / "assets" / "style.css").exists()
    body = []
    n_files = 0
    for cid, files in by_chapter.items():
        if not files:
            continue
        cards = []
        for f, items in files.items():
            n_files += 1
            main = next((x for x in items if x["kind"] == "page"), items[0])
            chips = []
            for x in items:
                if x is main:
                    continue
                label = f'{kind_label.get(x["kind"], x["kind"])}{colon}{esc(x["name"])}'
                if x["kind"] == "popup":
                    chips.append(f'<span class="tag tag--primary" title="{popup_tip}">{label}</span>')
                else:
                    chips.append(f'<a class="tag tag--primary" href="{esc(x["url"])}">{label}</a>')
            sec = f'<span class="idx-sec">{esc(main["section"])}</span>' if main.get("section") else ""
            cards.append(
                f'<div class="card idx-card"><a class="idx-main" href="{esc(main["url"])}">{esc(main["name"])}</a>{sec}'
                f'<div class="idx-file">{esc(f)}</div>'
                + (f'<div class="idx-chips">{"".join(chips)}</div>' if chips else "") + "</div>")
        body.append(f'<h2 class="idx-h">{esc(cid)} {esc(chapters.get(cid, ""))}</h2><div class="idx-grid">{"".join(cards)}</div>')

    css_link = '<link rel="stylesheet" href="assets/style.css">' if has_css else ""
    title_suffix = "Prototype index" if en else "原型导航"
    html_lang = "en" if en else "zh-CN"
    sub = (f"{n_files} page files · generated from spec/screens.json (run prdkit.py index to refresh after adding or removing pages)" if en
           else f"共 {n_files} 个页面文件 · 由 spec/screens.json 自动生成（页面增删后运行 prdkit.py index 刷新）")
    title = f'{data.get("name", proj.name)} {data.get("version", "")} {title_suffix}'.strip()
    page = f"""<!DOCTYPE html>
<html lang="{html_lang}"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>{css_link}
<style>
body{{max-width:960px;margin:0 auto;padding:28px 20px 60px;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
h1{{font-size:24px;margin:0 0 4px}}.idx-sub{{color:#6b7280;font-size:13px;margin-bottom:8px}}
.idx-h{{font-size:17px;margin:26px 0 12px}}.idx-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}}
.idx-card{{margin:0!important;padding:14px 16px}}.idx-main{{font-size:16px;font-weight:600;color:var(--color-primary,#1677ff);text-decoration:none}}
.idx-sec{{margin-left:8px;font-size:12px;color:#9ca3af}}.idx-file{{font-size:12px;color:#9ca3af;margin:4px 0 8px;font-family:ui-monospace,Menlo,monospace}}
.idx-chips{{display:flex;flex-wrap:wrap;gap:6px}}.idx-chips .tag{{text-decoration:none}}
</style></head>
<body><h1>{esc(title)}</h1>
<div class="idx-sub">{sub}</div>
{"".join(body)}
</body></html>
"""
    out = proj.proto / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out, n_files
