#!/usr/bin/env python3
# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""回归基线：用两个虚构案例跑完整链路，要求全部通过。

  - 邻里借物（移动端，examples/neighbor-lend）：spec → shot → flow → lint，PRD 得分 100
  - 云仓后台（PC 后台，tests/fixtures/admin）：1440 视口截图、流转图、导航页、4 种风格逐一应用并截图
  - 另有：固定风格预览图是否过期、页面地图草案模式、FLOWGEO-05 贴边自检（植入缺陷应被查出）
  - Demo 三态（待发布/在线/本地兜底）的 links 与 lint 一致性、demo 子命令、开源版卫生（无内网痕迹）

用法：python3 tests/regress.py [--keep]
  --keep  保留临时目录，便于人工查看截图与流程图
改过 flow.py / lint.py / shot.py / style.py / 模板样式后必须跑一遍。
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "neighbor-lend"
ADMIN = ROOT / "tests" / "fixtures" / "admin"
PRDKIT = ROOT / "scripts" / "prdkit.py"

failed = []


def run(proj, *args, env=None):
    cmd = [sys.executable, str(PRDKIT), *args] + (["-p", str(proj)] if proj else [])
    e = None
    if env:
        import os
        e = {**os.environ, **env}
    p = subprocess.run(cmd, capture_output=True, text=True, env=e)
    return p.returncode, p.stdout + p.stderr


def check(name, ok, out=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        failed.append(name)
        if out:
            print("\n".join("      " + ln for ln in out.strip().splitlines()[-12:]))



# 植入缺陷：(名称, 期望出现的规则码, 对 PRD 文本的破坏函数)
def _mut_transit_extra(t):
    return t.replace("**流转**：物品列表 关键词无匹配 → **本页**", "**流转**：物品列表 关键词无匹配，或从评价页 → **本页**", 1)


def _mut_transit_missing(t):
    lines, k = t.split("\n"), None
    for i, ln in enumerate(lines):
        if ln.startswith("##### ") and "页面交互说明 — 物品详情" in ln:
            k = i
        elif k is not None and ln.startswith("**流转**"):
            lines[i] = "**流转**：无"
            break
    return "\n".join(lines)


LINT_PLANTS = [
    ("残留模板注释", "L-101", lambda t: t + "\n<!-- AI_INSTRUCTION: x -->\n"),
    ("标题带模板标注", "L-102", lambda t: t.replace("\n## 1. ", "\n## 【必填】1. ", 1)),
    ("HTML img 标签", "L-103", lambda t: t + '\n<img src="images/list.png">\n'),
    ("残留占位符", "L-105", lambda t: t + "\nTODO: 待补充\n"),
    ("图片文件缺失", "L-113", lambda t: t + "\n![x](images/not-exist.png)\n"),
    ("章号断档", "L-206", lambda t: t.replace("\n## 5. 附录", "\n## 7. 附录", 1)),
    ("流转行提到了不相邻页面", "L-412", _mut_transit_extra),
    ("流转行漏写相邻页面", "L-413", _mut_transit_missing),
    ("本机地址", "L-501", lambda t: t + "\n预览：http://localhost:8888/x\n"),
]


def guards(tmp, proj):
    base = tmp / "guard-base"
    shutil.copytree(proj, base)
    prd = next(base.glob("*-prd.md"))
    original = prd.read_text(encoding="utf-8")

    # (1) 预防：flow --transit 生成的流转行草稿，直接替换后必须通过图文一致检查
    code, out = run(base, "flow", "--transit")
    drafts = {}
    cur = None
    for ln in out.splitlines():
        if ln.startswith("##### "):
            cur = ln.split("—", 1)[1].strip()
        elif ln.startswith("**流转**") and cur:
            drafts[cur] = ln
    lines = original.split("\n")
    name = None
    for i, ln in enumerate(lines):
        if ln.startswith("##### ") and "页面交互说明 —" in ln:
            name = ln.split("—", 1)[1].strip()
        elif ln.startswith("**流转**") and name in drafts:
            lines[i] = drafts[name]
            name = None
    prd.write_text("\n".join(lines), encoding="utf-8")
    code, out = run(base, "lint")
    check("预防：flow --transit 草稿替换全部流转行后，lint 无 L-412/L-413", code == 0 and "L-412" not in out and "L-413" not in out and len(drafts) == 9, out)
    prd.write_text(original, encoding="utf-8")

    # (2) 质检有效：逐类植入缺陷，lint 必须报出对应规则码
    for title, code_, mut in LINT_PLANTS:
        g = tmp / "guard-lint"
        shutil.copytree(base, g)
        f = next(g.glob("*-prd.md"))
        before = f.read_text(encoding="utf-8")
        after = mut(before)
        f.write_text(after, encoding="utf-8")
        c, o = run(g, "lint")
        check(f"植入缺陷「{title}」→ lint 报 {code_}", after != before and code_ in o, o)
        shutil.rmtree(g, ignore_errors=True)

    # (3) 缺整体流程图 / 边标签规则：写图阶段就提醒
    g = tmp / "guard-flow"
    shutil.copytree(base, g)
    (g / "spec" / "flows" / "3.0.json").unlink()
    c, o = run(g, "lint")
    check("植入缺陷「缺整体页面流程图」→ lint 报 L-310", "L-310" in o, o)
    fp = g / "spec" / "flows" / "3.1.json"
    d = json.loads(fp.read_text(encoding="utf-8"))
    d["edges"][0]["label"] = "物品列表"
    d["edges"][2]["label"] = "点击某个物品卡片然后进入详情页查看更多信息"
    fp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    c, o = run(g, "spec")
    check("边标签与目标页同名 / 过长 → spec 报 FLOW-025 / FLOW-026", "FLOW-025" in o and "FLOW-026" in o, o)
    shutil.rmtree(g, ignore_errors=True)

    # (4) 流程图：连线穿过节点必须报 FLOWGEO-01（PC 样例里原版端口会触发）
    g = tmp / "guard-geo"
    shutil.copytree(ADMIN, g)
    run(g, "style", "apply", "flat")
    run(g, "shot")
    fp = g / "spec" / "flows" / "4.1.json"
    d = json.loads(fp.read_text(encoding="utf-8"))
    for e in d["edges"]:
        if e["t"] == "dlg":
            e.update({"fs": "b", "ts": "l", "fo": 40})
    fp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    c, o = run(g, "flow", "--check-only")
    check("植入缺陷「连线穿过节点」→ FLOWGEO-01 且退出码非 0", c != 0 and "FLOWGEO-01" in o, o)
    shutil.rmtree(g, ignore_errors=True)

    # (5) 中文字体：模拟没有中文字体的环境，doctor 必须报错，shot 必须拒绝产出
    import re as _re
    import shutil as _sh
    fc = _sh.which("fc-list")
    dejavu = None
    if fc:
        o = subprocess.run([fc, "DejaVu Sans", "file"], capture_output=True, text=True).stdout
        m = _re.search(r"(/[^:\n]+)/DejaVuSans[^/:\n]*\.ttf", o)
        dejavu = m.group(1) if m else None
    if not dejavu:
        print("SKIP  缺中文字体环境模拟：本机找不到 DejaVu 字体目录")
    else:
        conf = tmp / "nocjk.conf"
        conf.write_text(f'<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>{dejavu}</dir><cachedir>{tmp}/fc-cache</cachedir></fontconfig>', encoding="utf-8")
        env = {"FONTCONFIG_FILE": str(conf)}
        c1, o1 = run(None, "doctor", env=env)
        c2, o2 = run(base, "shot", "--only", "list", env=env)
        check("缺中文字体：doctor 报错，shot 拒绝产出（不静默出乱码）", c1 != 0 and "缺字方块" in o1 and c2 != 0 and "缺字方块" in o2, o1 + o2)

    # (6) 风格 CSS 固定彩色扫描：干净通过；植入旧版粉红色块必须被抓出
    c, o = run(None, "style", "check-css")
    check("风格 CSS：彩色全部来自主色变量或允许的固定色", c == 0, o)
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib import style as stylemod
    fake = tmp / "styles-fake"
    shutil.copytree(stylemod.STYLES_DIR, fake, ignore=shutil.ignore_patterns("preview"))
    g_css = fake / "glass.css"
    g_css.write_text(g_css.read_text(encoding="utf-8").replace("body {", "body { background-image: radial-gradient(circle, rgba(255, 170, 150, 0.45), transparent);", 1), encoding="utf-8")
    real = stylemod.STYLES_DIR
    stylemod.STYLES_DIR = fake
    try:
        bad = stylemod.scan_fixed_colors()
    finally:
        stylemod.STYLES_DIR = real
    check("植入缺陷「风格里写死粉红色块」→ 扫描能抓出", any(b[0] == "glass" for b in bad), str(bad))

    # (7) 质量闸门：干净项目全部通过；植入缺陷分级报出；同一错误连续两次未修 → 止损(退出码 3)；修好后通过并清零
    c, o = run(base, "check", "all")
    check("闸门 check all：干净样例逐关通过", c == 0 and "止损" not in o and o.count("✅ 通过") + o.count("✅ 无错误") >= 5, o)
    g = tmp / "guard-gate"
    shutil.copytree(base, g)
    lp = g / "prototype" / "pages" / "list.html"
    lp.write_text(lp.read_text(encoding="utf-8").replace('<div class="nav-bar">', '<div class="nav-bar" style="background:#FF6600">', 1), encoding="utf-8")
    rp = g / "prototype" / "pages" / "review.html"
    rp.write_text(rp.read_text(encoding="utf-8").replace('href="../assets/style.css"', 'href="https://cdn.example.com/x.css"', 1), encoding="utf-8")
    c1, o1 = run(g, "check", "prototype")
    c2, o2 = run(g, "check", "prototype")
    check("闸门 prototype：植入写死色值/外链/缺样式 → 报 PROTO-001/002/003 且分级", c1 == 1 and all(k in o1 for k in ("PROTO-001", "PROTO-002", "PROTO-003", "可直接修复", "需要你判断")), o1)
    check("闸门止损：同一错误连续 2 次未修 → 退出码 3", c2 == 3 and "止损" in o2, o2)
    lp.write_text(lp.read_text(encoding="utf-8").replace(' style="background:#FF6600"', "", 1), encoding="utf-8")
    rp.write_text(rp.read_text(encoding="utf-8").replace('href="https://cdn.example.com/x.css"', 'href="../assets/style.css"', 1), encoding="utf-8")
    c3, o3 = run(g, "check", "prototype")
    check("闸门：修好后重跑通过", c3 == 0 and "✅ 通过" in o3, o3)
    d = json.loads((g / "spec" / "screens.json").read_text(encoding="utf-8"))
    d.pop("style", None)
    (g / "spec" / "screens.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    c4, o4 = run(g, "check", "style")
    check("闸门 style：风格未确认 → 报 STYLE-001", c4 == 1 and "STYLE-001" in o4, o4)
    shutil.rmtree(g, ignore_errors=True)
    shutil.rmtree(base, ignore_errors=True)


def extras(tmp, src):
    """批 3：Demo 三种状态（pending/online/local）、init、SKILL.md 引用、开源版卫生。"""
    import os
    import re

    def setdemo(p, demo):
        f = p / "spec" / "screens.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        if demo is None:
            d.pop("demo", None)
        else:
            d["demo"] = demo
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── links / lint L-51x ──
    p = tmp / "demo-proj"
    shutil.copytree(src, p)
    prd = next(p.glob("*-prd.md"))
    code, out = run(p, "links", "--apply")
    c2, o2 = run(p, "lint")
    check("links --apply（local）后 lint 无 L-51x 问题", code == 0 and "L-51" not in o2, out + o2)
    before = prd.read_text(encoding="utf-8")
    run(p, "links", "--apply")
    check("links --apply 幂等", prd.read_text(encoding="utf-8") == before)
    setdemo(p, {"mode": "online", "url": "https://demo-x-v1-0.example.com"})
    c3, o3 = run(p, "lint")
    check("online 模式但 PRD 仍是本地链接 → lint 报 L-51x", "L-51" in o3, o3)
    run(p, "links", "--apply")
    c4, o4 = run(p, "lint")
    check("切到 online 模式并 links --apply → L-51x 消除", "L-51" not in o4, o4)
    setdemo(p, {"mode": "online", "url": "http://bad.example.com"})
    c5, o5 = run(p, "spec")
    check("spec 校验：online 模式 url 不是 https → SPEC-009", c5 != 0 and "SPEC-009" in o5, o5)
    setdemo(p, {"mode": "weird"})
    c6, o6 = run(p, "spec")
    check("spec 校验：demo.mode 非法 → SPEC-008", c6 != 0 and "SPEC-008" in o6, o6)
    setdemo(p, {"mode": "local"})

    # ── Demo“待发布”（缺省）：发布前不写原型地址，发布后统一回填 ──
    setdemo(p, None)
    c7, o7 = run(p, "links", "--apply")
    t7 = prd.read_text(encoding="utf-8")
    c8, o8 = run(p, "lint")
    check("待发布（缺省）：links --apply 移除全部关联原型行，附录 B 写“发布后补充”，lint 无 L-51x",
          c7 == 0 and "**关联原型**" not in t7 and "在线 Demo 发布后" in t7 and "prototype/pages/" not in t7.split("附录B")[-1] and "L-51" not in o8, o7 + o8)
    c9, o9 = run(p, "links", "--apply")
    check("待发布：links --apply 幂等", "已与 spec 一致" in o9 and prd.read_text(encoding="utf-8") == t7, o9)
    c10, o10 = run(p, "check", "prd")
    check("待发布：check prd 不再提示“还没选 Demo 方式”（DEMO-001 已取消）", "DEMO-001" not in o10, o10)
    sec = t7.split("\n")
    k = next(i for i, ln in enumerate(sec) if ln.startswith("**流转**"))
    sec[k + 1:k + 1] = ["", "**关联原型**：`prototype/pages/list.html`"]
    prd.write_text("\n".join(sec), encoding="utf-8")
    c11, o11 = run(p, "lint")
    check("待发布：手写了关联原型地址 → lint 报 L-515", "L-515" in o11, o11)
    run(p, "links", "--apply")
    check("待发布：links --apply 能清掉手写的地址", "**关联原型**" not in prd.read_text(encoding="utf-8"))
    setdemo(p, {"mode": "online", "url": "https://demo-x-v1-0.example.com"})
    c12, o12 = run(p, "links", "--apply")
    t12 = prd.read_text(encoding="utf-8")
    c13, o13 = run(p, "lint")
    check("待发布 → 在线：links --apply 统一回填在线链接，附录 B 给出在线入口，lint 无 L-51x",
          c12 == 0 and t12.count("**关联原型**：[在线 Demo](https://demo-x-v1-0.example.com/") == 9 and "在线 Demo 入口" in t12 and "L-51" not in o13, o12 + o13)
    c14, o14 = run(p, "demo", "reset")
    c15, o15 = run(p, "links", "--apply")
    check("demo reset：回到待发布，旧站点链接被清掉",
          c14 == 0 and c15 == 0 and "demo-x-v1-0" not in prd.read_text(encoding="utf-8") and "**关联原型**" not in prd.read_text(encoding="utf-8"), o14 + o15)
    setdemo(p, {"mode": "local"})

    # ── demo 本地兜底 / 记录在线地址 / 打包 ──
    bare = tmp / "demo-bare-proj"
    shutil.copytree(EXAMPLE, bare)
    for f in (bare / "prototype" / "index.html", bare / "prototype" / "assets" / "style.css"):
        if f.exists():
            f.unlink()
    code, out = run(bare, "demo", "pack")
    check("demo pack：没有 index.html 时拒绝打包", code != 0 and "index" in out, out)
    run(bare, "index")
    code, out = run(bare, "demo", "pack")
    check("demo pack：没有 style.css 时拒绝打包（避免打出没样式的包）", code != 0 and "style" in out, out)
    run(p, "style", "apply", "flat")
    run(p, "index")
    code, out = run(p, "demo", "local")
    check("demo local：生成 zip", code == 0 and any(p.glob("*-prototype.zip")), out)
    q = tmp / "demo-online-proj"
    shutil.copytree(src, q)
    run(q, "style", "apply", "flat")
    run(q, "index")
    code, out = run(q, "demo", "online", "http://insecure.example.com")
    check("demo online：非 https 地址被拒，spec 不被改动", code != 0 and "https" in out and (json.loads((q / "spec" / "screens.json").read_text(encoding="utf-8")).get("demo") or {}).get("mode") != "online", out)
    code, out = run(q, "demo", "online")
    check("demo online：缺地址被拒（退出码 2）", code == 2, out)
    code, out = run(q, "demo", "online", "https://demo-x-v1-0.example.com/")
    dm = json.loads((q / "spec" / "screens.json").read_text(encoding="utf-8")).get("demo") or {}
    check("demo online：记录 mode=online 与规范化后的地址", code == 0 and dm.get("mode") == "online" and dm.get("url") == "https://demo-x-v1-0.example.com", out)
    code, out = run(q, "demo", "status")
    check("demo status：显示在线站点", code == 0 and "online" in out and "demo-x-v1-0.example.com" in out, out)
    code, out = run(q, "demo", "pack", "--out", str(q / "out" / "x.zip"))
    check("demo pack：打包成功且不含 screenshots/", code == 0 and (q / "out" / "x.zip").exists() and not any(n.startswith("screenshots/") for n in __import__("zipfile").ZipFile(q / "out" / "x.zip").namelist()), out)

    # ── GitHub Pages 发布器（mock，不碰真实 GitHub）──
    sys.path.insert(0, str(ROOT / "tests"))
    from mock_github import MockGitHub, GOOD_TOKEN, LOGIN
    home = tmp / "fakehome"
    home.mkdir(exist_ok=True)
    clean = {"HOME": str(home), "GITHUB_TOKEN": "", "GH_TOKEN": ""}
    g = tmp / "gh-proj"
    shutil.copytree(src, g)
    run(g, "style", "apply", "flat")
    run(g, "index")
    setdemo(g, None)
    name = "gh-proj-v1-0"
    mock = MockGitHub()
    base = mock.start()
    try:
        ok = {**clean, "PRDKIT_GITHUB_API": base, "GITHUB_TOKEN": GOOD_TOKEN}
        bad = {**clean, "PRDKIT_GITHUB_API": base, "GITHUB_TOKEN": "wrong-token-xyz"}
        none = {**clean, "PRDKIT_GITHUB_API": base}
        P = ("publish", "github-pages")

        code, out = run(g, *P, env=ok)
        check("github-pages：没带 --confirm-public → 拒绝并提示“公开”，不联网（退出码 3）",
              code == 3 and "公开" in out and "--confirm-public" in out and not mock.requests, out)
        code, out = run(g, *P, "--dry-run", env=none)
        check("github-pages --dry-run：不联网、无需令牌、不要求确认", code == 0 and not mock.requests, out)
        code, out = run(g, *P, "--confirm-public", env=none)
        check("github-pages 无令牌：退出码 2，提示可改用打包交付，不联网", code == 2 and "GITHUB_TOKEN" in out and "demo local" in out and not mock.requests, out)
        code, out = run(g, *P, "--confirm-public", env=bad)
        check("github-pages 错令牌：401 只请求一次、不重试、输出不含令牌", code != 0 and len(mock.requests) == 1 and "wrong-token-xyz" not in out, out)

        code, out = run(g, *P, "--confirm-public", "--no-wait", env=ok)
        files = mock.branch_files(LOGIN, "prd-demos") if (LOGIN, "prd-demos") in mock.repos else {}
        dm = (json.loads((g / "spec" / "screens.json").read_text(encoding="utf-8")).get("demo") or {})
        check("github-pages 首次：自动创建专用仓库 prd-demos、推到 gh-pages 子目录 <项目名>-<版本>/、含 .nojekyll、开启 Pages",
              code == 0 and mock.repos[(LOGIN, "prd-demos")]["pages"] and ".nojekyll" in files
              and f"{name}/index.html" in files and f"{name}/assets/style.css" in files and not any(k.startswith("screenshots") for k in files), out)
        check("github-pages：记录 spec.demo 为 online（含发布器与仓库），地址为 https://<账号>.github.io/prd-demos/<子目录>/",
              dm.get("mode") == "online" and dm.get("url") == f"https://{LOGIN}.github.io/prd-demos/{name}"
              and dm.get("publisher") == "github-pages" and dm.get("repo") == f"{LOGIN}/prd-demos", json.dumps(dm, ensure_ascii=False))
        check("github-pages：发布后再次提醒公开地址；输出与请求头之外不出现令牌", "公开地址" in out and GOOD_TOKEN not in out, out)
        code, out = run(g, "links", "--apply")
        code2, out2 = run(g, "lint")
        check("github-pages → links --apply：PRD 切到在线链接，lint 无 L-51x", code == 0 and "L-51" not in out2, out + out2)

        n0 = len(mock.requests)
        code, out = run(g, *P, env=ok)
        check("github-pages：公开确认不被记忆，第二次不带 --confirm-public 依然拒绝且不联网", code == 3 and len(mock.requests) == n0, out)
        code, out = run(g, *P, "--confirm-public", "--no-wait", env=ok)
        check("github-pages：同子目录已存在默认拒绝，提示 --update 与换 --path", code != 0 and "--update" in out and "--path" in out, out)

        code, out = run(g, *P, "--confirm-public", "--no-wait", "--path", "demo-b", env=ok)
        files = mock.branch_files(LOGIN, "prd-demos")
        check("灵活性① 同一仓库多个 Demo：换 --path 即多一个子目录，原 Demo 不受影响",
              code == 0 and f"{name}/index.html" in files and "demo-b/index.html" in files, out)

        mock.inject(LOGIN, "prd-demos", f"{name}/stale.html")
        code, out = run(g, *P, "--confirm-public", "--no-wait", "--update", env=ok)
        files = mock.branch_files(LOGIN, "prd-demos")
        check("github-pages --update：只整目录替换自己的子目录（旧文件被清掉），其他 Demo 与 .nojekyll 保留",
              code == 0 and f"{name}/stale.html" not in files and f"{name}/index.html" in files
              and "demo-b/index.html" in files and ".nojekyll" in files, out)

        code, out = run(g, *P, "--confirm-public", "--no-wait", "--repo", f"{LOGIN}/solo-demo", "--path", ".", env=ok)
        files = mock.branch_files(LOGIN, "solo-demo") if (LOGIN, "solo-demo") in mock.repos else {}
        dm = (json.loads((g / "spec" / "screens.json").read_text(encoding="utf-8")).get("demo") or {})
        check("灵活性② 一个 Demo 一个仓库：--repo 自己/某仓库 --path . → 文件在站点根目录，地址无子目录",
              code == 0 and "index.html" in files and not any(k.startswith(name + "/") for k in files)
              and dm.get("url") == f"https://{LOGIN}.github.io/solo-demo", out)

        n0 = len(mock.requests)
        code, out = run(g, *P, "--confirm-public", "--no-wait", "--repo", "someone-else/x", env=ok)
        check("github-pages：别人名下不存在的仓库不会自动创建", code != 0 and "不会自动创建" in out and ("someone-else", "x") not in mock.repos, out)
        for badargs, label in ((["--path", "../x"], "子目录含 .."), (["--path", ".hidden"], "子目录以点开头"), (["--repo", "not a repo"], "仓库名格式不对")):
            n0 = len(mock.requests)
            code, out = run(g, *P, "--confirm-public", *badargs, env=ok)
            check(f"github-pages：非法参数被拒（{label}），不联网", code != 0 and len(mock.requests) == n0, out)
        # ── 令牌无权创建仓库：给出可操作的下一步（建仓链接），而不是笼统让用户去查 Contents / Pages ──
        for deny in (403, 404):
            mock.deny_create = deny
            mock.repos.pop((LOGIN, "no-create-demo"), None)
            n0 = len(mock.requests)
            code, out = run(g, *P, "--confirm-public", "--repo", f"{LOGIN}/no-create-demo", "--no-wait", env=ok)
            check(f"github-pages：创建仓库被拒（{deny}）→ 退出码 1，给出建仓链接与“好了”重试指引，且没有创建任何仓库",
                  code == 1 and "https://github.com/new?name=no-create-demo&visibility=public" in out and "好了" in out
                  and (LOGIN, "no-create-demo") not in mock.repos and len(mock.requests) > n0, out)
            check(f"github-pages：创建仓库被拒（{deny}）→ 不再给“检查 Contents 与 Pages 权限”这句误导提示", "Contents 与 Pages 的读写权限" not in out, out)
            check(f"github-pages：创建仓库被拒（{deny}）→ 并列“仓库没建”与“已建但令牌看不到”两种情形，说明 Repository access、Resource owner 与免费账号私有仓库限制",
                  all(k in out for k in ("A. 仓库还没建", "B. 仓库已经建好", "Repository access", "Resource owner", "免费账号无法为私有仓库开启 Pages")), out)
        ge = tmp / "neighbor-lend-en-pub"                    # 英文项目：语言由项目的 spec.lang 决定（PRDKIT_LANG 只管没有项目的命令）
        shutil.copytree(EXAMPLE_EN, ge)
        for _a in (["style", "apply", "flat"], ["index"]):
            run(ge, *_a)
        code, out = run(ge, *P, "--confirm-public", "--repo", f"{LOGIN}/no-create-demo", "--no-wait", env=ok)
        check("github-pages：创建仓库被拒（英文项目）→ 英文提示含建仓链接与 “Reply \"done\"”，整段输出不含中文",
              code == 1 and "https://github.com/new?name=no-create-demo&visibility=public" in out and 'reply "done"' in out.lower() and not _han(out)
              and all(k in out for k in ("A. The repository does not exist yet", "B. The repository already exists", "Repository access", "Resource owner", "GitHub Free cannot publish Pages from a private repository")), out)
        mock.deny_create = None
        mock.repos.pop((LOGIN, "no-create-demo"), None)
        code, out = run(g, *P, "--confirm-public", "--repo", f"{LOGIN}/no-create-demo", "--no-wait", env=ok)
        check("github-pages：令牌有权限时仍然自动创建仓库（原有行为不变）", code == 0 and (LOGIN, "no-create-demo") in mock.repos, out)
        code, out = run(g, *P, "--confirm-public", env={**ok, "PRDKIT_GITHUB_API": "https://evil.example.com"})
        check("PRDKIT_GITHUB_API 指向非 api.github.com / 回环地址被拒，令牌不泄露", code != 0 and GOOD_TOKEN not in out, out)
        check("github-pages：全程所有请求都带令牌且仅发往 mock（令牌只在请求头）", all(a == "Bearer " + GOOD_TOKEN or "wrong" in a or a == "Bearer " + "wrong-token-xyz" for a in mock.auth_seen))
    finally:
        mock.stop()
    sp = (ROOT / "scripts" / "publishers" / "github_pages.py").read_text(encoding="utf-8")
    check("github-pages 代码级约束：只用标准库、令牌不进 print、只允许 api.github.com/回环、公开确认为必需参数",
          "import requests" not in sp and "subprocess" not in sp and "print(token" not in sp and "print(f\"{token" not in sp
          and "PUBLIC_WARNING" in sp and "if not confirm_public" in sp and "https://api.github.com" in sp)

    # ── init ──
    root = tmp / "init-root"
    root.mkdir()
    code, out = run(None, "init", "demo-app", "--name", "演示", "--platform", "h5", "--root", str(root))
    check("init：建项目骨架", code == 0 and (root / "demo-app" / "spec" / "screens.json").exists(), out)
    code, out = run(None, "init", "Bad Name", "--name", "x", "--platform", "h5", "--root", str(root))
    check("init：非法目录名被拒", code != 0, out)
    code, out = run(None, "init", "demo-app", "--name", "演示", "--platform", "h5", "--root", str(root))
    check("init：已存在项目被拒", code != 0, out)

    # ── SKILL.md 引用的文件、子命令都存在 ──
    skill = _skill_with_msgs()
    miss = [r for r in set(re.findall(r"(?:references|templates|examples)/[\w\-./]+\.\w+", skill)) if not (ROOT / r).exists()]
    miss += [r for r in ("templates/page-desktop.html",) if r in skill and not (ROOT / r).exists()]
    check("SKILL.md 引用的文件都存在", not miss, str(miss))
    cmds = set(re.findall(r"prdkit(?:\.py)? ([a-z]+)", skill))
    code, out = run(None, "--help")
    gone = [c for c in cmds if c not in out]
    check("SKILL.md 提到的 prdkit 子命令都存在", not gone, str(gone))
    fm = skill.split("---")[1] if skill.startswith("---") else ""
    check("SKILL.md frontmatter 保留 name 与触发场景（触发词并入 description，不再有 triggers/disable 顶层字段）",
          "name: prd-generator-oss\n" in fm and all(k in fm for k in ("PRD生成", "写PRD", "修改", "发布Demo", "发布在线Demo", "不适用于"))
          and "\ntriggers:" not in fm and "\ndisable:" not in fm)
    check("SKILL.md 写 PRD 时的图片引用规则保留关键信息：用模板写法、images/ 目录、文件名取 screens.json 的 shot；模板里有完整示例",
          "截图按模板里的图片写法引用" in skill and "`images/`" in skill and "`shot`" in skill
          and "![{页面名}](images/{截图}.png)" in (ROOT / "templates" / "prd-template.md").read_text(encoding="utf-8"))
    pub = (ROOT / "references" / "publish.md").read_text(encoding="utf-8")
    check("Demo 交付用语：SKILL.md / publish.md 都讲“记录在线地址 / 打包交付 / 本地兜底”，核心不要求任何凭证",
          all(t in skill and t in pub for t in ("在线地址", "demo online", "demo local", "https://"))
          and "核心不内置任何托管服务，也不需要任何凭证" in skill and "核心不内置任何托管服务，也不需要任何凭证" in pub)
    check("体验规范：3 个确认点话术、风格图走 view 预览服务 + preview_url、Demo 走 bundle 单文件并在预览窗自动打开、交付给路径、发布菜单一次收齐、缺依赖先征得同意",
          all(k in skill for k in ("第 1 步 · 共 3 步", "第 2 步 · 共 3 步", "第 3 步 · 共 3 步", "preview_url",
                                   "prdkit view --style", "prdkit view --bundle", "prdkit bundle", "prdkit open", "菜单", "一次收齐", "征得同意")))
    check("体验规范：总分结构 + ▶ 确认后预告 + 排版硬规则 + 非必要信息禁止清单 + 不让用户空等 + 不降低产出标准",
          all(k in skill for k in ("总分结构", "▶ 确认后", "排版硬规则", "非必要信息一律不出现", "不让用户空等", "不降低任何一步的产出标准"))
          and "你只需要" not in skill and "10–15 分钟" not in skill)
    # 话术模板排版：代码块内不得用 · / • 串联；相邻的“**① …**”小标题之间必须有空行（IDE 会把相邻行合并成一段）
    bad = []
    for rel in ("SKILL.md", "references/publish.md", "references/revision.md"):
        lines = (ROOT / rel).read_text(encoding="utf-8").split("\n")
        inb = False
        for i, ln in enumerate(lines):
            if ln.strip().startswith("```"):
                inb = not inb
                continue
            if not inb:
                continue
            if re.match(r"^\s*[·•]\s", ln):
                bad.append("%s:%d 用了 · / • 当行首" % (rel, i + 1))
            if re.match(r"^\*\*[①②③④⑤⑥⑦⑧]", ln) and i > 0 and lines[i - 1].strip() and not lines[i - 1].strip().startswith("```"):
                bad.append("%s:%d 小标题与上一行之间没有空行" % (rel, i + 1))
    check("话术模板排版：无 · 行首、相邻小标题之间有空行", not bad, "; ".join(bad))
    # 链接规则：模板里不得有 [文字](地址) 文字链、file:/// 链接、占位地址（IDE 会转成 vscode-resource 虚拟域名，浏览器打不开）
    badlink = []
    for rel in ("SKILL.md", "references/publish.md", "references/revision.md", "references/design-guide.md"):
        lines = (ROOT / rel).read_text(encoding="utf-8").split("\n")
        inb = False
        for i, ln in enumerate(lines):
            if ln.strip().startswith("```"):
                inb = not inb
                continue
            if inb and (re.search(r"\[[^\]]+\]\([^)]*\)", ln) or "file:///" in ln):
                badlink.append("%s:%d %s" % (rel, i + 1, ln.strip()[:40]))
    check("话术模板链接：无 [文字](地址) 文字链和 file:/// 链接（本机文件一律反引号绝对路径）", not badlink, "; ".join(badlink))
    check("链接规则写进了 SKILL.md（反引号路径、禁文字链、原型 Demo 走 http 而非编辑器预览）",
          all(k in skill for k in ("反引号包住的绝对路径", "vscode-resource", "不要让用户用编辑器里的“预览”按钮看原型")))
    check("主色对用户只用颜色描述，不展示色号（色号仅内部使用）",
          "主色：{颜色描述" in skill and "主色{颜色描述" in skill and "主色 {色值}" not in skill and "主色：{色值}" not in skill and "对用户只说颜色，不说色号" in skill)
    # ── 发布包卫生：不得带本机路径、账号、真实页面 ID、内部维护信息（本文件自身除外）──
    pat = re.compile("|".join([
        "/data/" + "workspace", "/data/" + "home", "/Users" + "/", "prd-generator-" + "chun", "纯净" + "版", "纯子" + "版",
        "4017400" + "280", "4018325" + "353", "4054212" + "130", "4017403" + "457",
    ]))
    leaks = []
    for f in ROOT.rglob("*"):
        if (not f.is_file() or "__pycache__" in f.parts or f.suffix in (".png", ".pyc", ".zip") or f.name in ("regress.py", "hash.txt")
                or ".prdkit" in f.parts):
            continue
        try:
            t = f.read_text(encoding="utf-8")
        except Exception:
            continue
        m = pat.search(t)
        if m:
            leaks.append("%s: %s" % (f.relative_to(ROOT), m.group(0)))
    check("发布包卫生：无本机路径 / 真实页面 ID / 内部维护信息", not leaks, "; ".join(leaks))
    internal = re.compile("|".join([
        r"\bwoa\.com", r"\.oa\.com", r"iwiki", r"knot\.", r"cmlliazhang", r"TAI_PAT", r"OA_PAGES", r"tai\.it\.",
        r"mcp\.it\.", r"太湖", r"企微", r"腾讯内网", r"tof 验证", r"\biOA\b", r"mirrors\.cloud\.tencent",
    ]), re.I)
    inleaks = []
    for f in ROOT.rglob("*"):
        if (not f.is_file() or "__pycache__" in f.parts or f.suffix in (".png", ".pyc", ".zip") or f.name in ("regress.py", "hash.txt")
                or ".prdkit" in f.parts):
            continue
        try:
            t = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if f.name == "SKILL.md" and f.parent == ROOT:
            t = t.replace("  author: Tencent (cmlliazhang)\n", "", 1)                 # 署名行：唯一允许出现该账号名的位置
        m = internal.search(t)
        if m:
            inleaks.append("%s: %s" % (f.relative_to(ROOT), m.group(0)))
    check("开源版卫生：无内网域名 / 内网凭证名 / 个人账号 / 内网专有说法", not inleaks, "; ".join(inleaks))
    # ── 开源合规：许可证、版权头、社区文件、品牌示例词 ──
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8") if (ROOT / "LICENSE").exists() else ""
    check("开源合规：LICENSE 含腾讯开源声明头与 MIT 条款全文（法务提供原文），不含 Apache 字样",
          lic.startswith("Tencent is pleased to support the open source community by making")
          and "PRD Generator is licensed under the MIT." in lic and "Permission is hereby granted, free of charge" in lic
          and "THE SOFTWARE IS PROVIDED \"AS IS\"" in lic and "Apache" not in lic)
    miss_files = [n for n in ("NOTICE", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "CHANGELOG.md", ".gitignore", "requirements.txt",
                              ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/bug_report.md") if not (ROOT / n).exists()]
    check("开源合规：社区与工程文件齐全（NOTICE / CONTRIBUTING / SECURITY / CODE_OF_CONDUCT / CHANGELOG / .gitignore / requirements / GitHub 模板）", not miss_files, str(miss_files))
    nohdr = [str(f.relative_to(ROOT)) for f in ROOT.rglob("*.py")
             if "__pycache__" not in f.parts and "Tencent is pleased to support the open source community" not in f.read_text(encoding="utf-8")[:500]]
    check("开源合规：每个 .py 文件都带版权头", not nohdr, "; ".join(nohdr))
    check("开源合规：模板/样式（会被复制进用户产出）不带版权头，避免污染用户文件",
          not any("Tencent is pleased" in f.read_text(encoding="utf-8") for f in (ROOT / "templates").rglob("*") if f.is_file() and f.suffix in (".css", ".js", ".html")))
    brand = [str(f.relative_to(ROOT)) for f in ROOT.rglob("*")
             if f.is_file() and f.suffix in (".md", ".py", ".json", ".html") and f.name != "regress.py" and "__pycache__" not in f.parts
             and any(w in f.read_text(encoding="utf-8") for w in ("腾讯蓝", "联通红"))]
    check("开源合规：示例里不出现具体企业品牌色（腾讯蓝 / 联通红），统一用“品牌蓝 / 品牌红”", not brand, "; ".join(brand))
    check("开源版卫生：内网发布模块已移除（iwiki / pages / connect_mcp / publish_to_iwiki）",
          not any((ROOT / "scripts" / n).exists() for n in ("connect_mcp.py", "publish_to_iwiki.py"))
          and not any((ROOT / "scripts" / "lib" / n).exists() for n in ("iwiki.py", "pages.py")))
    sv = (ROOT / "scripts" / "lib" / "view.py").read_text(encoding="utf-8")
    check("预览服务加固：禁目录列表、空闲自动退出、停服务前确认进程身份",
          all(k in sv for k in ("def list_directory", "IDLE_SECONDS", "_is_ours")))
    # ── 命名与安装方式：安装只保留“复制 prompt”与“下载 zip”两种；不依赖任何内网地址 ──
    readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")        # 中文版文档（README.md 现为英文，另有断言）
    guide_t = (ROOT / "guide.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    guide_en = (ROOT / "guide.en.md").read_text(encoding="utf-8")
    check("命名：SKILL.md 的 name 为 prd-generator-oss，包内不再出现“团队版”", "name: prd-generator-oss\n" in skill and not any("团队版" in t for t in (skill, readme, guide_t)))
    check("安装方式：README 与 guide 都有“复制 prompt”和“下载 zip”两种方式；没有命令行安装方式",
          all("方式一" in t and "方式二" in t and "方式三" not in t for t in (readme, guide_t)))
    check("英文文档：README.md 与 guide.en.md 有 Option 1 / Option 2 两种安装方式（没有 Option 3），且互相链到中文版",
          all("Option 1" in t and "Option 2" in t and "Option 3" not in t for t in (readme_en, guide_en))
          and "README.zh-CN.md" in readme_en and "guide.md" in guide_en and "README.md" in readme and "guide.en.md" in guide_t)
    check("英文安装 prompt：标准包名、不写死某个 AI 工具、不确定目录就问用户、已有目录先备份不覆盖、装完跑 doctor、提醒新开对话",
          all(k in readme_en for k in ("naming the folder exactly prd-generator-oss", "the AI tool you are running in", "ask me first; do not guess", "rename it as a backup",
                                       "do not overwrite or delete it", "scripts/prdkit.py doctor", "open a new chat")))
    check("英文 README 的命令用英文触发词，并说明中文触发词也可用",
          all(k in readme_en for k in ("Write a PRD", "Draft a PRD", "I need a PRD", "Turn these notes into a PRD", "Generate PRD",
                                       "Update the quiz-game PRD", "Publish the demo", "PRD生成", "发布在线Demo")))
    def _first_body_line_ascii(txt):
        if txt.startswith("---\n"):                      # 跳过 front matter
            txt = txt[txt.index("\n---\n", 4) + 5:]
        first = next((l for l in txt.split("\n") if l.strip()), "")
        return not any("\u4e00" <= c <= "\u9fff" for c in first)
    zh_only = [n for n in ("CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", ".github/PULL_REQUEST_TEMPLATE.md",
                           ".github/ISSUE_TEMPLATE/bug_report.md", ".github/ISSUE_TEMPLATE/feature_request.md")
               if not (_first_body_line_ascii((ROOT / n).read_text(encoding="utf-8"))               # 英文在前
                       and sum("\u4e00" <= c <= "\u9fff" for c in (ROOT / n).read_text(encoding="utf-8")) > 20)]   # 中文仍然保留
    check("社区文件为中英双语（英文在前，保留中文）", not zh_only, str(zh_only))
    check("安装 prompt：用标准包名，不写死某个 AI 工具，不确定目录就问用户，已有目录先备份不覆盖，装完跑 doctor",
          all(k in readme for k in ("目录名必须定为 prd-generator-oss", "当前这个 AI 工具", "不确定目录在哪，先问我", "改名备份再放入", "不要直接覆盖或删除", "scripts/prdkit.py doctor", "新开一个对话")))
    # ── 开场：工具巡检 + 需求询问；浏览器优先用已有 Chrome / Edge；安装必须先征得同意 ──
    a, b = skill.index("### 3.1 开场"), skill.index("### 3.2 步骤 1")
    opening = skill[a:b] + "\n" + "\n".join(_msg_blocks("zh")[k] for k in ("M-A", "M-B", "M-C", "M-MANUAL", "M-INSTALLED", "M-E", "M-D"))
    check("开场：分“工具巡检（静默）”和“需求询问”两个模块，并区分带描述与不带描述",
          all(k in opening for k in ("模块一：工具巡检", "模块二：需求询问", "prdkit doctor --brief", "ENV=OK", "模板 A", "模板 B", "模板 C", "模板 D", "模板 E")))
    check("开场：用户回复词为“安装”（不是“装”），也有“先不安装”，并写明没回答就绝不安装、第 2 步前再问一次",
          all(k in opening for k in ("回复“安装”", "先不安装", "绝不安装", "第 2 步之前")) and "回复“装”" not in opening)
    blocks_txt = "\n".join(re.findall(r"```\n(.*?)\n```", opening, flags=re.S))
    bad_words = [w for w in ("pip ", "doctor", "setup", "prdkit", "python3", "--yes") if w in blocks_txt]
    check("开场：用户可见话术模板里不出现内部命令名和安装命令（pip / doctor / setup / prdkit / python3 / --yes）", not bad_words, str(bad_words))
    remind = (opening[opening.index("**模板 B"):opening.index("**用户回复怎么处理**")]
              + "\n" + "\n".join(_msg_blocks("zh")[k] for k in ("M-B", "M-C", "M-MANUAL")))
    check("开场：缺什么直接写名称（Playwright / Chromium / 中文字体 / Python 版本），不再用“一个小组件”这类模糊说法",
          all(k in remind for k in ("Playwright", "Chromium", "Noto Sans CJK", "3.8 及以上")) and "一个小组件" not in opening and "一个浏览器" not in opening)
    check("开场：提醒块里不暴露安装命令；用户主动要命令时才给；仍须先问后装",
          "python3 -m pip" not in remind and "playwright install" not in remind
          and "主动要安装命令" in opening and "用户没要求就不主动给" in opening
          and "不擅自安装，不直接甩命令" in skill and "视为**没同意，绝不安装**" in opening)
    check("开场：只发需求询问的模板 A 与原来的开场内容一致（一字不变）",
          "好的，告诉我你想做什么就行，一两句话即可，例如：" in opening and "说得越具体，我要问你的就越少。缺什么关键信息，我会在下一步一起确认。" in opening)
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib import browser as _br, setup as _su
    check("浏览器选择顺序：Chrome → Edge → 内置 Chromium；PRDKIT_BROWSER 可强制指定",
          _br.order() == ["chrome", "msedge", None])
    os.environ["PRDKIT_BROWSER"] = "chromium"
    forced_ok = _br.order() == [None]
    os.environ["PRDKIT_BROWSER"] = "msedge"
    forced_ok = forced_ok and _br.order() == ["msedge"]
    os.environ.pop("PRDKIT_BROWSER")
    check("PRDKIT_BROWSER 强制指定生效", forced_ok)
    check("安装计划：缺小组件且有 Chrome/Edge → 只装小组件；没有 → 还要下载浏览器；缺浏览器 → 只下载；缺字体/Python 低 → 手动",
          _su.plan_for("NO_PLAYWRIGHT", ["chrome"]) == ["pip"]
          and _su.plan_for("NO_PLAYWRIGHT", []) == ["pip", "browser"]
          and _su.plan_for("NO_BROWSER", []) == ["browser"]
          and _su.plan_for("NO_FONT", []) == ["manual"] and _su.plan_for("OLD_PYTHON", []) == ["manual"]
          and _su.plan_for("OK", []) == [])
    os.environ["PRDKIT_FORCE_STATUS"] = "NO_PLAYWRIGHT"
    code, out = run(None, "doctor", "--brief")
    check("doctor --brief：输出 ENV= 与 SYSTEM_BROWSER= 两行，不通过时退出码 1", code == 1 and "ENV=NO_PLAYWRIGHT" in out and "SYSTEM_BROWSER=" in out, out)
    code, out = run(None, "setup")
    check("setup：不加 --yes 只预演，绝不安装（明确提示未执行任何安装）", code == 0 and "预演" in out and "没有执行任何安装" in out, out)
    os.environ["PRDKIT_FORCE_STATUS"] = "NO_FONT"
    code, out = run(None, "setup", "--yes")
    check("setup：缺中文字体时即使带 --yes 也不自动处理，只给指引（退出码 2）", code == 2 and "fonts-noto-cjk" in out, out)
    os.environ.pop("PRDKIT_FORCE_STATUS")
    pip_src = (ROOT / "scripts" / "lib" / "setup.py").read_text(encoding="utf-8")
    check("setup 安全与提速：不用 sudo、不用 --break-system-packages；默认官方源，镜像仅在环境变量指定且可达时使用；镜像文件不全不用于内置浏览器",
          "sudo" not in pip_src.replace("不使用 sudo", "").replace("不用 sudo", "").replace("要 sudo", "")
          and "--break-system-packages" not in pip_src.replace("不使用 --break-system-packages", "")
          and "_reachable(PIP_MIRROR_PROBE)" in pip_src and "all(_reachable(u)" in pip_src)
    check("每个确认节点都有“▶ 确认后”预告（第 1、2、3 步与交付）", skill.count("▶ 确认后") >= 3 and "▶ 处理后" in skill and "▶ 完成后" in skill)

    # ── view / open：本机预览服务（交互 Demo / 风格对比页）与在编辑器里打开 PRD ──
    vp = tmp / "view-proj"
    shutil.copytree(src, vp)
    if (vp / "prototype" / "index.html").exists():
        (vp / "prototype" / "index.html").unlink()
    code, out = run(vp, "view")
    check("prdkit view：没有 prototype/index.html 时给出明确提示", code == 1 and "prdkit index" in out, out)
    (vp / "prototype").mkdir(exist_ok=True)
    (vp / "prototype" / "index.html").write_text("<html><body><a href='pages/a.html'>去 A</a></body></html>", encoding="utf-8")
    (vp / "prototype" / "pages").mkdir(exist_ok=True)
    (vp / "prototype" / "pages" / "a.html").write_text("<html><body>页面 A 中文</body></html>", encoding="utf-8")
    code, out = run(vp, "view", "--demo")
    m = re.search(r"http://127\.0\.0\.1:(\d+)/prototype/index\.html", out)
    check("prdkit view --demo：返回 Demo 的 127.0.0.1 http 地址与本地文件路径", code == 0 and m and "本地文件" in out, out)
    ok = False
    try:
        import urllib.request as _u
        r = _u.urlopen("http://127.0.0.1:%s/prototype/pages/a.html" % m.group(1), timeout=5)
        ok = r.status == 200 and "charset=utf-8" in r.headers.get("Content-Type", "").lower() and "页面 A 中文" in r.read().decode("utf-8")
    except Exception as e:
        out = str(e)
    check("prdkit view：服务可访问页面，且声明 UTF-8（防止乱码）", ok, out)
    md = next(vp.glob("*-prd.md"))
    try:
        r = _u.urlopen("http://127.0.0.1:%s/%s" % (m.group(1), _u.quote(md.name)), timeout=5)
        ok = "charset=utf-8" in r.headers.get("Content-Type", "").lower()
    except Exception as e:
        ok = False
    check("prdkit view：md 文件也声明 UTF-8", ok)
    code, out = run(vp, "view", "--style")
    check("prdkit view --style：没有风格图时给出明确提示", code == 1 and "style preview" in out, out)
    run(vp, "style", "preview")
    code, out = run(vp, "view", "--style")
    check("prdkit view --style：返回页面地址和图片文件路径", code == 0 and "style-preview/index.html" in out and "图片文件" in out, out)
    code, out = run(vp, "view", "--stop")
    check("prdkit view --stop：关闭预览服务并清理状态", code == 0 and not (vp / ".prdkit" / "view-server.json").exists(), out)
    code, out = run(vp, "open")
    check("prdkit open：环境不支持时静默降级为给路径（不报错），支持时提示已请求打开", code == 0 and md.name in out, out)
    code, out = run(vp, "open", str(vp / "不存在.md"))
    check("prdkit open：文件不存在时报错", code == 1, out)
    code, out = run(None, "--help")
    check("prdkit --help 列出 view / open 子命令", "view" in out and "open" in out, out)

    bundle_tests(tmp, src)


def _px_differs(diff):
    """像素比对：半透明图层合成的取整（<=8）与极少量边缘抗锯齿像素（<0.02%）视为一致；缺文字/图标/色块会是成千上万个像素，必被拦住。"""
    if diff.getbbox() is None:
        return False
    if max(e[1] for e in diff.getextrema()) <= 8:
        return False
    w, h = diff.size
    big = sum(1 for px in diff.convert("L").getdata() if px > 8)
    return big > w * h * 0.0002


def bundle_tests(tmp, src):
    """单文件 Demo（prdkit bundle）：不依赖服务，页面切换在文件内完成，且与原多文件版渲染一致。"""
    import hashlib
    import io
    import re
    import zipfile  # noqa: F401
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib import bundle as bd

    # ── JS 改写（纯函数）──
    rw = bd.rewrite_js
    check("bundle 改写：location.href= / window.location.search / location= / location.assign 全部接管",
          "__PRD_LOC.href='a.html'" in rw("location.href='a.html'") and "__PRD_LOC.search" in rw("var q=new URLSearchParams(window.location.search)")
          and rw("location='b.html'") == "__PRD_LOC.href='b.html'" and "__PRD_LOC.assign(" in rw("document.location.assign('c')"))
    check("bundle 改写：history.back()→__PRD_HIST、window.open(→__PRD_OPEN(", "__PRD_HIST.back()" in rw("history.back()") and "__PRD_OPEN(" in rw("window.open('x')"))
    check("bundle 改写：字符串、注释、其它对象的 .location 属性、relocation 这类词都不被误改",
          rw("var a='my location'; var b=\"location.href\";") == "var a='my location'; var b=\"location.href\";"
          and rw("// location.href=1\nfoo()") == "// location.href=1\nfoo()" and rw("item.location=1; relocation=2") == "item.location=1; relocation=2")
    check("bundle 改写：模板字符串里只改 ${} 内的代码，文字部分原样",
          rw("var t=`go location ${location.search} end`") == "var t=`go location ${__PRD_LOC.search} end`")

    # ── 返回键：skill 自带模板的 javascript:history.back() 必须被接管 ──
    import tempfile as _tf
    _c = bd._Ctx(Path(_tf.mkdtemp(prefix="bk-")))
    _pg = bd.process_page('<html><head></head><body><a class="nav-bar__back" href="javascript:history.back()">x</a>'
                          '<button onclick="history.back()">y</button><a href="javascript:void(0)" onclick="foo()">z</a></body></html>', "pages/a.html", _c)
    check("bundle 改写：href=javascript:history.back() 与 onclick=history.back() 都改为接管版；javascript:void(0) 不动",
          'href="javascript:__PRD_HIST.back()"' in _pg and 'onclick="__PRD_HIST.back()"' in _pg and 'href="javascript:void(0)"' in _pg
          and 'href="javascript:history.back()"' not in _pg)

    # ── 链接审计：只看真实标签，脚本/注释里的示例文字不算 ──
    ok_pages = {"index.html": "<a href='pages/x.html'>x</a>", "pages/x.html": "<!-- data-go=\"页面.html\" --><script>/* <a href=\"nope.html\"> */var s='data-go=\"页面.html\"';</script><body>ok</body>"}
    check("bundle 审计：注释和脚本里的示例文字不误报；真实坏链接必报",
          bd.audit_links(ok_pages) == [] and len(bd.audit_links({**ok_pages, "pages/x.html": "<a href=\"gone.html\">x</a>"})) == 1)

    # ── 构建 ──
    b = tmp / "bundle-proj"
    shutil.copytree(src, b)
    run(b, "style", "apply", "flat")
    run(b, "index")
    code, out = run(b, "bundle")
    demo_files = list(b.glob("*-demo.html"))
    check("bundle：生成单文件 <名称>-<版本>-demo.html，并通过自带的无头浏览器自检", code == 0 and len(demo_files) == 1 and "自检通过" in out, out)
    f = demo_files[0] if demo_files else None
    text = f.read_text(encoding="utf-8") if f else ""
    pages_json = ""
    m = re.search(r'<script type="application/json" id="__prd_data">(.*?)</script>', text, re.S)
    if m:
        pages_json = m.group(1)
    data = json.loads(pages_json) if pages_json else {}
    check("bundle：index 与全部页面都在包内；页面里不再有本地 <link>/<script src>/相对资源引用",
          "index.html" in data and len(data) == 5 and not any(
              re.search(r'<link[^>]+rel=["\']stylesheet', nostyle) or re.search(r'<script[^>]+\ssrc=', nostyle) or '../assets' in nostyle
              for nostyle in (re.sub(r'<style\b.*?</style>', '', v, flags=re.S) for v in data.values())))
    check("bundle：成品里没有任何外部网址依赖（只允许 demo.local 这个内部占位域名）",
          not [u for u in re.findall(r'(?:src|href)=\\?["\']https?://[^"\'\\ ]+', text) if "demo.local" not in u])

    # ── 不改动原型源文件，也不产生其它文件 ──
    def snap(root):
        return hashlib.sha256("".join(f"{q.relative_to(root)}:{hashlib.sha256(q.read_bytes()).hexdigest()};"
                                      for q in sorted((root / "prototype").rglob("*")) if q.is_file()).encode()).hexdigest()
    before = snap(b)
    run(b, "bundle", "--no-verify")
    check("bundle：不改动 prototype/ 源文件（再次打包前后哈希一致）", snap(b) == before)

    # ── 浏览器里的真实行为：从未离开本文件、逐页载入、点击在文件内切页 ──
    from playwright.sync_api import sync_playwright
    from lib import browser as _br
    try:
        from PIL import Image, ImageChops
    except Exception:
        Image = ImageChops = None
    with sync_playwright() as pw:
        brw = _br.launch(pw)
        ctx = brw.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        navs, errs = [], []
        pg.on("framenavigated", lambda fr: navs.append(fr.url) if fr == pg.main_frame else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f.resolve().as_uri())
        pg.wait_for_function("window.PRDDEMO && window.PRDDEMO.loaded()")
        fl = pg.frame_locator("#__prd_frame")
        fl.locator("a.idx-main").first.click()
        pg.wait_for_function("window.PRDDEMO.current().key !== 'index.html'")
        cur = pg.evaluate("window.PRDDEMO.current()")
        check("bundle 点击：导航页点卡片 → 在文件内切到对应页面", cur["key"].startswith("pages/"), str(cur))
        pg.evaluate("window.PRDDEMO.open('pages/list.html?s=empty')")
        pg.wait_for_function("window.PRDDEMO.current().qs === '?s=empty' && window.PRDDEMO.loaded()")
        st = pg.evaluate("window.PRDDEMO.frame.contentWindow.__PRD_LOC.search")
        txt_empty = pg.evaluate("window.PRDDEMO.frame.contentDocument.body.innerText")
        pg.evaluate("window.PRDDEMO.open('pages/list.html')")
        pg.wait_for_function("window.PRDDEMO.current().qs === '' && window.PRDDEMO.loaded()")
        txt_full = pg.evaluate("window.PRDDEMO.frame.contentDocument.body.innerText")
        check("bundle 状态：?s=empty 经伪 location 传入页面，页面按状态渲染（与无状态页内容不同）", st == "?s=empty" and txt_empty != txt_full, f"{st!r}")
        pg.evaluate("window.PRDDEMO.open('index.html')")
        pg.wait_for_function("window.PRDDEMO.current().key === 'index.html' && window.PRDDEMO.loaded()")
        fl.locator("a.idx-main").nth(1).click()
        pg.wait_for_function("window.PRDDEMO.current().key !== 'index.html'")
        pg.click("#__prd_back")
        pg.wait_for_function("window.PRDDEMO.current().key === 'index.html'")
        check("bundle 返回：悬浮的“返回”按钮回到上一页", pg.evaluate("window.PRDDEMO.current().key") == "index.html")
        base = f.resolve().as_uri()
        check("bundle：整个过程外层地址从未离开本文件（IDE 预览里没有可被拦截的导航），页面无脚本报错",
              all(u.split("#")[0] == base for u in navs) and not errs, f"navs={navs} errs={errs}")
        # 与原多文件版逐像素一致（半透明图层合成取整允许 <=8）
        if Image:
            pg.add_style_tag(content="#__prd_pill{display:none!important}")
            po = ctx.new_page()
            bad = []
            for u in ["pages/list.html", "pages/list.html?s=empty", "pages/detail.html", "pages/mine.html"]:
                po.goto((b / "prototype" / u.split("?")[0]).resolve().as_uri() + ("?" + u.split("?", 1)[1] if "?" in u else ""))
                po.wait_for_timeout(300)
                pg.evaluate("t=>window.PRDDEMO.open(t)", u)
                pg.wait_for_function("window.PRDDEMO.loaded()")
                pg.wait_for_timeout(300)
                ia = Image.open(io.BytesIO(po.screenshot(animations="disabled"))).convert("RGB")
                ib = Image.open(io.BytesIO(pg.screenshot(animations="disabled"))).convert("RGB")
                dd = ImageChops.difference(ia, ib)
                if ia.size != ib.size or _px_differs(dd):
                    bad.append(u)
            check("bundle 等价：移动端各页面状态与原多文件版渲染一致", not bad, str(bad))
        ctx.close()
        brw.close()

    # ── 返回键的真实点击（示例原本没有返回键：这里在副本里加上模板自带的写法）──
    k = tmp / "bundle-back"
    shutil.copytree(src, k)
    dp = k / "prototype" / "pages" / "detail.html"
    dp.write_text(re.sub(r"(<body[^>]*>)", r'\1<a class="nav-bar__back" id="bk1" href="javascript:history.back()">‹ 返回</a>'
                         r'<button id="bk2" onclick="history.back()">返回2</button>', dp.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    run(k, "style", "apply", "flat")
    run(k, "index")
    code, out = run(k, "bundle")
    kf = next(k.glob("*-demo.html"), None)
    check("bundle：带返回键的原型打包并自检通过", code == 0 and kf is not None, out)
    if kf:
        with sync_playwright() as pw:
            brw = _br.launch(pw)
            ctx = brw.new_context(viewport={"width": 1280, "height": 900})
            pg = ctx.new_page()
            navs = []
            pg.on("framenavigated", lambda fr: navs.append(fr.url) if fr == pg.main_frame else None)
            pg.goto(kf.resolve().as_uri())
            pg.wait_for_function("window.PRDDEMO && window.PRDDEMO.loaded()")
            cur = lambda: pg.evaluate("window.PRDDEMO.current().key")
            fl = pg.frame_locator("#__prd_frame")
            for sel, label in (("#bk1", "a[href=javascript:history.back()]"), ("#bk2", "button[onclick=history.back()]")):
                pg.evaluate("window.PRDDEMO.open('pages/list.html')")
                pg.wait_for_function("window.PRDDEMO.loaded()")
                pg.evaluate("window.PRDDEMO.open('pages/detail.html')")
                pg.wait_for_function("window.PRDDEMO.current().key === 'pages/detail.html' && window.PRDDEMO.loaded()")
                fl.locator(sel).click()
                pg.wait_for_timeout(500)
                check(f"bundle 返回键（{label}）：点击后回到上一页，外层文档不丢", cur() == "pages/list.html" and pg.evaluate("!!window.PRDDEMO"), cur())
            # 深层直达（栈里只有 1 页）：点返回不能把外层带走
            p2 = ctx.new_page()
            n2 = []
            p2.on("framenavigated", lambda fr: n2.append(fr.url) if fr == p2.main_frame else None)
            p2.goto(kf.resolve().as_uri() + "#pages/detail.html")
            p2.wait_for_function("window.PRDDEMO && window.PRDDEMO.loaded()")
            p2.frame_locator("#__prd_frame").locator("#bk1").click()
            p2.wait_for_timeout(500)
            check("bundle 返回键：直接打开深层页再点返回，停留原页并提示，外层文档不被带走",
                  p2.evaluate("!!window.PRDDEMO") and p2.evaluate("window.PRDDEMO.current().key") == "pages/detail.html"
                  and all(u.split("#")[0] == kf.resolve().as_uri() for u in n2), str(n2))
            ctx.close()
            brw.close()

    # ── PC 后台夹具：1440 宽、弹窗自动打开 ──
    a = tmp / "bundle-admin"
    shutil.copytree(ADMIN, a)
    run(a, "style", "apply", "flat")
    run(a, "index")
    code, out = run(a, "bundle")
    check("bundle：PC 后台夹具（含 ?open= 自动打开弹窗）自检通过", code == 0 and "自检通过" in out, out)
    adm = next(a.glob("*-demo.html"), None)
    if adm and Image:
        with sync_playwright() as pw:
            brw = _br.launch(pw)
            ctx = brw.new_context(viewport={"width": 1440, "height": 900})
            pg, po = ctx.new_page(), ctx.new_page()
            pg.goto(adm.resolve().as_uri())
            pg.wait_for_function("window.PRDDEMO && window.PRDDEMO.loaded()")
            pg.add_style_tag(content="#__prd_pill{display:none!important}")
            bad = []
            for u in ["pages/orders.html", "pages/orders.html?open=%23dlg", "pages/order-detail.html"]:
                po.goto((a / "prototype" / u.split("?")[0]).resolve().as_uri() + ("?" + u.split("?", 1)[1] if "?" in u else ""))
                po.wait_for_timeout(300)
                pg.evaluate("t=>window.PRDDEMO.open(t)", u)
                pg.wait_for_function("window.PRDDEMO.loaded()")
                pg.wait_for_timeout(300)
                ia = Image.open(io.BytesIO(po.screenshot(animations="disabled"))).convert("RGB")
                ib = Image.open(io.BytesIO(pg.screenshot(animations="disabled"))).convert("RGB")
                dd = ImageChops.difference(ia, ib)
                if ia.size != ib.size or _px_differs(dd):
                    bad.append(u)
            check("bundle 等价：PC 后台各页面状态（含自动打开的弹窗）与原多文件版渲染一致", not bad, str(bad))
            ctx.close()
            brw.close()

    # ── 诚实报错，不静默出错 ──
    n = tmp / "bundle-nostyle"
    shutil.copytree(src, n)
    for q in (n / "prototype" / "assets").glob("*"):
        q.unlink()
    run(n, "index")
    code, out = run(n, "bundle", "--no-verify")
    check("bundle：缺样式文件时明确报错并指出页面与文件，不产出残缺 Demo", code == 1 and "找不到样式文件" in out and not list(n.glob("*-demo.html")), out)
    e = tmp / "bundle-esm"
    shutil.copytree(b, e)
    (e / "prototype" / "pages" / "list.html").write_text(
        (e / "prototype" / "pages" / "list.html").read_text(encoding="utf-8").replace("</body>", "<script>import x from './x.js';</script></body>"), encoding="utf-8")
    code, out = run(e, "bundle", "--no-verify")
    check("bundle：页面脚本用了 ES 模块 import 时明确报错（单文件不支持），不静默出错", code == 1 and "import" in out, out)
    code, out = run(b, "bundle", "--out", str(tmp / "bundle-out" / "x.html"), "--no-verify")
    check("bundle --out：可指定输出位置", code == 0 and (tmp / "bundle-out" / "x.html").exists(), out)
    # 自检必须真的会拦：让它去一个不存在的页面
    from lib import bundle as _bd
    iss, _n = _bd.verify(f, ["pages/not-exist.html"])
    check("bundle 自检：目标页面切不过去时必须报问题（防止自检假通过）", iss and any("没能切到" in x for x in iss), str(iss))

    # ── view --bundle：只用于交付时自动打开预览窗 ──
    code, out = run(b, "view", "--bundle")
    mm = re.search(r"预览地址：(http://127\.0\.0\.1:\d+/[^\s]+-demo\.html)", out)
    ok = False
    if mm:
        try:
            import urllib.request as _u
            ok = _u.urlopen(mm.group(1), timeout=5).status == 200
        except Exception:
            ok = False
    check("view --bundle：返回单文件 Demo 的自动打开地址且可访问", code == 0 and ok, out)
    run(b, "view", "--stop")
    nb = tmp / "bundle-none"
    shutil.copytree(src, nb)
    code, out = run(nb, "view", "--bundle")
    check("view --bundle：还没打包时明确提示先运行 bundle", code == 1 and "prdkit bundle" in out, out)
    run(nb, "view", "--stop")

    # ── SKILL.md：交付改为单文件，不再把 http 地址当 Demo 给用户 ──
    skill = _skill_with_msgs()
    _mb = _msg_blocks("zh")
    deliver = skill[skill.index("### 3.7 步骤 8：交付"):skill.index("## 4. 交付后")] + "\n" + _mb["M-DELIVER"]
    check("SKILL.md 交付：Demo 给单文件 demo.html 路径；不再给 http://127.0.0.1 地址和 prototype/index.html 源文件路径",
          "prdkit bundle" in deliver and "-demo.html" in deliver and "http://127.0.0.1:{端口}/prototype/index.html" not in deliver
          and "{项目目录绝对路径}/prototype/index.html" not in deliver and "自检未通过不要交付" in deliver)
    s33 = skill[skill.index("### 3.3 步骤 2：业务流程"):skill.index("### 3.4 步骤 3：视觉风格")] + "\n" + _mb["M-STEP2"]
    s34 = skill[skill.index("### 3.4 步骤 3：视觉风格"):skill.index("### 3.5")] + "\n" + _mb["M-STEP3"]
    check("SKILL.md 第 2 步：明确严禁打开预览窗（不调用 preview_url、不提前加载它）；第 3 步才 ToolSearch + 调用，且不再说“第 2 步已取得参数”",
          "严禁在这一步打开预览窗" in s33 and "不要调用 `preview_url`" in s33 and "取得 `preview_url` 的参数（它是延迟加载工具；只需取一次）" not in s33
          and "ToolSearch" in s34 and "DeferExecuteTool" in s34 and "第 2 步已取得参数" not in s34 and "第 2 步已取得参数" not in skill)
    check("SKILL.md 第 3 步：风格图按能力降级（preview_url → 宿主面板打开工具 → 尖括号文字链），消息模板里 preview_url 成功分支仍给反引号路径，且文字链只作为降级例外",
          "没有该工具（`ToolSearch` 查不到）或调用报错时，按顺序降级" in s34 and "在侧边面板打开本地文件或网页" in s34 and "用尖括号包住" in s34
          and "没看到的话，点下面的路径查看（图片文件）：\n\n`{图片绝对路径}`" in s34 and "唯一例外是 §3.4 第 3 步" in skill
          and "present_files" in s34 and "WorkBuddy" not in s34)
    check("SKILL.md：Demo 不依赖后台服务（view --stop 可随时执行），且保留“不用编辑器预览看多文件原型”的约束",
          "不依赖任何后台服务" in deliver and "不要让用户用编辑器里的“预览”按钮看原型" in skill and "vscode-resource" in skill)


# ───────────────────────── 语言维度（i18n）：中文黄金基线 + 英文端到端 ─────────────────────────
EXAMPLE_EN = ROOT / "examples" / "neighbor-lend-en"
GOLDEN_DIR = ROOT / "tests" / "golden" / "zh"
HAN_RE = None


def _han(text):
    global HAN_RE
    if HAN_RE is None:
        import re
        HAN_RE = re.compile(r"[\u4e00-\u9fff]")
    return HAN_RE.findall(text)


def _golden_collect(tmp):
    """在中文示例上跑一遍确定性命令，返回 ({名称: 规范化文本}, {产物: sha256})。
    黄金基线由“语言维度改造之前”的代码生成（--write-golden），之后任何改动都必须与它逐字一致。"""
    import hashlib
    g = tmp / "golden" / "neighbor-lend"
    shutil.copytree(EXAMPLE, g)
    for args in (["style", "apply", "flat"], ["index"], ["shot"], ["flow"]):
        code, out = run(g, *args)
        if code != 0:
            raise SystemExit(f"黄金基线准备失败：{args}\n{out}")
    texts = {}
    for name, args in [("spec", ["spec"]), ("flow_table", ["flow", "--table"]), ("flow_transit", ["flow", "--transit"]),
                       ("links", ["links"]), ("lint", ["lint"]), ("check_map", ["check", "map"]), ("check_prd", ["check", "prd"]),
                       ("style_list", ["style", "list"])]:
        code, out = run(g, *args)
        texts[name] = out.replace(str(g), "<PROJ>")
    run(g, "bundle", "--no-verify")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    hashes = {
        "prototype/index.html": sha(g / "prototype" / "index.html"),
        "prototype/assets/style.css": sha(g / "prototype" / "assets" / "style.css"),
        "prototype/assets/interaction.js": sha(g / "prototype" / "assets" / "interaction.js"),
        "demo.html": sha(next(g.glob("*-demo.html"))),
    }
    et, eh = _golden_collect_extra(tmp, g)
    texts.update(et)
    hashes.update(eh)
    hashes.update(_template_fingerprints())
    return texts, hashes



# ───────────────────────── 中文黄金基线：补强（由“改造前”代码生成） ─────────────────────────
# 来源：突变测试发现 M3（中文报错文案）、M4（流程图图例）、M5（doctor 结论）三类“悄悄改中文”没被抓到。
# 这里补三类采集：①中文质检/spec/闸门的报错文案 ②流程图渲染页（图里的全部文字）③doctor/setup 的中文提示。


def _plant_zh(proj_dir, tmp, title, mut):
    g = tmp / "golden-plants" / title
    if g.exists():
        shutil.rmtree(g)
    shutil.copytree(proj_dir, g)
    f = next(g.glob("*-prd.md"))
    f.write_text(mut(f.read_text(encoding="utf-8")), encoding="utf-8")
    return g


def _golden_collect_extra(tmp, g):
    """g = 已生成截图/流程图的中文示例项目；返回 (texts, hashes)。所有输出规范化掉临时路径。"""
    import hashlib
    import re
    texts, hashes = {}, {}
    norm = lambda s, p: s.replace(str(p), "<PROJ>")

    # ① 中文 PRD 植入缺陷：整份 lint 输出（含报错文案与修复建议）逐字比对
    plants = [
        ("plant_no_flow_line", lambda t: t.replace("**流转**：", "流转：", 1)),
        ("plant_missing_section", lambda t: t.replace("## 4. 非功能需求", "## 4. 其他", 1)),
        ("plant_todo", lambda t: t + "\nTODO: 补\n{待填}\n"),
        ("plant_localhost", lambda t: t + "\n预览：http://localhost:8888/x\n"),
        ("plant_no_revision", lambda t: t.replace("**修订说明**", "**变更**", 1)),
        ("plant_no_mermaid", lambda t: re.sub(r"(?m)^(\s*)(sequenceDiagram|flowchart\b)", r"\1x-\2", t)),
    ]
    for name, mut in plants:
        pg = _plant_zh(g, tmp, name, mut)
        code, out = run(pg, "lint")
        if "100/100" in out:          # 植入没有触发任何规则 = 这条基线形同虚设，必须在采集时就发现
            raise SystemExit(f"植入缺陷“{name}”没有触发任何质检规则（得分仍为 100），请修正植入方式\n{out}")
        texts[name] = norm(out, pg)
    # spec 报错：登记了不存在的页面文件 / 非法 platform / 重复 id
    sp = tmp / "golden-badspec"
    if sp.exists():
        shutil.rmtree(sp)
    shutil.copytree(g, sp)
    sj = sp / "spec" / "screens.json"
    d = json.loads(sj.read_text(encoding="utf-8"))
    d["platform"] = "tv"
    d["screens"][0]["url"] = "pages/not-exist.html"
    d["screens"].append(dict(d["screens"][1], url=d["screens"][1]["url"]))
    sj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    code, out = run(sp, "spec")
    texts["badspec_spec"] = norm(out, sp)
    for gate in ("map", "style", "prototype"):
        code, out = run(sp, "check", gate)
        texts[f"badspec_check_{gate}"] = norm(out, sp)
    # 闸门提示：没确认风格 / 没有 style.css
    ns = tmp / "golden-nostyle"
    if ns.exists():
        shutil.rmtree(ns)
    shutil.copytree(EXAMPLE, ns)
    d = json.loads((ns / "spec" / "screens.json").read_text(encoding="utf-8"))
    d.pop("style", None)
    (ns / "spec" / "screens.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    code, out = run(ns, "check", "style")
    texts["nostyle_check_style"] = norm(out, ns)

    # ② 流程图渲染页：图里的全部文字（图例/徽章/标题/连线标签）都在这里面
    for f in sorted((g / ".prdkit").glob("flow-*.html")):
        hashes[f"flow-render/{f.name}"] = hashlib.sha256(f.read_bytes()).hexdigest()

    # ③ doctor / setup 的中文提示：打桩成固定环境，输出与机器无关
    sys.path.insert(0, str(ROOT / "scripts"))
    import io as _io
    import os
    import contextlib
    from lib import doctor as _doc
    saved = (_doc._check_python, _doc._check_playwright, _doc._check_cjk_font, _doc._check_writable, _doc.get_secret, _doc.count_secret_definitions)
    import re as _re
    _norm_doc = lambda t: _re.sub(r"平台：\S+", "平台：<OS>", t.replace(str(tmp), "<WS>").replace(str(ROOT), "<SKILL>"))
    try:
        _doc.count_secret_definitions = lambda v: {}
        _doc._check_python = lambda: (_doc.OK, "Python 3.11.0", None, True)
        _doc._check_playwright = lambda: (_doc.OK, "页面截图组件可用（使用 Chrome）", None, True)
        _doc._check_cjk_font = lambda: (_doc.OK, "Chromium 中文渲染正常", None, True)
        _doc._check_writable = lambda p: True
        for label, token in (("doctor_ok", "x"), ("doctor_notoken", "")):
            _doc.get_secret = lambda v, _t=token: ((_t, "环境变量") if _t else (None, None))
            buf = _io.StringIO()
            with contextlib.redirect_stdout(buf):
                _doc.run(str(tmp))
            texts[label] = _norm_doc(buf.getvalue())
        _doc._check_python = lambda: (_doc.BAD, "Python 3.6", "需要 Python 3.8 及以上", True)
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            _doc.run(str(tmp))
        texts["doctor_blocked"] = _norm_doc(buf.getvalue())
    finally:
        (_doc._check_python, _doc._check_playwright, _doc._check_cjk_font, _doc._check_writable, _doc.get_secret, _doc.count_secret_definitions) = saved
    # NO_PLAYWRIGHT / NO_BROWSER 的预演文案会随本机是否装有 Chrome/Edge 而不同，不放进与机器无关的基线
    for st in ("NO_FONT", "OLD_PYTHON", "OK"):
        os.environ["PRDKIT_FORCE_STATUS"] = st
        code, out = run(None, "setup")
        texts[f"setup_{st.lower()}"] = out
    os.environ.pop("PRDKIT_FORCE_STATUS", None)
    return texts, hashes


def _template_fingerprints():
    """中文 PRD 模板 / 页面骨架 / 风格 CSS 等“随包文件”的 sha256：悄悄改一个字也会被发现。"""
    import hashlib
    out = {}
    for rel in ("templates/prd-template.md", "templates/page-mobile.html", "templates/page-desktop.html",
                "templates/prototype-style.css", "templates/interaction.js"):
        out["tpl/" + rel] = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    for f in sorted((ROOT / "templates" / "styles").glob("*.css")):
        out["tpl/templates/styles/" + f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def write_golden(out_dir):
    tmp = Path(tempfile.mkdtemp(prefix="prdkit-golden-"))
    texts, hashes = _golden_collect(tmp)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, txt in texts.items():
        (out_dir / f"{name}.txt").write_text(txt, encoding="utf-8")
    (out_dir / "hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"黄金基线已写入 {out_dir}（{len(texts)} 个文本 + {len(hashes)} 个产物指纹）")


def i18n_tests(tmp):
    import hashlib
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib import i18n

    # ── 纯函数：语言归一、词表、取值 ──
    check("i18n：语言归一（zh/en 及常见写法），不认识的返回 None，缺省 zh",
          i18n.normalize("EN") == "en" and i18n.normalize("zh-CN") == "zh" and i18n.normalize("") == "zh"
          and i18n.normalize("fr") is None and i18n.lang_of({}) == "zh" and i18n.lang_of({"lang": "en"}) == "en")
    zh = i18n.WORDS["zh"]
    check("i18n：中文词表与历史写死的字面量逐字一致（结构识别词不得悄悄改动）",
          zh["sec_page"] == "页面交互说明" and zh["transit_prefix"] == "**流转**：" and zh["rel_prefix"] == "**关联原型**："
          and zh["page_list"] == "页面清单" and zh["pending_mark"] == "在线 Demo 发布后" and zh["local_mark"] == "未发布在线 Demo"
          and zh["module_parts"] == ["功能描述", "业务规则", "页面交互说明", "数据字段", "异常处理"]
          and zh["top_required"] == [("项目背景", "背景"), ("产品概述", "概述"), ("产品功能", "功能说明"), ("非功能需求", "非功能")]
          and zh["table_head"] == "| 页面/弹窗 | 章节 | 类型 | 进入方式 | 去向 |")
    check("i18n：两种语言的词表键完全一致（加了一边必须加另一边）", set(i18n.WORDS["zh"]) == set(i18n.WORDS["en"]))
    i18n.set_lang("en")
    from lib import fontcheck
    ok_font, msg_font = fontcheck.has_cjk_font()
    i18n.set_lang("zh")
    check("fontcheck：英文项目不要求中文字体（不起浏览器直接放行）", ok_font is True and "not required" in msg_font, msg_font)
    zh_spec = json.loads((EXAMPLE / "spec" / "screens.json").read_text(encoding="utf-8"))
    check("中文示例的 spec 不带 lang 字段（缺省 zh，旧项目格式不变）", "lang" not in zh_spec)

    # ── 中文黄金基线：与“改造之前”的输出逐字一致 ──
    texts, hashes = _golden_collect(tmp)
    for name, txt in texts.items():
        gf = GOLDEN_DIR / f"{name}.txt"
        want = gf.read_text(encoding="utf-8") if gf.exists() else None
        check(f"中文黄金基线：{name} 输出与改造前逐字一致", want is not None and txt == want,
              "" if want is not None else f"缺少 {gf}")
    gh = GOLDEN_DIR / "hashes.json"
    want_h = json.loads(gh.read_text(encoding="utf-8")) if gh.exists() else {}
    for k, v in hashes.items():
        check(f"中文黄金基线：{k} 与改造前逐字节一致（sha256）", want_h.get(k) == v, f"{k}: {v[:12]} != {str(want_h.get(k))[:12]}")

    # ── init：--lang ──
    root = tmp / "init-root"
    run(None, "init", "demo-en", "--name", "Demo", "--platform", "h5", "--lang", "en", "--root", str(root))
    run(None, "init", "demo-zh", "--name", "演示", "--platform", "h5", "--root", str(root))
    s_en = json.loads((root / "demo-en" / "spec" / "screens.json").read_text(encoding="utf-8"))
    s_zh = json.loads((root / "demo-zh" / "spec" / "screens.json").read_text(encoding="utf-8"))
    check("init --lang en 写入 spec.lang；不带 --lang 的中文项目 spec 不含 lang", s_en.get("lang") == "en" and "lang" not in s_zh)
    bad = tmp / "bad-lang"
    shutil.copytree(EXAMPLE_EN, bad)
    sp = bad / "spec" / "screens.json"
    d = json.loads(sp.read_text(encoding="utf-8"))
    d["lang"] = "fr"
    sp.write_text(json.dumps(d), encoding="utf-8")
    code, out = run(bad, "spec")
    check("spec.lang 写成不支持的语言 → SPEC-021 报错", "SPEC-021" in out, out)

    # ── 英文示例：端到端 ──
    en = tmp / "neighbor-lend-en"
    shutil.copytree(EXAMPLE_EN, en)
    for name, args in [("英文 style apply", ["style", "apply", "flat"]), ("英文 index", ["index"]), ("英文 shot", ["shot"]), ("英文 flow", ["flow"])]:
        code, out = run(en, *args)
        check(name, code == 0, out)
    code, out = run(en, "spec")
    check("英文 spec 校验：退出码 0，输出（含汇总行）不含中文", code == 0 and "0 errors" in out and not _han(out), "".join(_han(out))[:30] or out)
    code, out = run(en, "lint")
    check("英文 PRD lint 100/100（章节/页面小节/Flow 行/附录 B 全部按英文词表识别）", code == 0 and "100/100" in out, out)
    check("英文 lint 输出不含中文", not _han(out), "".join(_han(out))[:30])
    for name, args in [("flow --table", ["flow", "--table"]), ("flow --transit", ["flow", "--transit"]), ("links", ["links"]),
                       ("style list", ["style", "list"])]:
        code, out = run(en, *args)
        check(f"英文 {name}：执行成功且输出不含中文", code == 0 and not _han(out), "".join(_han(out))[:30] or out)
    code, out = run(en, "flow", "--table")
    check("英文页面清单表头与类型用英文词表", "| Page / Popup | Section | Type | Entry | Exit |" in out and "Page state" in out and "(other chapter)" in out, out)
    code, out = run(en, "flow", "--transit")
    check("英文 Flow 行草稿以 **Flow**: 开头并含 **This page**", "**Flow**: " in out and "**This page**" in out and "##### 3.1.3.1 Page Interaction — Item list" in out, out)

    # 产物里不得有中文：导航页 / 单文件 Demo / 流程图页面 / 风格 CSS 注释
    code, out = run(en, "bundle")
    demo = next(en.glob("*-demo.html"), None)
    dtxt = demo.read_text(encoding="utf-8") if demo else ""
    check("英文 bundle：自检通过，宿主页提示与标题为英文（lang=en），文件内不含中文", code == 0 and demo is not None and not _han(dtxt)
          and '<html lang="en">' in dtxt and "Interactive Demo" in dtxt and "Back to the index" in dtxt, out + "".join(_han(dtxt))[:30])
    itxt = (en / "prototype" / "index.html").read_text(encoding="utf-8")
    check("英文导航页：lang=en，标题与副标题为英文，不含中文", '<html lang="en">' in itxt and "Prototype index" in itxt and not _han(itxt), "".join(_han(itxt))[:30])
    css = (en / "prototype" / "assets" / "style.css").read_text(encoding="utf-8")
    check("英文 style.css 的风格注释为英文；中文项目保持“风格：flat（扁平）”", "/* ===== Style: flat (Flat) ===== */" in css
          and "/* ===== 风格：flat（扁平） ===== */" in (tmp / "neighbor-lend" / "prototype" / "assets" / "style.css").read_text(encoding="utf-8"))
    flow_htmls = sorted((en / ".prdkit").glob("flow-*.html"))
    ftxt = "".join(f.read_text(encoding="utf-8") for f in flow_htmls)
    check("英文流程图渲染页（即图里的全部文字）：图例/徽章/标题全为英文，无中文", len(flow_htmls) == 3 and "Normal transition" in ftxt
          and "Popup" in ftxt and not _han(ftxt), "".join(_han(ftxt))[:30])
    check("英文截图与流程图都已生成", all((en / "images" / f).exists() for f in ("list.png", "borrow-sheet.png", "flow-3-0.png", "flow-3-1.png", "flow-3-2.png")))

    # ── 英文 PRD：植入缺陷必须被查出（质检在英文下同样有效） ──
    base = en
    prd = next(base.glob("*-prd.md"))
    original = prd.read_text(encoding="utf-8")
    flow_line = 'Item list: Tap an item card → **This page** → Tap "Request to borrow": opens "Request popup"'
    plants = [
        ("缺少“Flow”首行", "L-410", lambda t: t.replace("**Flow**: " + flow_line, "Item detail flow omitted", 1)),
        ("页面清单漏写页面", "L-324", lambda t: "\n".join(l for l in t.split("\n") if not l.startswith("| Request sent | 3.1.3.5"))),
        ("缺少必填章节（非功能需求）", "L-201", lambda t: t.replace("## 4. Non-functional Requirements", "## 4. Other", 1)),
        ("Flow 行提到了不相邻页面", "L-412", lambda t: t.replace("**Flow**: " + flow_line, "**Flow**: " + flow_line + "; also from Review done", 1)),
        ("Flow 行漏写相邻页面", "L-413", lambda t: t.replace("; Bottom tab \"My loans\": goes to \"My loans\"", "", 1)),
        ("残留占位符", "L-105", lambda t: t + "\nTODO: fill in\n"),
        ("本机地址", "L-501", lambda t: t + "\nPreview: http://localhost:8888/x\n"),
        ("缺少修订说明", "L-204", lambda t: t.replace("**Revision Notes**", "**Changes**", 1)),
    ]
    for title, code_, mut in plants:
        g = tmp / "guard-en"
        if g.exists():
            shutil.rmtree(g)
        shutil.copytree(base, g)
        f = next(g.glob("*-prd.md"))
        before = f.read_text(encoding="utf-8")
        after = mut(before)
        f.write_text(after, encoding="utf-8")
        code, out = run(g, "lint")
        check(f"英文质检有效：植入“{title}”→ 报 {code_}（且植入确实改动了文本）", after != before and code_ in out, out)
    prd.write_text(original, encoding="utf-8")



def _msg_blocks(lang="zh"):
    """解析 references/messages.<lang>.md，返回 {块id: 块文本}。话术已从 SKILL.md 搬到这里（见阶段 C）。"""
    import re
    t = (ROOT / "references" / f"messages.{lang}.md").read_text(encoding="utf-8")
    # 外层围栏可以是 3 个或 4 个反引号（块里自带代码块时外层用 4 个）；用反向引用保证开闭围栏长度一致
    return {m.group(1): m.group(3) for m in re.finditer(r"(?m)^## (M-[A-Z0-9]+)[^\n]*\n\n(`{3,4})\n(.*?)\n\2$", t, re.S)}


def _skill_with_msgs():
    """SKILL.md + 中文话术文件：现有断言读“并集”，保证话术仍然完整可查。"""
    return (ROOT / "SKILL.md").read_text(encoding="utf-8") + "\n" + (ROOT / "references" / "messages.zh.md").read_text(encoding="utf-8")



# ───────────────────────── 阶段 C：SKILL.md 话术外置 + 语言路由 ─────────────────────────
# 中文黄金基线：tests/golden/zh/skill_blocks.json（16 个话术块，逐字取自搬家前的 SKILL.md）
#               tests/golden/zh/skill_rest.txt     （搬家前的 SKILL.md，话术块位置换成 @@BLOCK:id@@ 标记）
# 允许的改动只有：①这里列出的被替换的原行 ②纯新增行（语言路由、英文触发词行、--lang en 一行）。其它任何删改都会被发现。
_ALLOWED_REPLACED = {"8. 文件操作用绝对路径；文档 UTF-8；输出简体中文。",
                     "name: prd-generator",                                              # 开源包名改为 prd-generator-oss
                     "  # TODO(开源发布前确定)：author、license 署名；未定之前不要对外发布",   # 署名已定，TODO 已清
                     "# PRD Generator — AI 执行指令（V5.2）",                             # 开源首发版本号 1.0.0

                     'description: Turn a one-line product requirement into a complete PRD, a clickable HTML prototype, page-flow diagrams and automated quality checks. Use when the user asks to generate, write, revise or update a PRD, or to package / host the demo. Not for weekly reports, slide decks or technical design docs. 从一句话需求生成 PRD 文档 + 可点击原型 + 流程图 + 质量自检。当用户要求 PRD生成、生成PRD、写PRD、修改PRD、调整PRD、更新PRD、发布Demo、发布在线Demo 时使用；不适用于周报、汇报PPT、技术方案等非产品需求类文档。'}     # description：英文触发场景放宽（中文部分另有断言保证不变）
_POINTER_RE = None


def _skill_normalized_lines():
    """把 SKILL.md 里的话术指针还原成 @@BLOCK:id@@，用于和黄金基线比对。返回 (行列表, 指针id列表)。"""
    import re
    global _POINTER_RE
    if _POINTER_RE is None:
        _POINTER_RE = re.compile(r"^> 📨 \*\*话术块 (M-[A-Z0-9]+)\*\*")
    out, ids = [], []
    for l in (ROOT / "SKILL.md").read_text(encoding="utf-8").split("\n"):
        m = _POINTER_RE.match(l)
        if m:
            ids.append(m.group(1))
            out.append(f"@@BLOCK:{m.group(1)}@@")
        else:
            out.append(l)
    return out, ids


def skill_lang_tests():
    import difflib
    import re
    gold = json.loads((GOLDEN_DIR / "skill_blocks.json").read_text(encoding="utf-8"))
    rest = (GOLDEN_DIR / "skill_rest.txt").read_text(encoding="utf-8").split("\n")
    zh = _msg_blocks("zh")
    en = _msg_blocks("en")

    # ── 中文话术：逐字不变 ──
    check("话术外置：messages.zh.md 有 16 个块，id 与顺序同搬家前一致", list(zh) == gold["order"] and len(zh) == 16, str(list(zh)))
    diff_ids = [k for k in gold["order"] if zh.get(k) != gold["blocks"][k]]
    check("话术外置：中文 16 个话术块与搬家前的 SKILL.md 逐字一致（一字不差）", not diff_ids, str(diff_ids))
    norm, ids = _skill_normalized_lines()
    check("话术外置：SKILL.md 里每个话术块恰好一个指针，顺序与搬家前一致", ids == gold["order"], str(ids))
    sm = difflib.SequenceMatcher(None, rest, norm, autojunk=False)
    bad = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("delete", "replace"):
            removed = [l for l in rest[i1:i2] if l.strip()]
            # replace 的右侧可以是“被允许替换的原行 + 新增的段落”，所以只检查左侧（原有的行）是否都在白名单里
            if any(l not in _ALLOWED_REPLACED for l in removed):
                bad.append(removed[:2])
    check("话术外置：除白名单里的 1 行外，中文 SKILL.md 的其余指令一行未删未改（只有新增）", not bad, str(bad))
    check("话术外置：SKILL.md 不再内嵌这 16 个话术块（防止两处各改各的）",
          all(gold["blocks"][k].split("\n")[0] not in (ROOT / "SKILL.md").read_text(encoding="utf-8") for k in ("M-STEP1", "M-STEP2", "M-STEP3", "M-DELIVER", "M-A")))

    # ── 英文话术：与中文一一对应 ──
    check("英文话术：messages.en.md 的块 id、顺序与中文版完全一致", list(en) == list(zh), str(list(en)))
    ph = lambda t: len(re.findall(r"\{", t))
    check("英文话术：每个块的花括号占位符个数与中文版一致（不丢占位符）", all(ph(en[k]) == ph(zh[k]) for k in zh),
          str([k for k in zh if ph(en[k]) != ph(zh[k])]))
    en_text = (ROOT / "references" / "messages.en.md").read_text(encoding="utf-8")
    import unicodedata
    cjk = [c for c in en_text if "\u3000" <= c <= "\u303f" or "\uff00" <= c <= "\uffef" or "\u4e00" <= c <= "\u9fff"]     # 汉字 + CJK 标点 + 全角字符
    check("英文话术：messages.en.md 不含任何汉字或 CJK/全角标点（用户不会在英文对话里看到中文）", not cjk, "".join(cjk)[:20])
    check("英文话术：三个确认点标题、“👉 请你”、“▶ 确认后”结构齐全",
          all(f"[Step {n} of 3]" in en[f"M-STEP{n}"] for n in (1, 2, 3))
          and all("👉" in en[k] for k in ("M-STEP1", "M-STEP2", "M-STEP3", "M-B", "M-C"))
          and all("▶ After you confirm" in en[k] for k in ("M-STEP1", "M-STEP2")) and "▶ When done" in en["M-STEP3"])
    check("英文话术：交付菜单 4 项齐全，回复词为 install / not now / confirm public / package",
          all(f"- {n} " in en["M-DELIVER"] for n in (1, 2, 3, 4)) and "confirm public" in en["M-PUBLIC"] and '"package"' in en["M-PUBLIC"]
          and all(w in en_text for w in ('"install"', '"not now"', '"guide"', '"done"')))
    check("英文话术：安装命令只在用户索取时给（提醒块里不出现命令名），且英文用 prdkit --lang en setup",
          not any(w in en[k] for k in ("M-B", "M-C", "M-MANUAL") for w in ("pip ", "prdkit", "python3", "--yes")) and "prdkit --lang en setup --yes" in en_text)
    check("英文话术：非块内容（检测行取值表、回复对照、降级话术、待确认标记）齐全，且与引擎的 PEND-001 标记一致",
          all(k in en_text for k in ("## S-LINES", "## S-REPLY", "## S-DELIVERY-REPLY", "## S-FALLBACK", "## S-PENDING")) and "[TBC" in en_text)
    check("英文话术：风格名与引擎一致（Flat / Glass / Soft / Dark）",
          all(w in en["M-STEP3"] for w in ("Flat", "Glass", "Soft", "Dark")))

    # ── 覆盖性：SKILL.md 里每一句“对用户说的整句话”（块外的短句），英文话术里都要有对应项 ──
    sk0 = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    inline = []
    for ln in sk0.split("\n"):
        if ln.startswith("> 📨"):
            continue
        for m in re.finditer(r"`([^`\n]+)`", ln):
            t = m.group(1)
            if sum("\u4e00" <= c <= "\u9fff" for c in t) >= 8 and t.strip().endswith("。") and not t.startswith("prdkit"):
                inline.append(t)
    EN_OF = {      # 中文整句 → 英文话术里必须出现的对应英文片段
        "收到，先帮你装好截图组件（约 1 分钟）。": "Got it, installing the screenshot component first (about 1 minute).",
        "接下来画流程图需要先装截图组件，回复“安装”即可（约 1 分钟）。": "To draw the flow diagram next I need the screenshot component first; reply \"install\" and it takes about 1 minute.",
        "装好了，接下来告诉我你想做什么就行，一两句话即可。": "All set, now tell me what you want to build, one or two sentences is enough.",
        "那我先帮你整理需求理解。": "Then I will organise the requirement understanding first.",
        "版本策略：另存为新版本 {名}-v{n}，旧版保留。": "Version strategy: save as a new version {name}-v{n}, the old one is kept.",
        "好的，文件留在本地。之后想处理 Demo，随时说「发布在线Demo」。": "Okay, the files stay local. To handle the demo later, say \"publish the demo\" any time.",
    }
    check("英文话术覆盖：SKILL.md 里每句块外的对用户短句都有英文对应（新增中文短句而没补英文会失败）",
          inline and all(t in EN_OF and EN_OF[t] in en_text for t in inline) and len(inline) == len(EN_OF),
          str([t for t in inline if t not in EN_OF or EN_OF[t] not in en_text]) + f" found={len(inline)} mapped={len(EN_OF)}")

    # ── GitHub 令牌指引：先建仓库再建令牌；命令一律代码块 ──
    pub = (ROOT / "references" / "publish.md").read_text(encoding="utf-8")
    _i0 = pub.find("### 申请 GitHub 令牌")
    sec_t = pub[_i0:] if _i0 >= 0 else ""
    def _order(txt, *marks):                      # 按顺序都能找到才为真；找不到就是 False（记为失败，而不是让整个回归崩溃）
        pos = [txt.find(m) for m in marks]
        return all(x >= 0 for x in pos) and pos == sorted(pos)
    check("令牌指引（中文）：顺序为 先建仓库 → 建令牌 → 配置命令 → 回复“好了”，建仓与建令牌都带直达链接",
          _order(sec_t, "第 1 步", "第 2 步", "第 3 步", "第 4 步")
          and "https://github.com/new?name=prd-demos&visibility=public" in sec_t and "https://github.com/settings/personal-access-tokens/new" in sec_t)
    check("令牌指引（中文）：仓库范围只授权 prd-demos；不再要求 All repositories，也不再写未核实的“账号级 Administration”",
          "只授权 `prd-demos` 这一个仓库" in sec_t and "All repositories" not in sec_t.replace("不要求选 All repositories", "")
          and "Account permissions" not in sec_t and "未核实" in sec_t)
    check("令牌指引（中文）：第 1 步写明必须选公开及原因（GitHub Free 只能为公开仓库开 Pages）；第 2 步有 Resource owner；经典令牌区分公开 public_repo / 私有 repo",
          all(k in sec_t for k in ("必须选公开（Public）", "GitHub Free 账号只能为公开仓库开启 Pages", "Resource owner", "私有的，必须勾选 `repo`")))
    check("令牌指引（中文）：配置命令是独占一行的代码块，命令里没有行尾注释，zsh 说明在代码块外",
          "```bash\necho 'export GITHUB_TOKEN=\"你的令牌\"' >> ~/.bashrc\n```" in sec_t and "使用 zsh 的话" in sec_t)
    _j0 = en_text.find("## S-TOKEN-GUIDE")
    _j1 = en_text.find("## S-", _j0 + 5) if _j0 >= 0 else -1
    sec_e = en_text[_j0:(_j1 if _j1 > 0 else len(en_text))] if _j0 >= 0 else ""
    check("令牌指引（英文）：四步顺序为 先建仓库 → 建令牌 → 保存令牌 → 回复 done，建仓与建令牌都带直达链接，仓库只选 prd-demos",
          _order(sec_e, "Step 1", "Step 2", "Step 3", "Step 4")
          and "https://github.com/new?name=prd-demos&visibility=public" in sec_e and "Only select repositories" in sec_e and "All repositories" not in sec_e)
    check("令牌指引（英文）：第 1 步写明必须选 Public 及原因；第 2 步有 Resource owner；经典令牌区分 public_repo / repo",
          all(k in sec_e for k in ("**choose Public**", "GitHub Free can only publish Pages from a public repository", "Resource owner", "a private repository needs `repo`")))
    check("令牌指引（英文）：配置命令是独占一行的代码块（不是行内代码）",
          "```bash\necho 'export GITHUB_TOKEN=\"your-token-here\"' >> ~/.bashrc\n```" in sec_e)
    inline_cmds = re.findall(r"(?m)^`([^`\n]*(?:echo |export |pip |python3 |prdkit )[^`\n]*)`\s*$", en_text)
    check("英文话术：没有任何独占一行的行内代码命令（要复制的命令都在代码块里）", not inline_cmds, str(inline_cmds))
    check("英文话术 M-E：手动安装命令改为代码块", "```\n{manual install command}\n```" in en["M-E"])
    sk_rule = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    check("SKILL.md：新增通用规则——要用户复制的命令一律独占一行的代码块，逐字照搬，翻译只翻说明不翻命令",
          "要用户复制的命令一律用独占一行的代码块" in sk_rule and "翻译只翻说明，不翻命令" in sk_rule)

    _imp = [str(f.relative_to(ROOT)) for f in (ROOT / "scripts").rglob("*.py") if "__pycache__" not in f.parts
            and re.search(r"(?m)^\s*(?:import|from)\s+requests\b", f.read_text(encoding="utf-8"))]
    check("依赖：脚本里没有 import requests（唯一第三方依赖是 Playwright，与 requirements.txt 一致，扫描工具不会报未声明依赖）",
          not _imp and "playwright" in (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
          and "requests" not in (ROOT / "requirements.txt").read_text(encoding="utf-8"), str(_imp))

    # ── 语言路由 ──
    sk = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    sec = sk[sk.index("## 0.5 语言路由"):sk.index("## 1. 路由")]
    check("语言路由：§0.5 写明判定依据（第一条消息主要语言）、混杂默认中文、一次性读话术文件、已有项目以 spec.lang 为准",
          all(k in sec for k in ("第一条消息", "拿不准默认 `zh`", "一次性读取", "spec.lang", "references/messages.en.md", "references/messages.zh.md")))
    check("语言路由：写明英文项目的全部切换点（--lang en、templates/en、doctor/setup 带全局 --lang、不要求中文字体）",
          all(k in sec for k in ("init … --lang en", "templates/en/prd-template.md", "templates/en/page-mobile.html",
                                 "prdkit --lang en doctor --brief", "prdkit --lang en setup", "不要求中文字体")))
    route = sk[sk.index("## 1. 路由"):sk.index("## 2. 对话体验规范")]
    check("英文触发词：路由表按意图覆盖“要一份 PRD”的多种说法（Write / Draft / Create / Generate / I need / Help me / Can you）",
          all(k in route for k in ("Write a PRD for", "Draft a PRD for", "Create a PRD for", "Generate a PRD for", "I need a PRD for",
                                   "Help me write a PRD for", "Can you write a PRD for", "按意图识别，不要求固定句式")))
    check("英文触发词：无描述的触发词、基于文件、draft、module 变体都有对应的英文说法",
          all(k in route for k in ("`Write a PRD` / `Generate PRD` / `PRD`（没有描述）", "Turn these notes into a PRD", "Write a PRD based on {file}",
                                   "Write a PRD draft for", "Just the flow first for", "Write only the {chapter} section", "--module {name}")))
    check("英文触发词：修改与发布 Demo 的多种说法（Revise / Update / Change / Edit / Adjust；Publish / Host / Share / Package / Deploy）",
          all(k in route for k in ("Revise / Update / Change / Edit / Adjust the PRD", "Publish the demo", "Host the demo", "Share the demo",
                                   "Package the demo", "Deploy the prototype")))
    check("英文快捷回复放宽（confirm / ok / yes / looks good / go ahead；start over / redo），但公开发布只认 confirm public",
          all(k in route for k in ("`looks good`", "`go ahead`", "`start over` / `redo`", "公开发布必须是 `confirm public`"))
          and "公开发布只认 `confirm public`" in sk and "Publishing publicly accepts only `confirm public`" in en_text)
    check("英文引导句口语化且可复制：交付消息给出修改例句，完成消息和降级句用 update the PRD / publish the demo（不再用 change XX / publish demo）",
          'for example: "change the points cap to 5000"' in en["M-DELIVER"]
          and 'for example "update the PRD: change the points cap to 5000"' in en["M-DONE"]
          and 'say "publish the demo" any time' in en_text
          and "change XX" not in en_text and 'say "publish demo"' not in en_text)
    desc = [l for l in sk.split("\n") if l.startswith("description: ")][0]
    check("description：英文侧覆盖 write / draft / create / generate / revise / update 与 publish / host / package；中文触发词原样保留",
          all(k in desc for k in ("write, draft, create, generate, revise, update or change a PRD", "write a PRD for", "I need a PRD for",
                                  "publish / host / package the demo", "only a request to write, draft or create a PRD with no details",
                                  '"Write a PRD", "write a prd"', "the skill then asks what to build"))
          and all(k in desc for k in ("PRD生成、生成PRD、写PRD、修改PRD、调整PRD、更新PRD、发布Demo、发布在线Demo", "不适用于周报、汇报PPT、技术方案等非产品需求类文档")))
    check("语言路由：§0.5 提到的每个 references/templates 文件都真实存在",
          all((ROOT / r).exists() for r in set(re.findall(r"(?:references|templates)/[\w\-./]+\.(?:md|html)", sec))))


# ───────────────────────── 试跑反馈修复：整张卡片包在 <a> 里 / 令牌指引直达链接 / 英文标题 ─────────────────────────
def trial_feedback_tests(tmp):
    import re
    from playwright.sync_api import sync_playwright
    from lib import browser as _br, style as _st
    # 1) 整张卡片包在 <a> 里：在 4 种风格下，<a class="card"> 都必须是块级，且背景盒子完整包住内容
    base_css = (ROOT / "templates" / "prototype-style.css").read_text(encoding="utf-8")
    check("样式表：<a class=\"card\"> 显式设为 display:block（<a> 默认行内，不设会让卡片背景碎成一块块）",
          re.search(r"(?m)^a\.card\s*\{\s*display:\s*block;\s*\}", base_css) is not None)
    html = ('<!doctype html><html><head><meta charset="utf-8"><style>%s</style></head><body><div class="phone-frame">'
            '<div class="card"><div class="card__title">Div card</div><p>text</p></div>'
            '<a class="card" href="#x"><div class="card__title">Anchor card</div><p class="text-sm">Set working days, slot length and blocked times for each doctor.</p>'
            '<span class="tag tag--primary mt-md">3 doctors on duty</span></a></div></body></html>')
    bad = []
    with sync_playwright() as pw:
        brw = _br.launch(pw)
        pg = brw.new_context(viewport={"width": 390, "height": 844}).new_page()
        for st in _st.STYLES:
            pg.set_content(html % _st.build_css(st))
            r = pg.evaluate("""() => { const a = document.querySelector('a.card'); const cs = getComputedStyle(a); const r = a.getBoundingClientRect();
                let b = r.top; a.querySelectorAll('*').forEach(e => { b = Math.max(b, e.getBoundingClientRect().bottom); });
                return {display: cs.display, h: Math.round(r.height), over: Math.round(b - r.bottom)}; }""")
            if r["display"] != "block" or r["over"] > 0 or r["h"] < 60:
                bad.append((st, r))
        brw.close()
    check("样式渲染：4 种风格下 <a class=\"card\"> 都是块级，且卡片底盒完整包住里面的文字和标签（内容不溢出）", not bad, str(bad))

    # 2) 令牌指引：第一步带直达链接（中文源文件 + 英文话术），链接单独成行
    pub = (ROOT / "references" / "publish.md").read_text(encoding="utf-8")
    en_t = (ROOT / "references" / "messages.en.md").read_text(encoding="utf-8")
    urls = ("https://github.com/settings/personal-access-tokens/new", "https://github.com/settings/tokens/new")
    check("令牌指引（中文）：建令牌的两个直达链接（细粒度、经典）都在，且每个链接单独成行；要求每一步需要打开的页面都带直达链接",
          all(re.search(r"(?m)^(?:- [^\n]*：)?" + re.escape(u) + r"$", pub) for u in urls) and "每一步需要打开的页面都必须带直达链接" in pub)
    _k0 = en_t.find("## S-TOKEN-GUIDE")
    _k1 = en_t.find("## S-", _k0 + 5) if _k0 >= 0 else -1
    sec = en_t[_k0:(_k1 if _k1 > 0 else len(en_t))] if _k0 >= 0 else ""
    check("令牌指引（英文）：S-TOKEN-GUIDE 的令牌页链接各占一行、不加反引号，并给出点不开时的菜单路径，且不含中文",
          all(re.search(r"(?m)^(?:\(A classic token also works: )?" + re.escape(u) + r"(?: \.|$)", sec) for u in urls[:1])
          and "https://github.com/settings/tokens/new" in sec and "Developer settings" in sec
          and "`https://" not in sec and not _han(sec))
    check("令牌指引：publish.md 指向英文话术 S-TOKEN-GUIDE（英文会话用英文措辞）", "S-TOKEN-GUIDE" in pub)

    # 3) 英文会话标题：逐字取自英文话术，不得拼中文步骤名
    sk = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    sec05 = sk[sk.index("## 0.5 语言路由"):sk.index("## 1. 路由")]
    check("英文标题：§0.5 要求标题逐字取自 messages.en.md、不拼中文步骤名、不换成【】或·，英文输出不应出现汉字",
          all(k in sec05 for k in ("逐字取自 `messages.en.md` 对应块的原文", "**[Step 2 of 3] Business flow**", "不得拼进英文输出",
                                   "不得把 `[ ]` 换成 `【 】`", "英文输出里不应出现任何汉字")))


# ───────────────────────── 开源首发（1.0.0）：包名 / 版本号 / 署名 / 许可证一致性 ─────────────────────────
def release_tests():
    import re
    sk = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    fm = sk.split("\n---\n")[0]
    check("发布元数据：SKILL.md 头部 name=prd-generator-oss、顶层 license=MIT、metadata.author=Tencent (cmlliazhang)、metadata.version=1.0.0",
          "name: prd-generator-oss\n" in fm and "\nlicense: MIT\n" in fm and "\n  author: Tencent (cmlliazhang)\n" in fm and '\n  version: "1.0.0"\n' in fm, fm[:300])
    # 头部必须能被真正的 YAML 解析器解析：只做字符串匹配会漏掉 `: `（冒号加空格）这类语法错误（11/12 引入、11/16 才被发现过）
    try:
        import yaml as _yaml
        _d = _yaml.safe_load(fm.lstrip("-\n"))
        _err = ""
    except ImportError:
        _d, _err = None, "PyYAML 未安装（本断言需要）"
    except Exception as _e:
        _d, _err = None, str(_e).split("\n")[0][:80]
    _md = (_d or {}).get("metadata") or {}
    _desc = str((_d or {}).get("description", ""))
    check("头部可解析：SKILL.md 的 YAML 头部能被真实 YAML 解析器解析，name/license/author/version 取值正确，description 在 1~1024 字符内",
          isinstance(_d, dict) and _d.get("name") == "prd-generator-oss" and _d.get("license") == "MIT"
          and _md.get("author") == "Tencent (cmlliazhang)" and _md.get("version") == "1.0.0" and 1 <= len(_desc) <= 1024, _err or str(_d)[:120])
    check("头部可解析：description 的触发语句在解析后仍完整（英文覆盖词、裸触发词、中文触发词都在）",
          all(k in _desc for k in ("write, draft, create, generate, revise, update or change a PRD", "only a request to write, draft or create a PRD with no details",
                                   "publish / host / package the demo", "PRD生成、生成PRD、写PRD", "不适用于周报")), _desc[:120])
    check("发布元数据：SKILL.md 头部没有 TODO 占位、没有内网元数据（data-classification / audit-level）",
          "TODO" not in fm and "data-classification" not in fm and "audit-level" not in fm)
    docs = {n: (ROOT / n).read_text(encoding="utf-8") for n in ("README.md", "README.zh-CN.md", "guide.md", "guide.en.md")}
    bare = {n: len(re.findall(r"prd-generator(?![-\w])", t)) for n, t in docs.items()}
    check("包名一致：README / guide（中英）里的安装提示词都要求安装目录名为 prd-generator-oss（与 SKILL.md 的 name 一致），没有残留旧包名，也不再提不存在的 zip 文件",
          not any(bare.values()) and all("prd-generator-oss" in t and "prd-generator-oss.zip" not in t for t in docs.values()), str(bare))
    ver_ok = ("version-1.0.0-blue" in docs["README.md"] and "version-1.0.0-blue" in docs["README.zh-CN.md"]
              and "（1.0.0）" in docs["guide.md"] and "**版本**：1.0.0" in docs["guide.md"]
              and "(1.0.0)" in docs["guide.en.md"] and "**Version**: 1.0.0" in docs["guide.en.md"] and any(l.startswith("# PRD Generator") and "（1.0.0）" in l for l in sk.split("\n")))
    check("版本一致：SKILL.md 标题 / metadata、README 徽章、guide（中英）都是 1.0.0，文档里没有残留 V5.2", ver_ok and not any("V5.2" in t for t in docs.values()))
    cl = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    check("CHANGELOG：当前版本标题为 [1.0.0]，不再有 [Unreleased]", "## [1.0.0]" in cl and "[Unreleased]" not in cl)
    holders = [str(f.relative_to(ROOT)) for f in ROOT.rglob("*")
               if f.is_file() and "__pycache__" not in f.parts and f.suffix not in (".png", ".pyc", ".zip") and f.name != "regress.py"
               and "cmlliazhang" in f.read_text(encoding="utf-8", errors="ignore")]
    check("署名卫生：企微名只出现在 SKILL.md 的 author 行这 1 处（不在 NOTICE / 版权头 / 文档 / 示例 / 测试数据里）", holders == ["SKILL.md"], str(holders))
    url = "https://github.com/Tencent/PRD-Generator"
    check("下载地址：四个文档里的安装提示词都指向 https://github.com/Tencent/PRD-Generator，没有残留旧仓库地址和 <org> 占位，并写明重命名为 prd-generator-oss",
          all(url in t for t in docs.values()) and not any("<org>" in t or "Tencent/prd-generator-oss" in t for t in docs.values())
          and all("PRD-Generator-main" in t for t in docs.values()), str([n for n, t in docs.items() if "<org>" in t or url not in t or "Tencent/prd-generator-oss" in t or "PRD-Generator-main" not in t]))
    author_line = [l for l in fm.split("\n") if l.startswith("  author:")]
    check("author 写法：括号并列（Tencent (cmlliazhang)），不含斜杠，避免被误认为 GitHub 组织/用户路径",
          author_line == ["  author: Tencent (cmlliazhang)"] and "/" not in author_line[0], str(author_line))
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    lic_txt = (ROOT / "LICENSE").read_text(encoding="utf-8")
    docs_lic = [n for n in ("README.md", "README.zh-CN.md", "CONTRIBUTING.md") if "Apache" in (ROOT / n).read_text(encoding="utf-8")]
    check("许可证一致：SKILL.md 的 license、LICENSE、NOTICE、README、CONTRIBUTING 都是 MIT，版权主体统一为 Tencent，仓库内（NOTICE 的 Playwright 依赖说明除外）不再出现 Apache",
          "licensed under the MIT." in notice and "PRD Generator is licensed under the MIT." in lic_txt
          and "Copyright (C) 2026 Tencent." in notice and "Copyright (C) 2026 Tencent." in lic_txt and not docs_lic, str(docs_lic))
    hdr_bad = [str(f.relative_to(ROOT)) for f in ROOT.rglob("*.py") if "__pycache__" not in f.parts
               and "PRD Generator is licensed under the MIT." not in f.read_text(encoding="utf-8")[:500]]
    check("许可证一致：每个 .py 的版权头都声明 MIT（与 LICENSE 对应），没有残留 Apache 头",
          not hdr_bad and not any("Apache License" in f.read_text(encoding="utf-8")[:800] for f in ROOT.rglob("*.py") if "__pycache__" not in f.parts), str(hdr_bad))


def main():
    if "--write-golden" in sys.argv:          # 维护者：用“改造之前”的代码生成中文黄金基线
        write_golden(sys.argv[sys.argv.index("--write-golden") + 1])
        return 0
    keep = "--keep" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="prdkit-regress-"))
    proj = tmp / "neighbor-lend"
    shutil.copytree(EXAMPLE, proj)

    # ── 0. 固定风格预览图必须与当前样式一致 ──
    code, out = run(None, "style", "check-preview")
    check("固定风格预览图与样式一致（不一致请运行 style build-preview）", code == 0, out)

    # ── 1. 移动端：4 个风格 + 自定义主色，各应用并截图抽查 ──
    for st, extra in [("flat", []), ("glass", []), ("soft", ["--accent", "#E5352B"]), ("dark", ["--accent", "#E5352B", "--source", "回归：深色+指定主色"])]:
        code, out = run(proj, "style", "apply", st, *extra)
        code2, out2 = run(proj, "shot", "--only", "list,borrow-sheet") if code == 0 else (1, "")
        check(f"移动端风格 {st}{' + 自定义主色' if extra else ''}：应用并截图", code == 0 and code2 == 0, out + out2)
    # 颜色与风格独立 + 沿用已确认的 style：不带参数 apply 应保持 dark + #E5352B + 依据不变
    code, out = run(proj, "style", "apply")
    st = json.loads((proj / "spec" / "screens.json").read_text(encoding="utf-8")).get("style", {})
    css = (proj / "prototype" / "assets" / "style.css").read_text(encoding="utf-8")
    check("style apply 无参数：沿用 spec 里已确认的风格、主色与依据",
          code == 0 and st == {"name": "dark", "accent": "#E5352B", "source": "回归：深色+指定主色"} and "--color-primary: #E5352B" in css, out + str(st))
    code, out = run(proj, "style", "preview", "glass", "--accent", "#07C160", "--out", str(tmp / "pv"))
    check("style preview <风格> --accent：只渲染所选风格+主色（移动端一张图）", code == 0 and (tmp / "pv" / "style-custom-app.png").exists() and not (tmp / "pv" / "style-custom-pc.png").exists(), out)
    run(proj, "style", "apply", "flat")
    check("apply 同时放入 assets/interaction.js", (proj / "prototype" / "assets" / "interaction.js").exists())

    for name, args in [("移动端 spec 校验", ["spec"]), ("移动端 页面截图", ["shot"]),
                       ("移动端 流程图渲染+几何自检", ["flow"]), ("移动端 PRD lint", ["lint"])]:
        code, out = run(proj, *args)
        ok = code == 0 and not (name.endswith("lint") and "100/100" not in out)
        check(name, ok, out)

    code, out = run(proj, "index")
    idx = proj / "prototype" / "index.html"
    txt = idx.read_text(encoding="utf-8") if idx.exists() else ""
    check("index：生成导航页且每个页面文件一个入口", code == 0 and txt.count('class="idx-main"') == 4 and "pages/list.html?s=empty" in txt, out)

    # ── 2. PC 后台：1440 视口 + 4 个风格 ──
    adm = tmp / "admin"
    shutil.copytree(ADMIN, adm)
    for st in ["flat", "glass", "soft", "dark"]:
        code, out = run(adm, "style", "apply", st)
        code2, out2 = run(adm, "shot", "--only", "orders,refund-dialog,order-log") if code == 0 else (1, "")
        check(f"PC 后台风格 {st}：应用并截图", code == 0 and code2 == 0, out + out2)
    run(adm, "style", "apply", "flat")
    for name, args in [("PC 后台 spec 校验", ["spec"]), ("PC 后台 页面截图", ["shot"]),
                       ("PC 后台 流程图+几何自检", ["flow"]), ("PC 后台 index", ["index"])]:
        code, out = run(adm, *args)
        check(name, code == 0, out)
    try:
        from PIL import Image
        w = Image.open(adm / "images" / "orders.png").size[0]
        check("PC 后台截图宽度为 1440（dpr 1）", w == 1440, f"实际宽度 {w}")
    except ImportError:
        pass

    # ── 3. 页面地图草案：没有原型、没有截图也能出图；正式模式必须拒绝；不得污染 images/ ──
    draft = tmp / "draft"
    shutil.copytree(EXAMPLE, draft, ignore=shutil.ignore_patterns("prototype", "images", ".prdkit"))
    code, out = run(draft, "flow", "--draft")
    outs = sorted(p.name for p in (draft / ".prdkit" / "draft").glob("*.png")) if (draft / ".prdkit" / "draft").is_dir() else []
    check("草案模式：无原型也能出流转图，且不写 images/", code == 0 and len(outs) >= 2 and not (draft / "images").exists(), out)
    code, out = run(draft, "flow")
    check("正式模式：无原型必须报错", code != 0, out)

    # ── 3b. 防再犯：批 1/批 2 修过的问题，必须有脚本能再次发现或从源头避免 ──
    guards(tmp, proj)
    extras(tmp, proj)

    # ── 4. FLOWGEO-05：植入“连线贴着节点边缘走”的缺陷，必须被查出；干净样例必须为 0 ──
    code, out = run(proj, "flow", "--check-only")
    check("FLOWGEO-05：干净样例无贴边告警", code == 0 and "FLOWGEO-05" not in out, out)
    fp = proj / "spec" / "flows" / "3.1.json"
    d = json.loads(fp.read_text(encoding="utf-8"))
    for e in d["edges"]:
        if e["f"] == "empty" and e["t"] == "list":
            e["fs"] = e["ts"] = "r"
            e.pop("fo", None)
            e.pop("to", None)
    fp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    code, out = run(proj, "flow", "--check-only")
    check("FLOWGEO-05：植入贴边缺陷被查出", "FLOWGEO-05" in out, out)


    # ── 批 3 试跑发现的问题（防再犯）──
    import os as _os
    cwd0 = _os.getcwd()
    try:
        _os.chdir(tmp)
        p = subprocess.run([sys.executable, str(PRDKIT), "check", "env"], capture_output=True, text=True)
    finally:
        _os.chdir(cwd0)
    check("check env：不在项目目录里也能运行（建项目之前就要跑）", p.returncode == 0 and "闸门" in p.stdout, p.stdout + p.stderr)

    d = tmp / "draft-table"
    shutil.copytree(EXAMPLE, d, ignore=shutil.ignore_patterns("prototype", "images", ".prdkit"))
    code, out = run(d, "flow", "--table", "--draft", "--scope", "3.1")
    check("flow --table --draft：原型未画完也能出页面清单", code == 0 and "| 页面/弹窗 |" in out, out)
    code, out = run(d, "flow", "--table", "--scope", "3.1")
    check("flow --table（无 --draft）：原型缺失时被拦住", code != 0, out)
    code, out = run(proj, "flow", "--table", "--scope", "3.2")
    other = [ln for ln in out.splitlines() if "（他章）" in ln]
    check("页面清单：他章页面的“去向”不写“终点”", bool(other) and all("终点" not in ln for ln in other), "\n".join(other))

    t = tmp / "pend"
    shutil.copytree(proj, t)
    tp = next(t.glob("*-prd.md"))
    tp.write_text(tp.read_text(encoding="utf-8") + "\n| 示例 | 指标 | [待确认-需PM补充] |\n", encoding="utf-8")
    code, o1 = run(t, "check", "prd")
    code2, o2 = run(t, "check", "prd")
    check("check prd：[待确认] 标记报 PEND-001（user 类，不阻断、不触发止损）",
          code == 0 and code2 == 0 and "PEND-001" in o2 and "止损" not in o2 and "连续" not in o2, o2)

    # ── 批 4：原型跳转 ↔ 流转一致（PROTO-020/021/022）──
    pl = tmp / "protolinks"
    shutil.copytree(proj, pl)
    code, out = run(pl, "check", "prototype")
    check("PROTO-02x：干净样例（返回键/Tab 不要求画进图）0 报告", code == 0 and "PROTO-02" not in out, out)

    def edit(fn, old, new):
        f = pl / "prototype" / "pages" / fn
        t = f.read_text(encoding="utf-8")
        assert old in t, (fn, old)
        f.write_text(t.replace(old, new, 1), encoding="utf-8")

    # 植入 1：<a href> 指向流转里没有连线的页面
    edit("list.html", "</body>", '<a href="review.html">偷偷的入口</a></body>')
    code, out = run(pl, "check", "prototype")
    check("PROTO-020：<a href> 跳转在流转里没有连线 → 报错", code != 0 and "PROTO-020" in out and "偷偷的入口" in out, out)
    # 豁免
    edit("list.html", '<a href="review.html">偷偷的入口</a>', '<a href="review.html" data-flow-ignore>偷偷的入口</a>')
    code, out = run(pl, "check", "prototype")
    check("PROTO-020：加 data-flow-ignore 可显式豁免", "PROTO-020" not in out, out)
    # 植入 2：onclick / data-go / script 三种写法
    edit("list.html", '<a href="review.html" data-flow-ignore>偷偷的入口</a>', '<div onclick="location.href=\'review.html\'">B</div><span data-go="review.html">C</span><script>function x(){location.assign("review.html")}</script>')
    code, out = run(pl, "check", "prototype")
    check("PROTO-020：onclick / data-go / script 里的跳转同样被识别", code != 0 and "PROTO-020" in out, out)
    # 植入 3：死链
    edit("list.html", '<div onclick="location.href=\'review.html\'">B</div><span data-go="review.html">C</span><script>function x(){location.assign("review.html")}</script>', '<a href="nope.html">死链</a>')
    code, out = run(pl, "check", "prototype")
    check("PROTO-022：链接指向不存在的页面 → 报错", code != 0 and "PROTO-022" in out and "nope.html" in out, out)
    edit("list.html", '<a href="nope.html">死链</a>', "")
    # 植入 4：流转里有连线，原型里没有入口（反向）
    fp = pl / "spec" / "flows" / "3.2.json"
    fd = json.loads(fp.read_text(encoding="utf-8"))
    nodes = {n["screen"]: n["id"] for n in fd["nodes"] if n.get("screen")}
    nodes["detail"] = "x-detail"
    fd["nodes"].append({"id": "x-detail", "screen": "detail", "col": 5, "row": 0})
    fd["edges"].append({"f": nodes["review"], "t": "x-detail", "label": "点“再借一次”", "kind": "normal"})
    fp.write_text(json.dumps(fd, ensure_ascii=False, indent=1), encoding="utf-8")
    code, out = run(pl, "check", "prototype")
    check("PROTO-021：流转里有连线但原型没入口 → 提醒（不阻断）", code == 0 and "PROTO-021" in out, out)

    i18n_tests(tmp)
    skill_lang_tests()
    trial_feedback_tests(tmp)
    release_tests()

    if keep:
        print(f"\n临时目录已保留：{tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n回归通过" if not failed else f"\n回归失败：{', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
