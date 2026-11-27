# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""style：视觉风格的列出 / 预览对比 / 应用。

设计取舍（刻意保持简单）：
  - 风格 = templates/styles/<名>.css，叠加在 templates/prototype-style.css 之后，只改表面（颜色/阴影/圆角/边框/背景）。
  - 颜色与风格是两件独立的事：任何风格都可以配任何主色。主色由业务调性、用户指定或已有设计决定，skill 不写死任何配色。
    不指定主色时仅用通用蓝色占位（并提示确认）；指定一个色值时自动派生浅/深/浅底变体。
  - 应用风格 = 把“基础样式 + 风格 + 主色覆盖”拼成项目自己的 prototype/assets/style.css。
    之后项目不再引用 skill 目录，skill 装在哪里都不影响已生成的原型。
  - 用户不满意内置风格时，直接改项目里的 style.css 即可，没有任何格式限制。
"""
from . import i18n
import html as htmllib
import json
import re
from pathlib import Path

from . import common

TEMPLATES = common.SKILL_DIR / "templates"
BASE_CSS = TEMPLATES / "prototype-style.css"
STYLES_DIR = TEMPLATES / "styles"
PREVIEW_DIR = STYLES_DIR / "preview"          # 随 skill 发布的固定预览图：app.png / pc.png / hash.txt

STYLES = {
    "flat": ("扁平", "纯色块、无阴影、小圆角，利落清爽", "工具、后台、信息密集型"),
    "glass": ("毛玻璃", "半透明加模糊、渐变背景、大圆角、内高光", "C 端、重氛围和品质感"),
    "soft": ("柔和圆润", "大圆角、浅色渐变底、柔和彩色阴影", "生活服务、社区、多数 C 端"),
    "dark": ("深色", "深底浅字、描边卡片、发光按钮", "科技、工具、夜间场景"),
}
STYLES_EN = {
    "flat": ("Flat", "Solid colour blocks, no shadows, small radius - crisp and clean", "Tools, admin, information-dense products"),
    "glass": ("Glass", "Translucency with blur, gradient background, large radius, inner highlight", "Consumer apps that stress atmosphere and quality"),
    "soft": ("Soft", "Large radius, light gradient base, soft coloured shadows", "Lifestyle services, community, most consumer apps"),
    "dark": ("Dark", "Dark base with light text, outlined cards, glowing buttons", "Tech, tools, night-time scenarios"),
}
DEFAULT_STYLE = "flat"


def style_info(k):
    """(名称, 说明, 适合) —— 按当前项目语言取。"""
    return (STYLES_EN if i18n.cur() == "en" else STYLES)[k]
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


# ───────────────────────── 主色派生 ─────────────────────────
def parse_hex(value):
    m = HEX_RE.match((value or "").strip())
    if not m:
        raise ValueError(i18n.t(f"主色需为 6 位十六进制色值，例如 #E5352B，收到：{value!r}", f"The accent must be a 6-digit hex colour such as #E5352B, got: {value!r}"))
    h = m.group(1)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(rgb, other, t):
    return tuple(round(a * (1 - t) + b * t) for a, b in zip(rgb, other))


def _hex(rgb):
    return "#%02X%02X%02X" % rgb


def derive_accent(value):
    rgb = parse_hex(value)
    return {
        "primary": _hex(rgb),
        "light": _hex(_mix(rgb, (255, 255, 255), 0.25)),
        "dark": _hex(_mix(rgb, (0, 0, 0), 0.25)),
        "bg": _hex(_mix(rgb, (255, 255, 255), 0.92)),
        "rgb": "%d, %d, %d" % rgb,
    }


def accent_css(value):
    a = derive_accent(value)
    return (f"/* 主色覆盖：{a['primary']}（由 prdkit style 自动派生） */\n:root {{\n"
            f"  --color-primary: {a['primary']};\n  --color-primary-light: {a['light']};\n"
            f"  --color-primary-dark: {a['dark']};\n  --color-primary-bg: {a['bg']};\n"
            f"  --color-primary-rgb: {a['rgb']};\n}}\n")


# ───────────────────────── 组装 ─────────────────────────
_HAN_RE = re.compile(r"[\u4e00-\u9fff]")
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def _strip_cjk_comments(css):
    """英文项目：去掉含汉字的 CSS 注释（模板里的设计说明）。只删注释，不影响任何样式规则。"""
    return _CSS_COMMENT_RE.sub(lambda m: "" if _HAN_RE.search(m.group(0)) else m.group(0), css)


def build_css(style, accent=None, lang=None):
    if style not in STYLES:
        raise ValueError(i18n.t(f"未知风格 {style!r}，可选：{', '.join(STYLES)}", f"Unknown style {style!r}; choose from: {', '.join(STYLES)}"))
    # 顺序：基础 → 主色 → 风格。风格放最后，这样深色风格能按自己的方式重定义派生色（如主色浅底）。
    en = (lang or i18n.cur()) == "en"
    parts = [BASE_CSS.read_text(encoding="utf-8")]
    if accent:
        parts.append("\n" + accent_css(accent))
    if en:
        parts.append(f"\n/* ===== Style: {style} ({STYLES_EN[style][0]}) ===== */\n")
    else:
        parts.append(f"\n/* ===== 风格：{style}（{STYLES[style][0]}） ===== */\n")
    parts.append((STYLES_DIR / f"{style}.css").read_text(encoding="utf-8"))
    css = "".join(parts)
    return _strip_cjk_comments(css) if en else css


def cmd_list():
    if i18n.cur() == "en":
        print("Built-in styles (default: %s):" % DEFAULT_STYLE)
        for k, (name, desc, fit) in STYLES_EN.items():
            print(f"  {k:<6} {name}  {desc}  Best for: {fit}")
        print("\nColour and style are independent: pass --accent #hex to apply to set the accent colour and --source to record why "
              "(without it a generic blue placeholder is used). If none of the built-in styles fits, edit prototype/assets/style.css in the project directly.")
        return 0
    print("内置风格（默认：%s）：" % DEFAULT_STYLE)
    for k, (name, desc, fit) in STYLES.items():
        print(f"  {k:<6} {name}　{desc}　适合：{fit}")
    print("\n颜色与风格相互独立：apply 时用 --accent #色值 指定主色、--source 记录依据（不指定则为通用蓝占位）。内置风格都不满意时，直接修改项目里的 prototype/assets/style.css 即可。")
    return 0


def apply(proj, style=None, accent=None, source=None):
    """应用风格与主色。style 省略时沿用 spec.style（项目重建样式、或沿用已确认的设计）。"""
    prev = {}
    i18n.set_lang(proj.lang)
    if proj.screens_path.exists():
        prev = proj.load_screens().get("style") or {}
    if not style:
        style = prev.get("name")
        if not style:
            raise ValueError(i18n.t("请指定风格名：" + "、".join(STYLES) + "（项目 spec 里还没有已确认的 style 可沿用）", "Specify a style name: " + ", ".join(STYLES) + " (the project spec has no confirmed style to reuse yet)"))
        accent = accent or prev.get("accent")
        source = source or prev.get("source")
    css = build_css(style, accent)
    out = proj.proto / "assets" / "style.css"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(css, encoding="utf-8")
    js_src, js_dst = TEMPLATES / "interaction.js", out.parent / "interaction.js"
    if js_src.exists() and not js_dst.exists():      # 已存在则不覆盖（用户或 LLM 可能改过）
        js = js_src.read_text(encoding="utf-8")
        if i18n.cur() == "en":                       # 英文项目：去掉含汉字的注释（该文件的汉字全部在注释里，运行行为不变）
            js = _strip_cjk_comments(js)
            js = "\n".join(l for l in js.split("\n") if not (_HAN_RE.search(l) and l.lstrip().startswith("//")))
        js_dst.write_text(js, encoding="utf-8")
    if proj.screens_path.exists():
        data = proj.load_screens()
        rec = {"name": style}
        if accent:
            rec["accent"] = derive_accent(accent)["primary"]
        if source:
            rec["source"] = source
        data["style"] = rec
        proj.screens_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if i18n.cur() == "en":
        note_en = f", accent {derive_accent(accent)['primary']}" if accent else ""
        print(f"✅ Style \"{STYLES_EN[style][0]}\" applied{note_en} -> {out.relative_to(proj.root)} ({len(css) // 1024 + 1} KB)")
        if proj.screens_path.exists():
            print("   Recorded in the style field of spec/screens.json" + (f" (basis: {source})." if source else "."))
        if not accent:
            print("   ⚠️ No accent colour given; a generic blue placeholder is used. Confirm one from the brand or an existing design (--accent #hex, state the basis with --source).")
        return 0
    note = f"，主色 {derive_accent(accent)['primary']}" if accent else ""
    print(f"✅ 已应用风格「{STYLES[style][0]}」{note} → {out.relative_to(proj.root)}（{len(css) // 1024 + 1} KB）")
    if proj.screens_path.exists():
        print("   已记录到 spec/screens.json 的 style 字段" + (f"（依据：{source}）。" if source else "。"))
    if not accent:
        print("   ⚠️ 未指定主色，当前用的是通用蓝色占位。请按业务调性或已有设计确认主色（--accent #色值，--source 写明依据）。")
    return 0


# ───────────────────────── 风格 CSS 的固定彩色扫描 ─────────────────────────
# 规则：风格里的彩色必须来自主色变量（var(--color-primary…) / rgba(var(--color-primary-rgb), a)），否则换主色后
# 会残留一块固定颜色（曾出现过毛玻璃背景右下角的固定粉红色块）。以下情况允许写字面量：
#   1. 中性色：白、黑、灰（RGB 三通道接近）
#   2. 状态语义色：橙、红、绿（提示/成功/错误等，不随品牌色变化）
#   3. :root 里对设计令牌（--xxx）的定义：风格自己的色板（如深色风格的底色与文字色）
#   4. 深色风格里的深色表面（亮度很低）
_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{8}\b|#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b|rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
_SEMANTIC = {(250, 140, 22), (255, 77, 79), (82, 196, 26), (123, 224, 79), (255, 180, 94), (255, 133, 135), (255, 77, 79)}


def _lum(rgb):
    r, g, b = [c / 255 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _rgb_of(m):
    t = m.group(0)
    if t.startswith("#"):
        h = t[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def scan_fixed_colors():
    """返回违规列表 [(风格, 行号, 色值, 该行内容)]；空列表表示全部合规。"""
    bad = []
    for name in STYLES:
        depth_root, in_root = 0, False
        for no, ln in enumerate((STYLES_DIR / f"{name}.css").read_text(encoding="utf-8").splitlines(), 1):
            code = re.sub(r"/\*.*?\*/", "", ln)
            if re.match(r"\s*:root\s*{", code):
                in_root, depth_root = True, 0
            if in_root:
                depth_root += code.count("{") - code.count("}")
                if depth_root <= 0:
                    in_root = False
                if re.match(r"\s*(--[\w-]+\s*:|:root)", code):
                    continue
            for m in _COLOR_RE.finditer(code):
                rgb = _rgb_of(m)
                if max(rgb) - min(rgb) <= 14 or rgb in _SEMANTIC:
                    continue
                if name == "dark" and _lum(rgb) < 0.2:
                    continue
                bad.append((name, no, m.group(0), ln.strip()[:70]))
    return bad


# ───────────────────────── 固定预览图 ─────────────────────────
# 预览图是随 skill 发布的固定文件（4 种风格 × APP/PC 各一张），运行时直接拿给用户挑选，不现场渲染。
# 样式文件一改，hash 就对不上；回归会检查，维护者运行 `prdkit.py style build-preview` 重新生成即可。
PREVIEW_TITLE = "示例产品"


def _sample_app(css):
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head>
<body><div class="phone-frame" style="padding-bottom:70px">
<div class="nav-bar"><span class="nav-bar__title">{PREVIEW_TITLE}</span><span class="nav-bar__action">筛选</span></div>
<div style="padding:12px 16px 2px"><input class="input" placeholder="搜索关键词"></div>
<div class="flex gap-sm px-lg py-md"><span class="tag tag--primary">全部</span><span class="tag tag--success">进行中</span><span class="tag tag--orange">待处理</span><span class="tag tag--red">已关闭</span></div>
<div class="card"><div class="card__title">示例卡片标题</div><p class="text-secondary text-sm">这里是一段说明文字，用来感受卡片的层次、圆角和留白。</p></div>
<div class="card"><div class="card__title">第二张卡片</div><p class="text-secondary text-sm">卡片之间的间距和阴影，是不同风格最直观的差异。</p></div>
<div style="padding:6px 16px"><div class="btn btn--primary">主要操作</div><div class="btn btn--secondary mt-md">次要操作</div></div>
<div style="position:fixed;left:50%;transform:translateX(-50%);bottom:50px;width:100%;max-width:375px"><div class="modal-content" style="padding:14px 16px 12px"><div class="card__title">弹窗示例</div><p class="text-secondary text-sm" style="margin-bottom:10px">底部弹窗的表面材质。</p><div class="btn btn--primary" style="height:40px">确认</div></div></div>
<div class="tab-bar"><div class="tab-bar__item active"><span>🏠</span>首页</div><div class="tab-bar__item"><span>📦</span>我的</div></div>
</div></body></html>"""


def _sample_pc(css):
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head>
<body><div class="desktop-frame">
<aside class="sidebar"><div class="sidebar__logo">{PREVIEW_TITLE}</div><div class="sidebar__group">运营管理</div>
<a class="sidebar__item active">订单管理</a><a class="sidebar__item">用户管理</a><a class="sidebar__item">内容审核</a>
<div class="sidebar__group">系统</div><a class="sidebar__item">角色权限</a></aside>
<div class="main"><header class="topbar"><div class="breadcrumb">运营管理 / <b>订单管理</b></div><div class="text-secondary text-sm">管理员</div></header>
<div class="page-body"><div class="page-title">订单管理</div>
<div class="stat-grid"><div class="stat"><div class="stat__label">今日订单</div><div class="stat__value">1,286</div><div class="stat__delta">较昨日 +12.4%</div></div>
<div class="stat"><div class="stat__label">待处理</div><div class="stat__value">37</div><div class="stat__delta down">较昨日 -3</div></div>
<div class="stat"><div class="stat__label">成交额</div><div class="stat__value">¥82.6万</div><div class="stat__delta">较昨日 +5.1%</div></div>
<div class="stat"><div class="stat__label">退款率</div><div class="stat__value">1.8%</div><div class="stat__delta down">较昨日 +0.2%</div></div></div>
<div class="panel"><div class="filter-bar"><input class="input" placeholder="订单号 / 手机号"><span class="select">全部状态 <span>▾</span></span><div class="btn btn--primary btn--sm">查询</div><div class="btn btn--secondary btn--sm">重置</div></div>
<table class="table"><thead><tr><th>订单号</th><th>状态</th><th class="num">金额</th><th>下单时间</th><th>操作</th></tr></thead><tbody>
<tr><td>20261028001</td><td><span class="tag tag--success">已完成</span></td><td class="num">¥128.00</td><td>2026-10-28 09:12</td><td><span class="btn btn--link">详情</span></td></tr>
<tr><td>20261028002</td><td><span class="tag tag--orange">待发货</span></td><td class="num">¥56.50</td><td>2026-10-28 09:40</td><td><span class="btn btn--link">详情</span></td></tr>
<tr><td>20261028003</td><td><span class="tag tag--red">已退款</span></td><td class="num">¥239.00</td><td>2026-10-28 10:05</td><td><span class="btn btn--link">详情</span></td></tr>
<tr><td>20261028004</td><td><span class="tag tag--primary">配送中</span></td><td class="num">¥76.00</td><td>2026-10-28 10:31</td><td><span class="btn btn--link">详情</span></td></tr></tbody></table>
<div class="pagination"><span>共 128 条</span><span class="pagination__item">‹</span><span class="pagination__item active">1</span><span class="pagination__item">2</span><span class="pagination__item">3</span><span class="pagination__item">›</span></div></div></div></div>
<div class="dialog" style="position:absolute;right:56px;bottom:44px;width:360px"><div class="dialog__title">确认退款</div><div class="dialog__body">退款后金额将原路退回，操作不可撤销。</div><div class="dialog__footer"><div class="btn btn--secondary btn--sm">取消</div><div class="btn btn--primary btn--sm">确认</div></div></div>
</div></body></html>"""


_SAMPLE_EN = [
    ("退款后金额将原路退回，操作不可撤销。", "The amount is returned to the original payment method; this cannot be undone."),
    ("这里是一段说明文字，用来感受卡片的层次、圆角和留白。", "A line of descriptive text to feel the layering, corner radius and white space of a card."),
    ("卡片之间的间距和阴影，是不同风格最直观的差异。", "Spacing and shadows between cards are the most visible difference between styles."),
    ("底部弹窗的表面材质。", "The surface material of a bottom sheet."),
    ("订单号 / 手机号", "Order no. / phone"),
    ("示例卡片标题", "Sample card title"), ("示例产品", "Sample Product"), ("搜索关键词", "Search keywords"),
    ("第二张卡片", "Second card"), ("主要操作", "Primary action"), ("次要操作", "Secondary action"),
    ("弹窗示例", "Popup example"), ("确认退款", "Confirm refund"), ("全部状态", "All statuses"),
    ("运营管理", "Operations"), ("订单管理", "Orders"), ("用户管理", "Users"), ("内容审核", "Moderation"),
    ("角色权限", "Roles"), ("今日订单", "Orders today"), ("较昨日", "vs yesterday"), ("¥82.6万", "¥826K"),
    ("退款率", "Refund rate"), ("成交额", "Revenue"), ("下单时间", "Placed at"), ("订单号", "Order no."),
    ("进行中", "In progress"), ("待处理", "Pending"), ("已关闭", "Closed"), ("已完成", "Completed"),
    ("待发货", "To ship"), ("已退款", "Refunded"), ("配送中", "Shipping"), ("管理员", "Admin"),
    ("共 128 条", "128 items"), ("筛选", "Filter"), ("全部", "All"), ("首页", "Home"), ("我的", "Me"),
    ("系统", "System"), ("状态", "Status"), ("金额", "Amount"), ("操作", "Actions"), ("详情", "Details"),
    ("查询", "Search"), ("重置", "Reset"), ("确认", "Confirm"), ("取消", "Cancel"),
]


def _localize_sample(html):
    """英文样例页：只翻译 <style> 之外的文字（长词在前，避免被短词吃掉）。"""
    head, rest = html.split("</style>", 1)
    for zh, en in _SAMPLE_EN:
        rest = rest.replace(zh, en)
    return head.replace('lang="zh-CN"', 'lang="en"') + "</style>" + rest


def sample_app(css, lang=None):
    html = _sample_app(css)
    return _localize_sample(html) if (lang or i18n.cur()) == "en" else html


def sample_pc(css, lang=None):
    html = _sample_pc(css)
    return _localize_sample(html) if (lang or i18n.cur()) == "en" else html


def preview_dir(lang=None):
    return PREVIEW_DIR / "en" if (lang or i18n.cur()) == "en" else PREVIEW_DIR


def preview_hash(lang="zh"):
    """样式与示例页内容的指纹；任何一处变化，固定预览图就算过期。"""
    import hashlib
    h = hashlib.sha256()
    for k in STYLES:
        css = build_css(k, lang=lang)
        h.update(sample_app(css, lang).encode("utf-8"))
        h.update(sample_pc(css, lang).encode("utf-8"))
    if lang == "en":
        h.update(repr(STYLES_EN).encode("utf-8"))
    return h.hexdigest()[:16]


def preview_status(lang=None):
    """返回 (是否齐全且最新, 说明)。"""
    lang = lang or i18n.cur()
    d = preview_dir(lang)
    need = [d / "app.png", d / "pc.png", d / "hash.txt"]
    miss = [p.name for p in need if not p.exists()]
    if miss:
        return False, i18n.t("缺少固定预览图文件：" + "、".join(miss), "Fixed preview image files are missing: " + ", ".join(miss))
    if (d / "hash.txt").read_text(encoding="utf-8").strip() != preview_hash(lang):
        return False, i18n.t("固定预览图与当前样式不一致（样式改过但没重新生成）", "The fixed preview images no longer match the styles (styles changed but were not regenerated)")
    return True, i18n.t("固定预览图与当前样式一致", "The fixed preview images match the current styles")


def _compare_html(kind, note, lang="zh"):
    en = lang == "en"
    info = STYLES_EN if en else STYLES
    best = "Best for: " if en else "适合："
    cap = lambda i, k: (f'<div class="cap"><b>{i}. {info[k][0]}</b><span>{htmllib.escape(info[k][1])}</span>'
                        f'<em>{best}{htmllib.escape(info[k][2])}</em></div>')
    if kind == "app":
        cols = "".join(f'<div class="col">{cap(i, k)}<iframe src="{k}-app.html" width="390" height="780"></iframe></div>'
                       for i, k in enumerate(STYLES, 1))
        width, h1 = len(STYLES) * 420 + 20, ("Choose a visual style (APP / mini program / H5)" if en else "请选择视觉风格（APP / 小程序 / H5）")
        row_css = ".row{display:flex;gap:20px;justify-content:center;padding:0 10px 28px}.col{width:400px}"
        frame = "iframe{width:390px;height:780px;border:1px solid #d9dce1;border-radius:26px;box-shadow:0 8px 28px rgba(0,0,0,.12);background:#fff;display:block;margin:0 auto}"
    else:
        cols = "".join(f'<div class="col">{cap(i, k)}<div class="wrap"><iframe src="{k}-pc.html"></iframe></div></div>'
                       for i, k in enumerate(STYLES, 1))
        width, h1 = 1500, ("Choose a visual style (PC / admin)" if en else "请选择视觉风格（PC / 后台）")
        row_css = ".row{display:grid;grid-template-columns:720px 720px;gap:28px 24px;justify-content:center;padding:0 10px 28px}.col{width:720px}"
        frame = (".wrap{width:720px;height:450px;border:1px solid #d9dce1;border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.12);overflow:hidden;background:#fff}"
                 "iframe{width:1440px;height:900px;border:0;transform:scale(.5);transform-origin:0 0;display:block}")
    html_lang = "en" if en else "zh-CN"
    page_title = "Style picker" if en else "风格选择"
    page = f"""<!DOCTYPE html><html lang="{html_lang}"><head><meta charset="utf-8"><title>{page_title}</title><style>
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;background:#fff;color:#1f1f1f;width:{width}px}}
h1{{font-size:26px;text-align:center;margin:0;padding:24px 0 4px}}.sub{{text-align:center;color:#6b7280;font-size:14px;padding-bottom:18px}}
{row_css}
.cap{{text-align:center;margin-bottom:12px}}.cap b{{font-size:18px}}.cap span,.cap em{{display:block;font-size:12.5px;color:#6b7280;margin-top:3px;font-style:normal}}
{frame}
</style></head><body><h1>{h1}</h1><div class="sub">{htmllib.escape(note)}</div><div class="row">{cols}</div></body></html>"""
    return page, width


def build_preview(lang="zh"):
    """维护者命令：重新生成固定预览图（改过 templates/ 下的样式后必须运行）。"""
    import tempfile
    bad = scan_fixed_colors()
    if bad:
        print(i18n.t("❌ 风格 CSS 里有不随主色变化的固定彩色，已拒绝生成预览图（请改用主色变量派生）：", "❌ The style CSS has fixed colours that do not follow the accent; preview generation refused (derive them from the accent variables):"))
        for st, no, col, text in bad[:10]:
            print(f"   {st}.css:{no}  {col}   {text}")
        return 1
    from playwright.sync_api import sync_playwright
    from . import browser as _browser
    out_dir = preview_dir(lang)
    out_dir.mkdir(parents=True, exist_ok=True)
    note = "同一份内容套用不同风格，内容与布局完全相同，只有视觉表面不同（图中的蓝色只是示例配色；你的主色会按业务调性或已有设计另行确定）"
    if lang == "en":
        note = ("The same content under different styles: content and layout are identical, only the visual surface differs "
                "(the blue is just a sample colour; your accent colour is decided later from the business tone or an existing design)")
    with tempfile.TemporaryDirectory(prefix="prdkit-preview-") as td, sync_playwright() as p:
        td = Path(td)
        for k in STYLES:
            css = build_css(k, lang=lang)
            (td / f"{k}-app.html").write_text(sample_app(css, lang), encoding="utf-8")
            (td / f"{k}-pc.html").write_text(sample_pc(css, lang), encoding="utf-8")
        b = _browser.launch(p)
        for kind in ("app", "pc"):
            page, width = _compare_html(kind, note, lang)
            f = td / f"compare-{kind}.html"
            f.write_text(page, encoding="utf-8")
            pg = b.new_page(viewport={"width": width, "height": 1000}, device_scale_factor=1.5)
            pg.goto(f"file://{f.resolve()}")
            pg.wait_for_timeout(700)
            pg.screenshot(path=str(out_dir / f"{kind}.png"), full_page=True)
            pg.close()
        b.close()
    (out_dir / "hash.txt").write_text(preview_hash(lang) + "\n", encoding="utf-8")
    print(i18n.t(f"✅ 已重新生成固定预览图：{out_dir}（app.png / pc.png / hash.txt）",
                 f"✅ Fixed preview images regenerated: {out_dir} (app.png / pc.png / hash.txt)"))
    return 0


def preview_custom(out_dir, style, accent=None, platform=None):
    """现场渲染“指定风格 + 指定主色”的 APP / PC 各一张（只渲染 1 个风格，几秒完成），用于确认真实配色。"""
    from playwright.sync_api import sync_playwright
    from . import browser as _browser
    if style not in STYLES:
        raise ValueError(i18n.t(f"未知风格 {style!r}，可选：{', '.join(STYLES)}", f"Unknown style {style!r}; choose from: {', '.join(STYLES)}"))
    kinds = ["pc"] if platform in ("web", "admin") else ["app"] if platform in ("miniprogram", "h5", "app") else ["app", "pc"]
    css = build_css(style, accent)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shown = []
    with sync_playwright() as p:
        b = _browser.launch(p)
        for k in kinds:
            html = (sample_app if k == "app" else sample_pc)(css)
            tmp = out / f".custom-{k}.html"
            tmp.write_text(html, encoding="utf-8")
            vp = {"width": 390, "height": 844} if k == "app" else {"width": 1440, "height": 900}
            pg = b.new_page(viewport=vp, device_scale_factor=2 if k == "app" else 1)
            pg.goto(f"file://{tmp.resolve()}")
            pg.wait_for_timeout(500)
            png = out / f"style-custom-{k}.png"
            pg.screenshot(path=str(png), full_page=(k == "pc"))
            pg.close()
            tmp.unlink()
            shown.append(png)
        b.close()
    if i18n.cur() == "en":
        acc_en = f", accent {derive_accent(accent)['primary']}" if accent else ", generic blue"
        print(f"✅ Preview of \"{STYLES_EN[style][0]}\"{acc_en} (sample content, for confirming the colours):")
        for s_ in shown:
            print(f"   {s_}")
        print("   After confirming run: prdkit.py style apply " + style + (f" --accent {derive_accent(accent)['primary']}" if accent else "") + " --source \"basis\"")
        return 0
    acc = f"，主色 {derive_accent(accent)['primary']}" if accent else "，通用蓝色"
    print(f"✅ 「{STYLES[style][0]}」{acc} 的效果图（示例内容，用于确认配色）：")
    for s_ in shown:
        print(f"   {s_}")
    print("   确认后运行：prdkit.py style apply " + style + (f" --accent {derive_accent(accent)['primary']}" if accent else "") + " --source \"依据说明\"")
    return 0


def preview(out_dir, platform=None):
    """把 skill 自带的固定预览图复制到 out_dir 并给出路径；不现场渲染，几乎瞬时。"""
    import shutil
    ok, msg = preview_status()
    if not ok:
        print(i18n.t(f"⚠️  {msg}。预览图仍可参考，但可能和实际样式有细微差别；请联系 skill 维护者运行：prdkit.py style build-preview",
                     f"⚠️  {msg}. The images are still usable but may differ slightly from the real styles; ask the skill maintainer to run: prdkit.py style build-preview --lang {i18n.cur()}"))
    kinds = ["pc"] if platform in ("web", "admin") else ["app"] if platform in ("miniprogram", "h5", "app") else ["app", "pc"]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shown = []
    for k in kinds:
        src = preview_dir() / f"{k}.png"
        if src.exists():
            shutil.copyfile(src, out / f"style-compare-{k}.png")
            shown.append(out / f"style-compare-{k}.png")
    if not shown:
        print(i18n.t("❌ 找不到固定预览图，无法预览。", "❌ Fixed preview images not found; cannot preview."))
        return 1
    print(i18n.t("✅ 风格对比图（请看图选择）：", "✅ Style comparison images (pick one by looking at them):"))
    for s in shown:
        print(f"   {s}")
    print(i18n.t("   选定风格后，再按业务调性或已有设计确定主色：prdkit.py style preview <风格名> --accent #色值 可看到真实配色效果。",
                 "   After choosing a style, decide the accent colour from the business tone or an existing design: prdkit.py style preview <style> --accent #hex shows the real colours."))
    return 0
