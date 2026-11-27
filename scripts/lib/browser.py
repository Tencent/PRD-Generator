# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""browser：统一选择截图 / 流程图渲染用的浏览器。

顺序：用户电脑上已有的 Chrome → Edge → Playwright 自带的 Chromium。哪个能启动就用哪个，启动失败静默跳过。
好处：用户电脑上有 Chrome 或 Edge 时，只需要一个很小的 Python 组件，不必再下载约 150MB 的浏览器。
说明：全程无窗口模式，使用独立的临时配置，不会弹窗，也不会动用户 Chrome 的账号和数据。

环境变量 PRDKIT_BROWSER=chrome|msedge|chromium 可强制指定（调试和对比用）。
"""
import os
import platform
import shutil
from pathlib import Path

_CHOICE = {"name": None}      # 本进程内记住已选定的浏览器，避免每次重试失败的候选
ORDER = ("chrome", "msedge", None)   # None = Playwright 自带的 Chromium
LABEL = {"chrome": "Chrome", "msedge": "Edge", None: "内置浏览器"}


def order():
    """候选顺序；PRDKIT_BROWSER 可强制只用某一个。"""
    forced = os.environ.get("PRDKIT_BROWSER", "").strip().lower()
    if forced in ("chrome", "msedge"):
        return [forced]
    if forced in ("chromium", "bundled"):
        return [None]
    return list(ORDER)


def find_system_browsers():
    """不依赖 Playwright，检测电脑上有没有 Chrome / Edge，返回 ['chrome', 'msedge'] 的子集（用于给用户的提示）。"""
    sysname = platform.system()
    home = Path.home()
    found = []
    if sysname == "Darwin":
        paths = {
            "chrome": ["/Applications/Google Chrome.app", str(home / "Applications" / "Google Chrome.app")],
            "msedge": ["/Applications/Microsoft Edge.app", str(home / "Applications" / "Microsoft Edge.app")],
        }
        for k, ps in paths.items():
            if any(Path(p).exists() for p in ps):
                found.append(k)
    elif sysname == "Windows":
        roots = [os.environ.get("PROGRAMFILES", r"C:\Program Files"), os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                 os.environ.get("LOCALAPPDATA", "")]
        rel = {"chrome": r"Google\Chrome\Application\chrome.exe", "msedge": r"Microsoft\Edge\Application\msedge.exe"}
        for k, r in rel.items():
            if any(root and (Path(root) / r).exists() for root in roots):
                found.append(k)
    else:
        names = {"chrome": ("google-chrome", "google-chrome-stable"), "msedge": ("microsoft-edge", "microsoft-edge-stable")}
        for k, ns in names.items():
            if any(shutil.which(n) for n in ns):
                found.append(k)
    return found


def launch(p, **kw):
    """在 sync_playwright() 的 p 上启动浏览器，返回 Browser。按 ORDER 依次尝试。"""
    candidates = [_CHOICE["name"]] if _CHOICE.get("chosen") else order()
    last = None
    for ch in candidates:
        args = {"args": ["--no-sandbox"]}
        if ch:
            args["channel"] = ch
        args.update(kw)
        try:
            b = p.chromium.launch(**args)
            _CHOICE["name"], _CHOICE["chosen"] = ch, True
            return b
        except Exception as e:     # 候选不可用：静默换下一个
            last = e
    raise last if last else RuntimeError("没有可用的浏览器")


def chosen_label():
    """已选定浏览器的中文名；还没启动过则返回 None。"""
    return LABEL.get(_CHOICE["name"]) if _CHOICE.get("chosen") else None


def probe():
    """实际启动一次，返回 (是否可用, 浏览器中文名, 错误摘要)。需要已安装 Playwright 包。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, None, "playwright 未安装"
    err = ""
    with sync_playwright() as p:
        for ch in order():
            args = {"args": ["--no-sandbox"]}
            if ch:
                args["channel"] = ch
            try:
                b = p.chromium.launch(**args)
                b.close()
                return True, LABEL[ch], ""
            except Exception as e:
                msg = str(e).strip().splitlines()[0][:100] if str(e).strip() else "未知错误"
                err = err or msg
    return False, None, err
