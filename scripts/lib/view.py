# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""view / open：把成品交到用户眼前（仅本机，不写入 PRD，不发给别人）。

- `prdkit view --demo`   起本机预览服务，返回交互 Demo（prototype/index.html）的 http 地址
- `prdkit view --style`  把风格对比图排成一页，起本机预览服务，返回页面地址
- `prdkit view --stop`   关闭本机预览服务
- `prdkit open [文件]`   在 IDE 编辑器里打开 PRD（默认项目里的 *-prd.md）；不可用时静默降级，只给路径

为什么 Demo 必须走 http：编辑器里“预览”按钮渲染本地 html 时，页面地址是 IDE 内部的 vscode-resource 虚拟域名，
点页面里的链接会被交给系统浏览器，而这个域名外部解析不了（DNS_PROBE_FINISHED_NXDOMAIN）。
走 http://127.0.0.1:端口/ 则在 IDE 预览窗和浏览器里都能正常跳转。

预览服务 = 项目根目录上的 127.0.0.1 静态服务（统一声明 UTF-8，避免 md/html 乱码），由本命令后台启动、复用、关闭。
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    from . import i18n
except ImportError:      # 预览服务子进程以独立脚本方式启动（python view.py --serve），没有包上下文；服务本身不需要 i18n
    i18n = None

STATE_FILE = "view-server.json"


# ───────────────────────── 风格对比页 ─────────────────────────

_CSS = """
*{box-sizing:border-box}body{margin:0;font:14px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:#1f2329;background:#f5f6f8}
.in{max-width:1200px;margin:0 auto;padding:24px 28px 60px}h1{font-size:24px;margin:.2em 0 .6em}h2{font-size:17px;margin:1.6em 0 .5em}
p.img{margin:.6em 0}img{max-width:100%;height:auto;border:1px solid #e5e6eb;border-radius:8px;background:#fff}
"""


def build_style_page(proj):
    """把 .prdkit/style-preview/ 里的对比图排成一页，返回路径；没有图则返回 None。"""
    d = proj.state / "style-preview"
    imgs = [n for n in ("style-compare-app.png", "style-compare-pc.png") if (d / n).exists()]
    if not imgs:
        return None
    en = i18n.cur() == "en"
    label = ({"style-compare-app.png": "Mobile (APP / mini program / H5): four styles compared",
              "style-compare-pc.png": "PC admin: four styles compared"} if en else
             {"style-compare-app.png": "移动端（APP / 小程序 / H5）四种风格对比",
              "style-compare-pc.png": "PC 后台四种风格对比"})
    blocks = "".join('<h2>%s</h2><p class="img"><img src="%s"></p>' % (label[n], n) for n in imgs)
    page_title = "Visual style comparison" if en else "视觉风格对比"
    page = ('<!doctype html><html lang="%s"><head><meta charset="utf-8"><title>%s</title>'
            "<style>%s</style></head><body><div class=\"in\"><h1>%s</h1>%s</div></body></html>") % (
        "en" if en else "zh-CN", page_title, _CSS, page_title, blocks)
    out = d / "index.html"
    out.write_text(page, encoding="utf-8")
    return out, [d / n for n in imgs]


# ───────────────────────── 本机预览服务 ─────────────────────────

IDLE_SECONDS = 4 * 3600   # 空闲这么久没人访问，服务自动退出（再用时 prdkit view 会自动重启）


def _serve(port, root):
    """服务进程入口：127.0.0.1 静态服务，统一声明 UTF-8；禁用目录列表；空闲超时自动退出。"""
    import functools
    import http.server
    import threading

    last = {"t": time.time()}

    class H(http.server.SimpleHTTPRequestHandler):
        extensions_map = {
            **http.server.SimpleHTTPRequestHandler.extensions_map,
            ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
            ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8",
            ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml",
        }

        def list_directory(self, path):   # 不暴露目录列表：同机其他用户看不到有哪些文件
            self.send_error(404, "Not Found")
            return None

        def log_message(self, *a):
            last["t"] = time.time()

    handler = functools.partial(H, directory=root)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", int(port)), handler)

    def _watch():
        while True:
            time.sleep(60)
            if time.time() - last["t"] > IDLE_SECONDS:
                srv.shutdown()
                return

    threading.Thread(target=_watch, daemon=True).start()
    try:
        srv.serve_forever()
    finally:
        srv.server_close()


def _alive(pid):
    """进程是否还在（不发送任何会终止进程的信号；兼容 Windows）。"""
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True, timeout=5).stdout
            return str(pid) in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)   # POSIX 下信号 0 只探测存在性
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _is_ours(pid):
    """PID 是否仍是本模块启动的预览服务（防止 PID 被系统复用后误杀别的进程）。"""
    try:
        if os.name == "nt":
            return True   # Windows 上无法低成本取命令行；_alive 已确认进程存在
        proc = Path("/proc/%d/cmdline" % pid)
        if proc.exists():
            cmd = proc.read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore")
        else:
            cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=5).stdout
        return "view.py" in cmd and "--serve" in cmd
    except Exception:
        return False


def _responds(port):
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=1.5).close()
        return True
    except Exception as e:  # 目录列表 / 404 都说明服务活着
        return getattr(e, "code", None) is not None


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ensure_server(proj):
    """启动（或复用）项目根目录上的 127.0.0.1 静态服务，返回端口。"""
    proj.state.mkdir(parents=True, exist_ok=True)
    sf = proj.state / STATE_FILE
    if sf.exists():
        try:
            st = json.loads(sf.read_text(encoding="utf-8"))
            if st.get("root") == str(proj.root) and _alive(st["pid"]) and _responds(st["port"]):
                return st["port"]
            stop(proj, quiet=True)
        except Exception:
            pass
    port = _free_port()
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve", str(port), str(proj.root)], **kw)
    for _ in range(40):
        if _responds(port):
            break
        time.sleep(0.1)
    sf.write_text(json.dumps({"pid": p.pid, "port": port, "root": str(proj.root)}), encoding="utf-8")
    return port


def stop(proj, quiet=False):
    sf = proj.state / STATE_FILE
    if not sf.exists():
        if not quiet:
            print(i18n.t("预览服务未在运行。", "The preview server is not running."))
        return 0
    try:
        st = json.loads(sf.read_text(encoding="utf-8"))
        if _alive(st["pid"]) and _is_ours(st["pid"]):
            os.kill(st["pid"], signal.SIGTERM)
    except Exception:
        pass
    try:
        sf.unlink()
    except OSError:
        pass
    if not quiet:
        print(i18n.t("✅ 预览服务已关闭。", "✅ The preview server has been stopped."))
    return 0


def cmd_view(proj, style=False, demo=False, stop_server=False, bundle=False):
    if stop_server:
        return stop(proj)
    if style:
        built = build_style_page(proj)
        if not built:
            print(i18n.t("❌ 还没有风格对比图。请先运行 prdkit style preview。", "❌ There is no style comparison image yet. Run prdkit style preview first."))
            return 1
        page, imgs = built
        kind = i18n.t("风格对比图", "Style comparison")
    elif bundle:   # 单文件 Demo：只为交付时在预览窗自动打开；看 Demo 本身不依赖这个服务
        cands = sorted(proj.root.glob("*-demo.html"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not cands:
            print(i18n.t("❌ 还没有单文件 Demo。请先运行 prdkit bundle。", "❌ There is no single-file demo yet. Run prdkit bundle first."))
            return 1
        page = cands[0]
        imgs = []
        kind = i18n.t("单文件 Demo", "Single-file demo")
    else:  # 默认即 --demo
        page = proj.proto / "index.html"
        imgs = []
        if not page.exists():
            print(i18n.t("❌ 还没有 prototype/index.html。请先运行 prdkit index。", "❌ prototype/index.html does not exist yet. Run prdkit index first."))
            return 1
        kind = i18n.t("交互 Demo", "Interactive demo")
    port = ensure_server(proj)
    rel = page.relative_to(proj.root).as_posix()
    if bundle:
        print(i18n.t("✅ 单文件 Demo 的自动打开地址已就绪（仅用于在预览窗自动打开；Demo 本身是独立文件，不依赖这个地址）",
                     "✅ The auto-open address of the single-file demo is ready (only used to open it in the preview pane automatically; the demo itself is a standalone file and does not depend on this address)"))
    else:
        print(i18n.t("✅ %s预览已就绪（本机服务，IDE 预览窗和浏览器都能打开；点页面请在这个地址里点）" % kind,
                     "✅ %s preview is ready (local server; opens in IDE preview panes and browsers; click through pages at this address)" % kind))
    print(i18n.t("预览地址：http://127.0.0.1:%d/%s" % (port, rel), "Preview address: http://127.0.0.1:%d/%s" % (port, rel)))
    print(i18n.t("本地文件：%s" % page, "Local file: %s" % page))
    for i in imgs:
        print(i18n.t("图片文件：%s" % i, "Image file: %s" % i))
    return 0


# ───────────────────────── 在 IDE 编辑器里打开文件 ─────────────────────────

def _find_ide_cli():
    """找 IDE 自带的命令行（VS Code 系：code / buddycn 等）。优先 PATH，其次扫描 ~/.codebuddy-server-cn 与 ~/.vscode-server。"""
    for name in ("buddycn", "codebuddy-cn", "code"):
        p = shutil.which(name)
        if p and "cargo" not in p:
            return p
    home = Path.home()
    cands = []
    for pat in (".codebuddy-server-cn/bin/*/bin/remote-cli/*", ".vscode-server/bin/*/bin/remote-cli/code"):
        cands += [c for c in home.glob(pat) if c.is_file() and os.access(c, os.X_OK)]
    cands.sort(key=lambda c: c.stat().st_mtime, reverse=True)
    return str(cands[0]) if cands else None


def _ipc_ok():
    sock = os.environ.get("VSCODE_IPC_HOOK_CLI")
    return bool(sock and Path(sock).exists())


def cmd_open(proj, target=None):
    """在 IDE 编辑器里打开文件。失败不报错（降级为由对话给出路径），始终返回 0。"""
    if target:
        f = Path(target).expanduser().resolve()
    else:
        f = proj.prd_md()
    if not f or not Path(f).exists():
        print(i18n.t("❌ 找不到要打开的文件：%s" % (target or "项目里的 PRD（*-prd.md）"),
                     "❌ File to open not found: %s" % (target or "the PRD in the project (*-prd.md)")))
        return 1
    cli = _find_ide_cli()
    if not cli or not _ipc_ok():
        print(i18n.t("ℹ️  当前环境没法由命令行驱动 IDE 打开文件，请把路径给用户自己点开：",
                     "ℹ️  This environment cannot drive the IDE from the command line; give the path to the user to open themselves:"))
        print(i18n.t("文件路径：%s" % f, "File path: %s" % f))
        return 0
    try:
        r = subprocess.run([cli, "--reuse-window", "-g", str(f)], capture_output=True, text=True, timeout=20)
        ok = r.returncode == 0
    except Exception:
        ok = False
    print((i18n.t("✅ 已请求 IDE 在编辑器里打开：", "✅ Asked the IDE to open it in the editor: ") if ok
           else i18n.t("ℹ️  IDE 没响应，请把路径给用户自己点开：", "ℹ️  The IDE did not respond; give the path to the user to open themselves: ")) + str(f))
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--serve":
        _serve(sys.argv[2], sys.argv[3])
