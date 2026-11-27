# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""doctor：环境体检。只报告，不擅自安装；每个缺项给出一条可直接执行的修复指引。

分级：
  必需  Python≥3.8、Playwright + Chromium（截图与流程图渲染都依赖）
  可选  发布器的凭证只检测“是否已配置”，绝不打印其内容或长度（发布器只用标准库，没有额外的第三方依赖）

"""
import os
import platform
import sys
import tempfile
from pathlib import Path

from .common import SKILL_DIR, find_workspace, get_secret, count_secret_definitions
from . import i18n

OK, WARN, BAD = "✅", "⚠️ ", "❌"


def _check_python():
    v = sys.version_info
    if v >= (3, 8):
        return OK, f"Python {v.major}.{v.minor}.{v.micro}", None, True
    return BAD, f"Python {v.major}.{v.minor}", i18n.t("需要 Python 3.8 及以上", "Python 3.8 or newer is required"), True


def _check_playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:
        return (BAD, i18n.t("playwright 未安装（截图与流程图渲染需要）", "playwright is not installed (needed for screenshots and flow-diagram rendering)"),
                i18n.t("运行 prdkit setup（用户同意后加 --yes），或手动 python3 -m pip install playwright",
                       "Run prdkit setup (add --yes after the user agrees), or install manually: python3 -m pip install playwright"), True)
    from . import browser
    ok, label, err = browser.probe()
    if ok:
        return OK, i18n.t(f"页面截图组件可用（使用 {label}）", f"Screenshot component available (using {label})"), None, True
    return (BAD, i18n.t(f"没有可用的浏览器：{err}", f"No usable browser: {err}"),
            i18n.t("有 Chrome 或 Edge 就会自动使用；都没有时运行 prdkit setup（用户同意后加 --yes）下载内置浏览器",
                   "Chrome or Edge is used automatically if present; otherwise run prdkit setup (add --yes after the user agrees) to download the bundled browser"), True)


def _check_cjk_font():
    try:
        from . import fontcheck
        ok, msg = fontcheck.has_cjk_font()
    except Exception as e:
        return WARN, i18n.t(f"中文字体检测跳过（{type(e).__name__}）", f"CJK font check skipped ({type(e).__name__})"), None, True
    if ok:
        if i18n.cur() == "en":
            return OK, "CJK font: not required for an English project", None, True
        return OK, "Chromium 中文渲染正常", None, True
    return (BAD, i18n.t(f"{msg}（截图与流程图会出现方块乱码）", f"{msg} (screenshots and flow diagrams will show boxes instead of text)"),
            i18n.t(fontcheck.INSTALL_HINT, fontcheck.INSTALL_HINT_EN), True)


def _check_env(var, label, hint, online=None):
    val, source = get_secret(var)
    if not val:
        return WARN, i18n.t(f"{label} 未配置", f"{label} is not configured"), hint, False
    dup = count_secret_definitions(var)
    dup_note = ""
    if sum(dup.values()) > 1:
        where = i18n.t("、", ", ").join(f"{k}×{v}" for k, v in dup.items())
        dup_note = i18n.t(f"；注意：重复 export（{where}），以最后一行为准，建议清理旧行",
                          f"; note: duplicate export lines ({where}); the last one wins, consider cleaning up the old ones")
    src_note = "" if source == "环境变量" else i18n.t(f"（读取自 {source}，当前进程未加载）", f" (read from {source}, not loaded in this process)")
    if online:
        ok, msg = online(val)
        return (OK if ok else BAD), i18n.t(f"{label} 已配置{src_note}，{msg}{dup_note}", f"{label} is configured{src_note}, {msg}{dup_note}"), (None if ok else hint), False
    return OK, i18n.t(f"{label} 已配置{src_note}{dup_note}", f"{label} is configured{src_note}{dup_note}"), None, False


def _check_writable(path):
    try:
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return True
    except Exception:
        return False


def run(cwd=None):
    ws = find_workspace(cwd)
    rows = []
    rows.append(_check_python())
    rows.append(_check_playwright())
    if rows[-1][0] == OK:
        rows.append(_check_cjk_font())
    gh_var = "GITHUB_TOKEN" if (get_secret("GITHUB_TOKEN")[0] or not get_secret("GH_TOKEN")[0]) else "GH_TOKEN"
    rows.append(_check_env(
        gh_var, i18n.t(f"{gh_var}（GitHub Pages 发布器，可选）", f"{gh_var} (GitHub Pages publisher, optional)"),
        i18n.t("仅影响“一键发布到 GitHub Pages”，不影响 PRD、原型与打包交付；配置步骤见 references/publish.md §3",
               "Only affects \"publish to GitHub Pages in one step\"; PRD, prototype and packaged delivery are unaffected. Setup steps: references/publish.md §3"),
    ))
    rows.append((OK if _check_writable(ws) else WARN, i18n.t(f"工作区可写：{ws}", f"Workspace writable: {ws}"), None, False))

    en = i18n.cur() == "en"
    print(f"prdkit environment check    platform: {platform.system()}    skill: {SKILL_DIR}" if en else f"prdkit 环境体检    平台：{platform.system()}    skill：{SKILL_DIR}")
    print("-" * 64)
    blocked = False
    for icon, msg, fix, required in rows:
        tag = ("[required]" if required else "[optional]") if en else ("[必需]" if required else "[可选]")
        print(f"{icon} {tag} {msg}")
        if fix:
            print(f"      {'Fix: ' if en else '修复：'}{fix}")
        if icon == BAD and required:
            blocked = True
    print("-" * 64)
    if blocked:
        print("Result: a required item has a problem, so screenshots / flow diagrams cannot run; follow the \"Fix\" lines above first." if en
              else "结论：存在必需项问题，截图/流程图无法运行，请先按上面的“修复”处理。")
        return 1
    optional_missing = [m for i, m, f, r in rows if i != OK and not r]
    if optional_missing:
        print("Result: PRDs and prototypes can be generated; the optional items marked ⚠️ above only affect publishing." if en
              else "结论：可以生成 PRD 和原型；上面标 ⚠️ 的可选项只影响发布功能。")
    else:
        print("Result: the environment is complete." if en else "结论：环境完整。")
    return 0


# ───────────────────────── 开场巡检：给 AI 用的简短状态 ─────────────────────────
# 状态码：OK / OLD_PYTHON / NO_PLAYWRIGHT / NO_BROWSER / NO_FONT
# NO_PLAYWRIGHT / NO_BROWSER 额外给出 SYSTEM_BROWSER=chrome,msedge 或 none，用来决定提示“只装小组件”还是“还要下载浏览器”。
# 测试钩子：环境变量 PRDKIT_FORCE_STATUS 可强制返回某个状态（仅回归测试使用）。

def status():
    """返回 (状态码, 系统浏览器列表)。不输出任何内容、不安装任何东西。"""
    from . import browser
    sys_browsers = browser.find_system_browsers()
    forced = os.environ.get("PRDKIT_FORCE_STATUS", "").strip().upper()
    if forced:
        return forced, sys_browsers
    if sys.version_info < (3, 8):
        return "OLD_PYTHON", sys_browsers
    try:
        import playwright  # noqa: F401
    except ImportError:
        return "NO_PLAYWRIGHT", sys_browsers
    ok, _label, _err = browser.probe()
    if not ok:
        return "NO_BROWSER", sys_browsers
    from . import fontcheck
    try:
        font_ok, _msg = fontcheck.has_cjk_font()
    except Exception:
        font_ok = True      # 字体检测本身出错时不拦用户，截图阶段还有一道字体闸门
    return ("OK" if font_ok else "NO_FONT"), sys_browsers


def brief():
    """打印两行机器可读结果；通过返回 0，否则返回 1。"""
    st, sys_browsers = status()
    print(f"ENV={st}")
    print("SYSTEM_BROWSER=" + (",".join(sys_browsers) if sys_browsers else "none"))
    return 0 if st == "OK" else 1
