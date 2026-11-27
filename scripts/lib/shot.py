# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""shot：按 screens.json 对原型的每个“页面状态 / 弹窗”截图，输出到 images/。

特点：
- 内置临时 HTTP 服务（端口自动分配），不依赖任何外部预览服务或固定端口
- 每个 screen 一个独立浏览器上下文，互不污染状态
- 支持 actions（click / eval / wait / fill / hover），用于展开弹窗、切换状态
- 默认 2x 清晰度；视口可被单个 screen 覆盖（例如 PC 页 1440）
- 记录页面 JS 报错，避免“截到半截页面却没人发现”
- 写 .prdkit/shots.json（md5/尺寸/时间），供增量发布使用
"""
import functools
import http.server
import socketserver
import threading
import time
from pathlib import Path

from .common import dump_json, md5_file
from . import spec as specmod
from . import i18n


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


class _Server:
    def __init__(self, directory):
        handler = functools.partial(_QuietHandler, directory=str(directory))
        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.t.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


def _run_actions(page, actions):
    for a in actions or []:
        (k, v), = a.items()
        if k == "click":
            page.click(v, timeout=5000)
        elif k == "hover":
            page.hover(v, timeout=5000)
        elif k == "eval":
            page.evaluate(v)
        elif k == "fill":
            page.fill(v[0], v[1], timeout=5000)
        elif k == "wait":
            page.wait_for_timeout(int(v))
        page.wait_for_timeout(120)


def take_shots(proj, only=None, chapter=None, dpr=None, settle_ms=450):
    """返回 (成功数, 失败列表)。"""
    from playwright.sync_api import sync_playwright
    from . import browser as _browser

    issues, screens = specmod.validate_screens(proj)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        for i in errors:
            print(i)
        raise SystemExit(i18n.t("spec 存在错误，已中止截图。先修复上面的问题。", "The spec has errors; screenshots aborted. Fix the issues above first."))

    from . import fontcheck
    fontcheck.require()

    data = proj.load_screens()
    base_vp = data["viewport"]
    base_dpr = dpr or base_vp.get("dpr", 2)
    want = [s for s in data["screens"]
            if (not only or s["id"] in only) and (not chapter or s["chapter"] == chapter)]
    if only:
        miss = set(only) - {s["id"] for s in want}
        if miss:
            raise SystemExit(i18n.t(f"未找到页面：{', '.join(sorted(miss))}", f"Pages not found: {', '.join(sorted(miss))}"))
    if not want:
        raise SystemExit(i18n.t("没有需要截图的页面（检查 --only / --chapter）", "No pages to screenshot (check --only / --chapter)"))

    proj.images.mkdir(parents=True, exist_ok=True)
    proj.state.mkdir(parents=True, exist_ok=True)
    manifest_path = proj.state / "shots.json"
    manifest = {}
    if manifest_path.exists():
        try:
            import json
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    ok, failed = 0, []
    with _Server(proj.proto) as srv, sync_playwright() as p:
        browser = _browser.launch(p)
        for s in want:
            vp = s.get("viewport") or base_vp
            ctx = browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                device_scale_factor=vp.get("dpr", base_dpr),
            )
            page = ctx.new_page()
            js_errors = []
            page.on("pageerror", lambda e, acc=js_errors: acc.append(str(e)))
            out = proj.images / s["shot"]
            try:
                page.goto(f"http://127.0.0.1:{srv.port}/{s['url'].lstrip('/')}", wait_until="load", timeout=20000)
                page.wait_for_timeout(settle_ms)
                _run_actions(page, s.get("actions"))
                page.wait_for_timeout(settle_ms)
                if s.get("selector"):
                    page.locator(s["selector"]).first.screenshot(path=str(out))
                else:
                    page.screenshot(path=str(out), full_page=s.get("full_page", True))
                manifest[s["id"]] = {
                    "file": s["shot"], "md5": md5_file(out), "bytes": out.stat().st_size,
                    "viewport": [vp["width"], vp["height"]], "dpr": vp.get("dpr", base_dpr),
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                if js_errors:
                    manifest[s["id"]]["js_errors"] = [x[:160] for x in js_errors[:3]]
                note = i18n.t(f"  ⚠️ 页面 JS 报错 {len(js_errors)} 条：{js_errors[0][:80]}", f"  ⚠️ {len(js_errors)} page JS error(s): {js_errors[0][:80]}") if js_errors else ""
                print(f"✅ {s['id']:<24} → images/{s['shot']} ({out.stat().st_size // 1024}KB){note}")
                ok += 1
            except Exception as e:
                msg = str(e).splitlines()[0][:120]
                print(i18n.t(f"❌ {s['id']:<24} 失败：{msg}", f"❌ {s['id']:<24} failed: {msg}"))
                failed.append((s["id"], msg))
            finally:
                ctx.close()
        browser.close()

    dump_json(manifest_path, manifest)
    return ok, failed
