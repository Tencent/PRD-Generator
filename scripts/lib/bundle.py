# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""bundle：把 prototype/ 打成【单文件】demo.html —— 不依赖服务、端口、网络，任何人拿到文件都能点。

为什么需要它
  多文件原型要靠 http 服务或文件系统才能互相跳转。IDE 内置预览（webview）会拦截页内链接并交给系统浏览器，
  浏览器又解析不了 IDE 的虚拟域名，于是“只有首页能开、点别的页面报错”；而 http 服务还会被关闭、被空闲回收。
  单文件把所有页面装进同一个文档，页面切换在文档内完成，不产生任何导航，也不需要任何后台进程。

做法
  · 每个页面原样放进一个 <iframe srcdoc>（样式/脚本互不污染，渲染与单页完全一致）
  · 页面里引用的本地样式、脚本、图片、字体全部内联
  · 页面脚本里的 location / history / window.open 被改写为“伪 location”，页面跳转与 ?s=状态 都由外层文档接管
  · <a href>、data-go、onclick 里的跳转一律在文档内完成
  · 外层只加一个很小的悬浮按钮（返回 / 导航页），因为单文件没有地址栏可用

不改动：prototype/ 源文件、截图、流程图、lint、PRD、zip 打包——bundle 只读取 prototype/，另外输出一个文件。
"""
import base64
import html as htmllib
import json
import mimetypes
import posixpath
import re
from pathlib import Path

from . import i18n

MAX_WARN = 20 * 1024 * 1024
START_KEYS = ("index.html",)


class BundleError(Exception):
    pass


# ───────────────────────── JS 改写：location / history / window.open ─────────────────────────
_LOC_ASSIGN = re.compile(r"(?<![\w$.])(?:(?:window|document|top|parent|self)\s*\.\s*)?location\s*=(?!=)")
_LOC = re.compile(r"(?<![\w$.])(?:(?:window|document|top|parent|self)\s*\.\s*)?location(?![\w$])")
_HIST = re.compile(r"(?<![\w$.])(?:window\s*\.\s*)?history(?![\w$])")
_OPEN = re.compile(r"(?<![\w$.])window\s*\.\s*open\s*\(")


def _fix_code(seg):
    seg = _LOC_ASSIGN.sub("__PRD_LOC.href=", seg)
    seg = _LOC.sub("__PRD_LOC", seg)
    seg = _HIST.sub("__PRD_HIST", seg)
    seg = _OPEN.sub("__PRD_OPEN(", seg)
    return seg


def _scan_code(code, i, stop_at_brace):
    """扫描 JS：字符串/注释原样保留，其余片段做改写。返回 (文本, 结束位置)。"""
    out, buf, n, depth = [], [], len(code), 0

    def flush():
        if buf:
            out.append(_fix_code("".join(buf)))
            buf.clear()

    while i < n:
        c = code[i]
        if stop_at_brace:
            if c == "{":
                depth += 1
            elif c == "}":
                if depth == 0:
                    flush()
                    return "".join(out), i
                depth -= 1
        if c in "\"'":
            flush()
            j = i + 1
            while j < n and code[j] != c:
                if code[j] == "\n":
                    raise ValueError("unterminated string")
                j += 2 if code[j] == "\\" else 1
            if j >= n:
                raise ValueError("unterminated string")
            out.append(code[i:j + 1])
            i = j + 1
        elif c == "`":
            flush()
            txt, i = _scan_template(code, i)
            out.append(txt)
        elif code.startswith("//", i):
            flush()
            j = code.find("\n", i)
            j = n if j < 0 else j
            out.append(code[i:j])
            i = j
        elif code.startswith("/*", i):
            flush()
            j = code.find("*/", i + 2)
            if j < 0:
                raise ValueError("unterminated comment")
            out.append(code[i:j + 2])
            i = j + 2
        else:
            buf.append(c)
            i += 1
    if stop_at_brace:
        raise ValueError("unterminated template expression")
    flush()
    return "".join(out), i


def _scan_template(code, i):
    out, n = ["`"], len(code)
    i += 1
    while i < n:
        c = code[i]
        if c == "\\":
            out.append(code[i:i + 2])
            i += 2
        elif c == "`":
            out.append("`")
            return "".join(out), i + 1
        elif code.startswith("${", i):
            out.append("${")
            inner, i = _scan_code(code, i + 2, True)
            out.append(inner)
            out.append("}")
            i += 1
        else:
            out.append(c)
            i += 1
    raise ValueError("unterminated template")


def rewrite_js(code):
    """改写 JS 里的 location/history/window.open。扫描失败（正则字面量等罕见写法）时退回到整段正则替换。"""
    if not re.search(r"location|history|window\s*\.\s*open", code):
        return code
    try:
        return _scan_code(code, 0, False)[0]
    except ValueError:
        return _fix_code(code)


# ───────────────────────── HTML 处理 ─────────────────────────
_ATTR = re.compile(r"""([^\s=/>"']+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?""")
_TAG_LINK = re.compile(r"<link\b[^>]*>", re.I)
_TAG_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.I | re.S)
_TAG_MEDIA = re.compile(r"(<(?:img|source|video|audio|input|image)\b[^>]*?\s(?:src|poster)\s*=\s*)([\"'])([^\"']*)\2", re.I)
_ON_ATTR = re.compile(r"""(\son[a-z]+\s*=\s*)(?:"([^"]*)"|'([^']*)')""", re.I)
_JS_HREF = re.compile(r"""(\shref\s*=\s*)(?:"(javascript:[^"]*)"|'(javascript:[^']*)')""", re.I)
_URL_FN = re.compile(r"""url\(\s*(["']?)([^"')]+)\1\s*\)""", re.I)
_HEAD_OPEN = re.compile(r"<head\b[^>]*>", re.I)
_HTML_OPEN = re.compile(r"<html\b[^>]*>", re.I)
PAGE_MARK = "<!--__PRD_PAGE__-->"


def _attrs(tag_inner):
    d = {}
    for m in _ATTR.finditer(tag_inner):
        v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else (m.group(4) or ""))
        d[m.group(1).lower()] = v
    return d


def _is_remote(ref):
    r = ref.strip().lower()
    return (not r) or r.startswith(("http:", "https:", "//", "data:", "blob:", "#", "javascript:", "mailto:", "tel:", "about:"))


class _Ctx:
    def __init__(self, proto):
        self.proto = Path(proto)
        self.warnings = []
        self.cache = {}

    def asset_path(self, from_rel, ref):
        """相对 from_rel（页面或样式文件）解析 ref，返回 prototype/ 内的文件路径；越界或不存在返回 None。"""
        p = re.split(r"[?#]", ref, 1)[0]
        rel = posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), p))
        if rel.startswith("..") or rel.startswith("/"):
            return None
        f = self.proto / rel
        return f if f.is_file() else None

    def data_uri(self, f):
        key = str(f)
        if key not in self.cache:
            mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            self.cache[key] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode("ascii")
        return self.cache[key]


def _inline_urls(text, ctx, from_rel):
    def sub(m):
        ref = m.group(2).strip()
        if _is_remote(ref):
            return m.group(0)
        f = ctx.asset_path(from_rel, ref)
        if not f:
            ctx.warnings.append(i18n.t(f"{from_rel}：找不到引用的资源 {ref}", f"{from_rel}: referenced resource not found: {ref}"))
            return m.group(0)
        return f'url("{ctx.data_uri(f)}")'
    return _URL_FN.sub(sub, text)


def _safe_script_text(js):
    return re.sub(r"</(script)", r"<\\/\1", js, flags=re.I)


def process_page(text, rel, ctx):
    """把一个页面处理成可放进 srcdoc 的自包含 HTML。"""
    # 1) 样式表 <link>
    def link_sub(m):
        a = _attrs(m.group(0)[5:-1])
        relv = a.get("rel", "").lower()
        href = a.get("href", "")
        if "stylesheet" in relv:
            if _is_remote(href):
                ctx.warnings.append(i18n.t(f"{rel}：引用了外部样式 {href}（离线时会丢失）", f"{rel}: references an external stylesheet {href} (lost when offline)"))
                return m.group(0)
            f = ctx.asset_path(rel, href)
            if not f:
                raise BundleError(i18n.t(f"{rel}：找不到样式文件 {href}", f"{rel}: stylesheet not found: {href}"))
            css = _inline_urls(f.read_text(encoding="utf-8"), ctx, f.relative_to(ctx.proto).as_posix())
            return f"<style data-src=\"{htmllib.escape(href)}\">\n{css}\n</style>"
        if any(k in relv for k in ("icon", "apple-touch", "manifest", "preload", "prefetch")) and not _is_remote(href):
            return ""
        return m.group(0)
    text = _TAG_LINK.sub(link_sub, text)

    # 2) 脚本：本地 src 内联；内联脚本改写
    def script_sub(m):
        a = _attrs(m.group(1))
        typ = a.get("type", "").lower()
        if typ and typ not in ("text/javascript", "application/javascript", "module"):
            return m.group(0)      # JSON-LD、模板等原样保留
        attrs_txt = re.sub(r"""\s+src\s*=\s*(?:"[^"]*"|'[^']*'|\S+)""", "", m.group(1), flags=re.I)
        if "src" in a:
            src = a["src"]
            if _is_remote(src):
                ctx.warnings.append(i18n.t(f"{rel}：引用了外部脚本 {src}（离线时会丢失）", f"{rel}: references an external script {src} (lost when offline)"))
                return m.group(0)
            f = ctx.asset_path(rel, src)
            if not f:
                raise BundleError(i18n.t(f"{rel}：找不到脚本文件 {src}", f"{rel}: script file not found: {src}"))
            body = f.read_text(encoding="utf-8")
        else:
            body = m.group(2)
        if re.search(r"(^|\n)\s*import\s[^;\n]*\sfrom\s|\bimport\s*\(", body):
            raise BundleError(i18n.t(f"{rel}：脚本里使用了 import（ES 模块），单文件打包不支持。请改成普通脚本", f"{rel}: the script uses import (ES modules), which single-file packing does not support; rewrite it as a plain script"))
        if re.search(r"\bfetch\s*\(|XMLHttpRequest", body):
            ctx.warnings.append(i18n.t(f"{rel}：脚本里有网络请求（fetch/XHR），单文件内无法访问其它文件", f"{rel}: the script makes network requests (fetch/XHR), which cannot reach other files inside a single file"))
        body = _safe_script_text(rewrite_js(body))
        return f"<script{attrs_txt}>\n{body}\n</script>"
    text = _TAG_SCRIPT.sub(script_sub, text)

    # 3) on* 事件属性
    def on_sub(m):
        raw = m.group(2) if m.group(2) is not None else m.group(3)
        if not re.search(r"location|history|window\s*\.\s*open", raw):
            return m.group(0)
        js = rewrite_js(htmllib.unescape(raw))
        return m.group(1) + '"' + htmllib.escape(js, quote=True) + '"'
    text = _ON_ATTR.sub(on_sub, text)

    # 3b) href="javascript:..."：模板里的返回键就是 javascript:history.back()，必须改写，否则点击会执行真实的 history.back()
    def jshref_sub(m):
        raw = m.group(2) if m.group(2) is not None else m.group(3)
        code = htmllib.unescape(raw)[len("javascript:"):]
        if not re.search(r"location|history|window\s*\.\s*open", code):
            return m.group(0)
        return m.group(1) + '"javascript:' + htmllib.escape(rewrite_js(code), quote=True) + '"'
    text = _JS_HREF.sub(jshref_sub, text)

    # 4) 图片等媒体、样式里的 url()
    def media_sub(m):
        ref = m.group(3).strip()
        if _is_remote(ref):
            return m.group(0)
        f = ctx.asset_path(rel, ref)
        if not f:
            ctx.warnings.append(i18n.t(f"{rel}：找不到引用的资源 {ref}", f"{rel}: referenced resource not found: {ref}"))
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{ctx.data_uri(f)}{m.group(2)}"
    text = _TAG_MEDIA.sub(media_sub, text)
    text = _inline_urls(text, ctx, rel)

    # 5) 页面标记（外层在加载时写入当前页面的 key 与查询串，供伪 location 使用）
    shim = PAGE_MARK + "<script>" + _PAGE_SHIM + "</script>"
    m = _HEAD_OPEN.search(text)
    if m:
        text = text[:m.end()] + shim + text[m.end():]
    else:
        m = _HTML_OPEN.search(text)
        if m:
            text = text[:m.end()] + "<head>" + shim + "</head>" + text[m.end():]
        else:
            text = "<!DOCTYPE html><html><head>" + shim + "</head><body>" + text + "</body></html>"
    return text


def audit_links(pages):
    """静态检查：页面里的本地链接是否都能在包内找到。返回问题清单。"""
    problems = []
    keys = set(pages)
    for key, text in pages.items():
        # 只检查真实标签：脚本、样式、注释里出现的示例文字（如 interaction.js 注释里的 data-go="页面.html"）不算链接
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        text = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", text, flags=re.S | re.I)
        text = re.sub(r"<style\b[^>]*>.*?</style\s*>", "", text, flags=re.S | re.I)
        for m in re.finditer(r"""<a\b[^>]*?\shref\s*=\s*(?:"([^"]*)"|'([^']*)')""", text, re.I):
            h = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
            if _is_remote(h) or h.startswith(("javascript", "#")):
                continue
            t = posixpath.normpath(posixpath.join(posixpath.dirname(key), re.split(r"[?#]", h, 1)[0]))
            if t not in keys:
                problems.append(i18n.t(f"{key}：链接 {h} 指向的页面不在包内", f"{key}: the link {h} points to a page that is not in the bundle"))
        for m in re.finditer(r"""<[a-z][^>]*?\sdata-go\s*=\s*(?:"([^"]*)"|'([^']*)')""", text, re.I):
            h = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
            if _is_remote(h):
                continue
            t = posixpath.normpath(posixpath.join(posixpath.dirname(key), re.split(r"[?#]", h, 1)[0]))
            if t not in keys:
                problems.append(i18n.t(f"{key}：data-go {h} 指向的页面不在包内", f"{key}: data-go {h} points to a page that is not in the bundle"))
    return problems


# ───────────────────────── 页面内垫片（每个页面最先执行）与外层文档 ─────────────────────────
_PAGE_SHIM = r"""
(function(){
  var P = window.__PRD_PAGE || {key:'index.html', qs:''};
  var cur = new URL('https://demo.local/' + P.key + (P.qs || ''));
  function go(to, replace){ parent.postMessage({__prd:1, type:'go', to:String(to), replace:!!replace}, '*'); }
  var L = {
    get href(){ return cur.href; }, set href(v){ go(v); },
    get search(){ return cur.search; }, set search(v){ v = String(v); go(v.charAt(0)==='?' ? v : '?' + v); },
    get hash(){ return cur.hash; }, set hash(v){},
    get pathname(){ return cur.pathname; }, set pathname(v){ go(v); },
    get origin(){ return cur.origin; }, get host(){ return cur.host; }, get hostname(){ return cur.hostname; },
    get protocol(){ return cur.protocol; }, get port(){ return cur.port; },
    assign: function(v){ go(v); }, replace: function(v){ go(v, true); }, reload: function(){ go('', true); },
    toString: function(){ return cur.href; }
  };
  var H = {
    back: function(){ parent.postMessage({__prd:1, type:'back'}, '*'); },
    forward: function(){}, go: function(n){ if (Number(n) < 0) H.back(); },
    pushState: function(){}, replaceState: function(){}, length: 1, state: null, scrollRestoration: 'auto'
  };
  window.__PRD_LOC = L;
  window.__PRD_HIST = H;
  window.__PRD_OPEN = function(u, t, f){
    if (/^[a-z][a-z0-9+.-]*:/i.test(String(u)) && !/^https:\/\/demo\.local/i.test(String(u))) return window.open(u, t, f);
    go(u); return null;
  };
  document.addEventListener('click', function(e){
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var h = a.getAttribute('href');
    if (h && /^javascript:/i.test(h)) {
      e.preventDefault();
      var code = h.replace(/^javascript:/i, '');
      try { code = decodeURIComponent(code); } catch (x) {}
      if (/^\s*(?:__PRD_HIST|history)\s*\.\s*(?:back\s*\(\s*\)|go\s*\(\s*-\s*\d+\s*\))\s*;?\s*$/.test(code)) { H.back(); return; }
      if (/^\s*(?:void\s*(?:\(\s*0?\s*\))?)?\s*;?\s*$/.test(code)) return;
      try { (new Function(code))(); } catch (x) {}
      return;
    }
    if (!h || h.charAt(0) === '#' || /^(mailto:|tel:)/i.test(h)) return;
    if (/^[a-z][a-z0-9+.-]*:/i.test(h) && !/^https:\/\/demo\.local/i.test(h)) return;
    e.preventDefault(); go(h);
  }, true);
  document.addEventListener('submit', function(e){ e.preventDefault(); }, true);
})();
"""

_HOST_TEMPLATE = r"""<!DOCTYPE html>
<html lang="__LANG__"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
html,body{margin:0;height:100%;background:#fff;overflow:hidden}
#__prd_frame{position:fixed;left:0;top:0;width:100%;height:100%;border:0;background:#fff}
#__prd_warn{position:fixed;left:0;right:0;top:0;z-index:2147483647;padding:14px 18px;background:#fff7e6;color:#8a5a00;border-bottom:1px solid #ffd591;font:14px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
#__prd_pill{position:fixed;right:6px;top:50%;transform:translateY(-50%);z-index:2147483646;display:flex;flex-direction:column;gap:4px;opacity:.45;transition:opacity .15s}
#__prd_pill:hover,#__prd_pill:focus-within{opacity:1}
#__prd_pill button{width:26px;height:26px;padding:0;border:0;border-radius:13px;background:#1f2329;color:#fff;font:14px/26px sans-serif;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.35)}
#__prd_toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:2147483647;padding:8px 14px;border-radius:6px;background:rgba(31,35,41,.92);color:#fff;font:13px/1.5 sans-serif;display:none}
</style></head>
<body>
<div id="__prd_warn">当前环境没有运行页面里的脚本，点击不会生效。请用浏览器（Chrome / Edge / Safari）打开本文件（远程 IDE 请先把文件下载到本机）。</div>
<iframe id="__prd_frame" title="demo"></iframe>
<div id="__prd_pill"><button id="__prd_back" title="返回上一页" aria-label="返回">‹</button><button id="__prd_home" title="回到导航页" aria-label="导航页">☰</button></div>
<div id="__prd_toast"></div>
<script type="application/json" id="__prd_data">__DATA__</script>
<script>
(function(){
  var warn = document.getElementById('__prd_warn');
  warn.style.display = 'none';
  var PAGES = JSON.parse(document.getElementById('__prd_data').textContent);
  var KEYS = Object.keys(PAGES);
  var START = __START__;
  var frame = document.getElementById('__prd_frame');
  var toastEl = document.getElementById('__prd_toast'), toastT;
  var stack = [], loaded = false;
  var BASE = 'https://demo.local/';
  function toast(t){ toastEl.textContent = t; toastEl.style.display = 'block'; clearTimeout(toastT); toastT = setTimeout(function(){ toastEl.style.display = 'none'; }, 2200); }
  function resolve(to, from){
    var base = new URL(BASE + (from ? from.key + from.qs : START));
    var u = new URL(String(to), base);
    return {external: u.origin !== 'https://demo.local', url: u, key: decodeURIComponent(u.pathname.replace(/^\//, '')), qs: u.search};
  }
  function render(key, qs){
    var mark = '<!--__PRD_PAGE__-->';
    var page = {key: key, qs: qs || ''};
    var inj = '<script>window.__PRD_PAGE=' + JSON.stringify(page).replace(/</g, '\\u003c') + ';<\/script>';
    loaded = false;
    frame.srcdoc = PAGES[key].replace(mark, function(){ return inj; });
    try { history.replaceState(null, '', '#' + key + (qs || '')); } catch (e) {}
  }
  function show(key, qs, replace){
    if (!Object.prototype.hasOwnProperty.call(PAGES, key)) { toast('这个 Demo 里没有页面：' + key); return; }
    if (stack.length && !replace) {
      var last = stack[stack.length - 1];
      if (last.key === key && last.qs === (qs || '')) { render(key, qs); return; }
    }
    if (replace && stack.length) stack[stack.length - 1] = {key: key, qs: qs || ''}; else stack.push({key: key, qs: qs || ''});
    render(key, qs);
  }
  function go(to, replace){
    var cur = stack.length ? stack[stack.length - 1] : null;
    var r = resolve(to, cur);
    if (r.external) { window.open(String(to), '_blank'); return; }
    show(r.key, r.qs, replace);
  }
  function back(){
    if (stack.length > 1) { stack.pop(); var t = stack[stack.length - 1]; render(t.key, t.qs); }
    else toast('已经是第一页了');
  }
  window.addEventListener('message', function(e){
    var d = e.data;
    if (!d || d.__prd !== 1 || e.source !== frame.contentWindow) return;
    if (d.type === 'go') go(d.to, d.replace);
    else if (d.type === 'back') back();
  });
  frame.addEventListener('load', function(){ loaded = true; });
  document.getElementById('__prd_back').onclick = back;
  document.getElementById('__prd_home').onclick = function(){ show(START, '', false); };
  var h = (location.hash || '').replace(/^#/, '');
  var first = {key: START, qs: ''};
  if (h) { try { var r0 = resolve(h, {key: START, qs: ''}); if (!r0.external && PAGES.hasOwnProperty(r0.key)) first = {key: r0.key, qs: r0.qs}; } catch (e) {} }
  show(first.key, first.qs, false);
  setTimeout(function(){
    if (!loaded) { warn.textContent = '页面容器没有加载出来。请用浏览器（Chrome / Edge / Safari）打开本文件（远程 IDE 请先把文件下载到本机）。'; warn.style.display = 'block'; }
  }, 3000);
  function open_(to){ var r = resolve(to, {key: START, qs: ''}); if (r.external) return false; show(r.key, r.qs, false); return true; }
  window.PRDDEMO = {keys: KEYS, go: go, open: open_, back: back, current: function(){ return stack[stack.length - 1]; }, frame: frame, loaded: function(){ return loaded; }};
})();
</script>
</body></html>
"""


def _json_for_script(obj):
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


# ───────────────────────── 构建与自检 ─────────────────────────
def build(proj, out=None):
    from .demo import collect, deliver_name
    proto = proj.proto
    if not (proto / "index.html").exists():
        raise BundleError(i18n.t("prototype/index.html 不存在：先运行 prdkit.py index 生成导航页", "prototype/index.html does not exist: run prdkit.py index to generate the index page first"))
    ctx = _Ctx(proto)
    pages = {}
    for p, rel in collect(proj):
        if not rel.lower().endswith((".html", ".htm")):
            continue
        pages[rel] = process_page(p.read_text(encoding="utf-8"), rel, ctx)
    if not pages:
        raise BundleError(i18n.t("prototype/ 里没有 html 页面", "There are no html pages in prototype/"))
    start = "index.html" if "index.html" in pages else sorted(pages)[0]
    problems = audit_links(pages)
    data = proj.load_screens() if proj.screens_path.exists() else {}
    i18n.set_lang(proj.lang)
    title = f'{data.get("name", proj.name)} {data.get("version", "")} {i18n.t("交互 Demo", "Interactive Demo")}'.strip()
    host = (_HOST_TEMPLATE
            .replace("__TITLE__", htmllib.escape(title))
            .replace("__START__", json.dumps(start))
            .replace("__DATA__", _json_for_script(pages)))
    host = _localize_host(host)
    out = Path(out) if out else proj.root / f"{deliver_name(proj, data)}-demo.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(host, encoding="utf-8")
    return out, len(pages), out.stat().st_size, ctx.warnings + problems


def verify(out_path, screens=None, shot_dir=None):
    """用无头浏览器以 file:// 打开成品，逐个页面状态载入并检查：无脚本报错、页面有内容、外层地址从不离开本文件。
    返回 (问题清单, 访问页面数)；浏览器组件不可用时返回 (None, 0)。"""
    try:
        from playwright.sync_api import sync_playwright
        from . import browser
    except Exception:
        return None, 0
    issues, visited = [], 0
    with sync_playwright() as p:
        try:
            b = browser.launch(p)
        except Exception:
            return None, 0
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        errs, nav = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
        pg.on("framenavigated", lambda f: nav.append(f.url) if f == pg.main_frame else None)
        url = Path(out_path).resolve().as_uri()
        pg.goto(url)
        pg.wait_for_function("window.PRDDEMO && window.PRDDEMO.loaded()", timeout=8000)
        warn_visible = pg.evaluate("getComputedStyle(document.getElementById('__prd_warn')).display !== 'none'")
        if warn_visible:
            issues.append("外层提示未被隐藏（页面脚本没有运行）")
        targets = list(screens or []) or pg.evaluate("window.PRDDEMO.keys")
        for t in targets:
            pg.evaluate("t => window.PRDDEMO.open(t)", t)
            want = pg.evaluate("t => { var u = new URL(t, 'https://demo.local/'); return decodeURIComponent(u.pathname.replace(/^\\//, '')) + u.search; }", t)
            try:
                pg.wait_for_function("window.PRDDEMO.loaded()", timeout=8000)
                pg.wait_for_timeout(120)
                cur = pg.evaluate("(function(){var c = window.PRDDEMO.current(); return c.key + c.qs;})()")
                if cur != want:
                    issues.append(f"{t}：没能切到这个页面（当前停在 {cur}）")
                    continue
                n = pg.evaluate("window.PRDDEMO.frame.contentDocument.body ? window.PRDDEMO.frame.contentDocument.body.innerText.trim().length : -1")
            except Exception as e:
                issues.append(f"{t}：页面没有加载（{type(e).__name__}）")
                continue
            visited += 1
            if n <= 0:
                issues.append(f"{t}：页面加载后没有可见文字")
        if errs:
            issues += [f"脚本报错：{e}" for e in errs[:5]]
        base = url.split("#")[0]
        stray = [u for u in nav if u.split("#")[0] != base]
        if stray:
            issues.append("外层页面发生了跳转（会在 IDE 预览里触发浏览器报错）：" + stray[0])
        ctx.close()
        b.close()
    return issues, visited


_HOST_EN = [('当前环境没有运行页面里的脚本，点击不会生效。请用浏览器（Chrome / Edge / Safari）打开本文件（远程 IDE 请先把文件下载到本机）。', 'Scripts in the page are not running in this environment, so clicks will not work. Open this file in a browser (Chrome / Edge / Safari); for a remote IDE, download the file to your computer first.'), ('title="返回上一页" aria-label="返回"', 'title="Back" aria-label="Back"'), ('title="回到导航页" aria-label="导航页"', 'title="Back to the index" aria-label="Index"'), ('这个 Demo 里没有页面：', 'This demo has no page: '), ('已经是第一页了', 'Already at the first page'), ('页面容器没有加载出来。请用浏览器（Chrome / Edge / Safari）打开本文件（远程 IDE 请先把文件下载到本机）。', 'The page container did not load. Open this file in a browser (Chrome / Edge / Safari); for a remote IDE, download the file to your computer first.')]


def _localize_host(host):
    """英文项目：把宿主页里的少量提示文字换成英文；中文项目原样返回（逐字节不变）。"""
    lang = i18n.cur()
    host = host.replace("__LANG__", "en" if lang == "en" else "zh-CN")
    if lang == "en":
        for zh, en in _HOST_EN:
            host = host.replace(zh, en)
    return host


def cmd_bundle(proj, out=None, do_verify=True):
    i18n.set_lang(proj.lang)
    try:
        path, n, size, warns = build(proj, out)
    except BundleError as e:
        print(f"❌ {e}")
        return 1
    print(i18n.t(f"✅ 已生成单文件 Demo：{path}（{size / 1024:.0f}KB，{n} 个页面）", f"✅ Single-file demo generated: {path} ({size / 1024:.0f}KB, {n} pages)"))
    if size > MAX_WARN:
        print(i18n.t("⚠️  文件超过 20MB，聊天工具可能发不出去；建议精简原型里的大图。", "⚠️  The file is over 20MB and may be too large for chat tools; consider slimming down large images in the prototype."))
    for w in warns[:8]:
        print(f"⚠️  {w}")
    if len(warns) > 8:
        print(i18n.t(f"⚠️  …另有 {len(warns) - 8} 条提醒", f"⚠️  …and {len(warns) - 8} more warning(s)"))
    if do_verify:
        screens = None
        try:
            if proj.screens_path.exists():
                screens = [s["url"] for s in proj.load_screens().get("screens", [])]
        except Exception:
            screens = None
        issues, visited = verify(path, screens)
        if issues is None:
            print(i18n.t("ℹ️  没有可用的浏览器组件，跳过自检（可运行 prdkit doctor 查看）。", "ℹ️  No usable browser component; self-check skipped (run prdkit doctor to see why)."))
        elif issues:
            print(i18n.t("❌ 自检未通过：", "❌ Self-check failed:"))
            for i in issues[:8]:
                print("   · " + i)
            return 1
        else:
            print(i18n.t(f"✅ 自检通过：{visited} 个页面状态逐个载入，无脚本报错，外层从未离开本文件。",
                         f"✅ Self-check passed: {visited} page states loaded one by one, no script errors, the outer document never left this file."))
    print(i18n.t("用法：点路径在 IDE 预览窗打开；发给别人时直接发这一个文件，用浏览器双击打开即可（远程 IDE 需先下载到本机）。",
                 "Usage: click the path to open it in the IDE preview; to share it, send this single file and open it by double-clicking in a browser (for a remote IDE, download it to your computer first)."))
    return 0
