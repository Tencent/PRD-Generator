# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""setup：安装缺失的截图组件。绝不擅自安装：不加 --yes 只预演，用户明确同意后才加 --yes。

流程（按 doctor.status() 的状态决定）：
  OK              → 什么都不做
  NO_PLAYWRIGHT   → 装 playwright 小组件；如果电脑上没有 Chrome / Edge，再下载内置浏览器
  NO_BROWSER      → 只下载内置浏览器
  NO_FONT / OLD_PYTHON → 需要用户自己处理（要 sudo 或换 Python），只给指引，不自动动手

提速：
  - 默认走官方源；网络受限时可用环境变量指定镜像：PRDKIT_PIP_MIRROR（pip）、PRDKIT_BROWSER_MIRROR（浏览器下载源）
  - 镜像先用 3 秒探测，可达（浏览器镜像还需文件齐全）才用，否则走官方源，不靠“失败后再切换”慢慢等
  - 有 Chrome / Edge 就完全不下载浏览器

安全：不使用 sudo，不使用 --break-system-packages；系统禁止装包时如实说明并给手动指引。
"""
import os
import re
import subprocess
import sys
import urllib.request

from . import doctor
from . import i18n

# 可选镜像：默认走官方源。网络受限时，可用环境变量指定（例如 PRDKIT_PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple）
PIP_MIRROR = os.environ.get("PRDKIT_PIP_MIRROR", "").strip().rstrip("/")
PIP_MIRROR_PROBE = PIP_MIRROR + "/playwright/" if PIP_MIRROR else ""
BROWSER_MIRROR = os.environ.get("PRDKIT_BROWSER_MIRROR", "").strip()
PIP_SPEC = "playwright>=1.40"


def _reachable(url, timeout=3):
    """HEAD 探测：2xx / 3xx 算可达。失败或超时返回 False。"""
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout).close()
        return True
    except Exception as e:
        code = getattr(e, "code", None)
        return bool(code and 200 <= code < 400)


def plan_for(status, sys_browsers):
    """纯函数：返回要执行的步骤列表（用于预演和测试）。"""
    if status == "OK":
        return []
    if status == "NO_PLAYWRIGHT":
        steps = ["pip"]
        if not sys_browsers:
            steps.append("browser")
        return steps
    if status == "NO_BROWSER":
        return ["browser"]
    return ["manual"]     # NO_FONT / OLD_PYTHON / 其他：需要用户自己处理


def _in_venv():
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


_WHY_EN = {
    "系统禁止直接安装 Python 组件（受保护的系统环境）": "the system forbids installing Python packages directly (externally managed environment)",
    "网络下载失败": "network download failed",
    "安装命令报错": "the install command failed",
    "下载超时": "download timed out",
}


def _why(w):
    return i18n.t(w, _WHY_EN.get(w, w))


def _pip_install():
    """安装 playwright 包。返回 (成功, 原因)。"""
    use_mirror = bool(PIP_MIRROR) and _reachable(PIP_MIRROR_PROBE)
    print(i18n.t("→ 安装截图组件 Playwright（%s）…" % ("自定义镜像" if use_mirror else "官方源"),
                 "→ Installing Playwright (screenshot component) (%s)…" % ("custom mirror" if use_mirror else "official source")), flush=True)
    base = [sys.executable, "-m", "pip", "install", PIP_SPEC, "--timeout", "15", "--retries", "1", "--disable-pip-version-check"]
    attempts = []
    if use_mirror:
        attempts.append(base + ["-i", PIP_MIRROR])
    attempts.append(base)       # 官方源作为兜底；镜像不可达时它就是第一选择
    last = ""
    for i, cmd in enumerate(attempts):
        for user in ([False, True] if not _in_venv() else [False]):
            c = cmd + (["--user"] if user else [])
            r = subprocess.run(c, capture_output=True, text=True)
            if r.returncode == 0:
                return True, ""
            last = (r.stderr or r.stdout or "").strip()
            if "externally-managed-environment" in last:
                return False, "系统禁止直接安装 Python 组件（受保护的系统环境）"
            if not re.search(r"Permission denied|EACCES|not writeable|PermissionError", last):
                break           # 不是权限问题，不必再试 --user
    reason = "网络下载失败" if re.search(r"timed out|Connection|connect|SSL|Temporary failure|Name or service", last, re.I) else "安装命令报错"
    return False, reason


def _browser_env():
    """内置浏览器下载源：镜像文件全部齐全才用镜像，否则用官方（返回环境变量字典）。"""
    env = dict(os.environ)
    if not BROWSER_MIRROR:
        return env, "官方源"
    try:
        r = subprocess.run([sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
                           capture_output=True, text=True, timeout=60,
                           env={**os.environ, "PLAYWRIGHT_DOWNLOAD_HOST": BROWSER_MIRROR})
        urls = re.findall(r"Download url:\s+(\S+)", r.stdout)
        if urls and all(_reachable(u) for u in set(urls)):
            env["PLAYWRIGHT_DOWNLOAD_HOST"] = BROWSER_MIRROR
            return env, "镜像"
    except Exception:
        pass
    return env, "官方源"


def _browser_install():
    env, src = _browser_env()
    print(i18n.t("→ 下载内置浏览器（%s，约 150MB，请耐心等待）…" % src,
                 "→ Downloading the bundled browser (%s, about 150MB, please wait)…" % ("mirror" if src == "镜像" else "official source")), flush=True)
    try:
        r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                           capture_output=True, text=True, env=env, timeout=900)
    except subprocess.TimeoutExpired:
        return False, "下载超时"
    if r.returncode == 0:
        return True, ""
    last = (r.stderr or r.stdout or "").strip()
    reason = "网络下载失败" if re.search(r"timed out|Connection|connect|SSL|ECONN|ENOTFOUND|getaddrinfo|Download failed", last, re.I) else "安装命令报错"
    return False, reason


def run(yes=False):
    st, sys_browsers = doctor.status()
    steps = plan_for(st, sys_browsers)
    if not steps:
        print(i18n.t("✅ 环境已就绪，无需安装。", "✅ The environment is ready; nothing to install."))
        return 0
    if steps == ["manual"]:
        if st == "OLD_PYTHON":
            print(i18n.t("ℹ️  Python 版本过低（需要 3.8 及以上），无法自动处理。请先升级 Python 后重试。",
                         "ℹ️  Python is too old (3.8 or newer is required) and cannot be fixed automatically. Upgrade Python and retry."))
        else:
            from . import fontcheck
            print(i18n.t("ℹ️  缺少中文字体，需要系统管理权限，无法自动处理。", "ℹ️  A CJK font is missing; installing it needs system privileges, so it cannot be done automatically."))
            print("   " + i18n.t(fontcheck.INSTALL_HINT, fontcheck.INSTALL_HINT_EN))
        return 2

    names = {"pip": "安装截图组件 Playwright", "browser": "下载 Chromium 浏览器（电脑上没有 Chrome / Edge）"}
    names_en = {"pip": "install Playwright (screenshot component)", "browser": "download the Chromium browser (no Chrome / Edge found)"}
    print(i18n.t("将要执行：" + "；".join(names[s] for s in steps), "About to run: " + "; ".join(names_en[s] for s in steps)))
    if not yes:
        print(i18n.t("预演：未加 --yes，没有执行任何安装。用户明确同意后再加 --yes。",
                     "Dry run: --yes was not given, so nothing was installed. Add --yes only after the user explicitly agrees."))
        return 0

    if "pip" in steps:
        ok, why = _pip_install()
        if not ok:
            print(i18n.t("❌ Playwright 没装成功：%s" % why, "❌ Playwright was not installed: %s" % _why(why)))
            print(i18n.t("   手动安装：python3 -m pip install playwright", "   Manual install: python3 -m pip install playwright"))
            return 1
        print(i18n.t("✅ Playwright 已安装", "✅ Playwright installed"))
    st2, _ = doctor.status()
    if st2 == "NO_BROWSER":
        ok, why = _browser_install()
        if not ok:
            print(i18n.t("❌ Chromium 浏览器没装成功：%s" % why, "❌ The Chromium browser was not installed: %s" % _why(why)))
            print(i18n.t("   手动安装：python3 -m playwright install chromium", "   Manual install: python3 -m playwright install chromium"))
            return 1
        print(i18n.t("✅ Chromium 浏览器已安装", "✅ Chromium browser installed"))
    st3, _ = doctor.status()
    if st3 == "OK":
        print(i18n.t("✅ 环境已就绪，已验证可以正常截图、中文显示正常。", "✅ The environment is ready; screenshots were verified to work."))
        return 0
    if st3 == "NO_FONT":
        from . import fontcheck
        print(i18n.t("⚠️  组件已装好，但缺少中文字体，需要你按指引处理：", "⚠️  The components are installed but a CJK font is missing; follow the hint:"))
        print("   " + i18n.t(fontcheck.INSTALL_HINT, fontcheck.INSTALL_HINT_EN))
        return 2
    print(i18n.t("❌ 安装后复查仍未通过（状态：%s）。请运行 prdkit doctor 查看详情。" % st3,
                 "❌ The re-check after installing still fails (status: %s). Run prdkit doctor for details." % st3))
    return 1
