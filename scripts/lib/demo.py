# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""demo：管理原型 Demo 的交付状态（pending / online / local），以及打包。

三种状态（写在 spec.demo.mode）：
  pending  尚未处理（缺省）：PRD 里不写原型地址，附录 B 只写“发布后补充”
  online   原型已托管到某个 https 地址（任意静态托管：GitHub Pages、对象存储、自建站点…）
  local    用户明确不托管：PRD 里写本地路径，随交付包附 prototype.zip

命令：
  prdkit demo pack [--out 文件]     只打包 prototype（排除 screenshots/、.prdkit/ 等）
  prdkit demo local                 记录为本地兜底并打包
  prdkit demo online <https 地址>    用户自己把 prototype/ 托管后，记录在线地址
  prdkit demo reset                 迭代出新版本目录后，回到“待发布”
  prdkit demo status                查看当前状态

托管本身不在核心里：核心只负责打包与记录。需要一键发布时，使用 publishers/ 下的发布器
（见 references/publish.md）。
"""
import re
import time
import zipfile
from pathlib import Path

from . import i18n
from .common import dump_json
from . import spec as specmod

EXCLUDE_DIRS = {"screenshots", ".prdkit", "__pycache__", ".git", "node_modules"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
MAX_ZIP = 100 * 1024 * 1024
URL_RE = re.compile(r"^https://[A-Za-z0-9]([A-Za-z0-9\-.]*[A-Za-z0-9])?(:\d+)?(/[^\s]*)?$")


class DemoError(Exception):
    pass


# ───────────────────────── 命名 ─────────────────────────
def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")


def deliver_name(proj, data=None):
    """交付物命名前缀：<项目名>-<版本>，例如 neighbor-lend-v1-0。"""
    data = data or proj.load_screens()
    dm = data.get("demo") or {}
    slug = _slug(dm.get("slug")) or _slug(proj.root.name)
    if not slug or re.fullmatch(r"v?\d+(-\d+)*", slug):      # 目录名只是版本号，往上找一级
        slug = _slug(proj.root.parent.name) or slug
    slug = re.sub(r"-v\d+(-\d+)*$", "", slug) or slug        # 迭代目录（xxx-v2）去掉自带的版本后缀，避免和 spec.version 重复
    ver = _slug(data.get("version") or "")
    if not slug:
        raise DemoError(i18n.t("无法从项目目录名推出交付物名称，请检查项目目录名", "Cannot derive a deliverable name from the project directory name; check the directory name"))
    return slug if (not ver or slug.endswith("-" + ver)) else f"{slug}-{ver}"


# ───────────────────────── 打包 ─────────────────────────
def collect(proj):
    out = []
    for p in sorted(proj.proto.rglob("*")):
        if not p.is_file() or p.name in EXCLUDE_FILES:
            continue
        rel = p.relative_to(proj.proto)
        if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
            continue
        out.append((p, rel.as_posix()))
    return out


def build_zip(proj, out):
    if not (proj.proto / "index.html").exists():
        raise DemoError(i18n.t("prototype/index.html 不存在：先运行 prdkit.py index 生成导航页", "prototype/index.html does not exist: run prdkit.py index to generate the index page first"))
    if not (proj.proto / "assets" / "style.css").exists():
        raise DemoError(i18n.t("prototype/assets/style.css 不存在：先运行 prdkit.py style apply 应用风格，否则打包出的页面没有样式", "prototype/assets/style.css does not exist: run prdkit.py style apply first, otherwise the packed pages have no styling"))
    files = collect(proj)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, rel in files:
            zf.write(p, rel)
    size = out.stat().st_size
    if size > MAX_ZIP:
        raise DemoError(i18n.t(f"zip 大小 {size / 1048576:.1f}MB，超过 100MB；请先精简原型里的大文件", f"The zip is {size / 1048576:.1f}MB, over 100MB; slim down large files in the prototype first"))
    return out, len(files), size


def precheck(proj):
    """托管前的轻量自检：spec 无错误，页面不引用外部资源（托管后可能打不开）。"""
    from .check import EXT_RE
    issues, _ = specmod.validate_all(proj)
    errs = [i for i in issues if i.level == "error"]
    if errs:
        raise DemoError(i18n.t("spec 校验有错误，先修复：\n  ", "The spec has errors; fix them first:\n  ") + "\n  ".join(str(i) for i in errs[:6]))
    bad = []
    for p, rel in collect(proj):
        if rel.endswith(".html") and EXT_RE.search(p.read_text(encoding="utf-8", errors="ignore")):
            bad.append(rel)
    if bad:
        raise DemoError(i18n.t("这些页面引用了外部资源（CDN/外链图片或字体），托管后可能打不开：" + "、".join(bad[:6]), "These pages reference external resources (CDN / external images or fonts) that may not open once hosted: " + ", ".join(bad[:6])))


# ───────────────────────── 记录 ─────────────────────────
def set_demo(proj, demo):
    data = proj.load_screens()
    data["demo"] = demo
    dump_json(proj.screens_path, data)


def record_online(proj, url, publisher=None, extra=None):
    """记录在线 Demo 地址（发布器与 `demo online` 共用）。"""
    url = str(url or "").strip().rstrip("/")
    if not URL_RE.match(url):
        raise DemoError(i18n.t(f"在线 Demo 地址需为 https:// 开头的网址，当前：{url!r}", f"The online demo address must be a URL starting with https://, got: {url!r}"))
    demo = {"mode": "online", "url": url, "published_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if publisher:
        demo["publisher"] = publisher
    if extra:
        demo.update(extra)
    set_demo(proj, demo)
    return demo


# ───────────────────────── 子命令 ─────────────────────────
def cmd_pack(proj, out=None):
    try:
        out = out or (proj.root / f"{deliver_name(proj)}-prototype.zip")
        path, n, size = build_zip(proj, out)
    except DemoError as e:
        print(f"❌ {e}")
        return 1
    print(i18n.t(f"✅ 已打包：{path}（{n} 个文件，{size / 1024:.0f}KB；已排除 screenshots/、.prdkit/）", f"✅ Packed: {path} ({n} files, {size / 1024:.0f}KB; screenshots/ and .prdkit/ excluded)"))
    return 0


def cmd_local(proj):
    """用户明确选择不托管在线 Demo：记录 demo.mode=local，并打 prototype.zip 随交付包提供。"""
    if cmd_pack(proj):
        return 1
    old = (proj.load_screens().get("demo") or {}).get("mode")
    set_demo(proj, {"mode": "local"})
    if old == "online":
        print(i18n.t("ℹ️  此前是 online 模式，已切换为 local；已托管的在线站点不会被删除。", "ℹ️  It was in online mode before and is now switched to local; an already hosted online site is not deleted."))
    print(i18n.t("✅ 已设为本地兜底：PRD 里写本地路径、附录 B 说明未提供在线 Demo。下一步：prdkit.py links --apply", "✅ Set to local fallback: the PRD carries local paths and Appendix B says no online demo is provided. Next: prdkit.py links --apply"))
    return 0


def cmd_online(proj, url):
    try:
        precheck(proj)
        demo = record_online(proj, url)
    except DemoError as e:
        print(f"❌ {e}")
        return 1
    print(i18n.t(f"✅ 已记录在线 Demo：{demo['url']}。下一步：prdkit.py links --apply", f"✅ Online demo recorded: {demo['url']}. Next: prdkit.py links --apply"))
    return 0


def cmd_reset(proj):
    """迭代出新版本目录后，清掉从旧版本带过来的 Demo 记录：回到“待发布”。"""
    old = (proj.load_screens().get("demo") or {}).get("mode")
    set_demo(proj, {"mode": "pending"})
    print(i18n.t(f"✅ Demo 已重置为“待发布”（此前：{old or '未设置'}）。旧站点不会被删除；"
          f"下一步：prdkit.py links --apply，PRD 里的原型地址会被清掉，托管新版本后再统一回填。", f"✅ Demo reset to \"pending\" (was: {old or 'not set'}). The old site is not deleted; "
          f"next: prdkit.py links --apply, which clears the prototype addresses in the PRD; back-fill them after hosting the new version."))
    return 0


def cmd_status(proj):
    d = proj.load_screens().get("demo") or {}
    mode = d.get("mode") or "pending"
    if mode == "pending":
        print(i18n.t("Demo 状态：待发布（PRD 里暂不写原型地址；托管后用 links --apply 统一回填）", "Demo status: pending (the PRD carries no prototype address yet; back-fill them with links --apply after hosting)"))
        return 0
    print(i18n.t(f"Demo 模式：{mode}", f"Demo mode: {mode}"))
    if mode == "online":
        extra = i18n.t(f"    发布器：{d['publisher']}", f"    publisher: {d['publisher']}") if d.get("publisher") else ""
        print(i18n.t(f"站点：{d.get('url')}    记录时间：{d.get('published_at')}{extra}", f"site: {d.get('url')}    recorded at: {d.get('published_at')}{extra}"))
        return 0
    zp = proj.root / f"{deliver_name(proj)}-prototype.zip"
    print(i18n.t(f"本地兜底包：{'已生成 ' + zp.name if zp.exists() else '尚未生成（prdkit.py demo local）'}", f"Local fallback package: {'generated ' + zp.name if zp.exists() else 'not generated yet (prdkit.py demo local)'}"))
    return 0
