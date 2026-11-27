# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""GitHub Pages 发布器（可选扩展，不是必经路径）。

把 prototype/ 推到 GitHub 仓库的 gh-pages 分支，并开启 GitHub Pages，成功后把站点地址记录进 spec.demo。

    prdkit publish github-pages --confirm-public [--repo 用户/仓库] [--path 子目录] [--update] [--dry-run] [--no-wait]

默认：仓库 = <你的账号>/prd-demos（不存在则创建为公开仓库）；子目录 = <项目名>-<版本>。
灵活用法：
  · 多个 Demo 共用一个仓库      默认行为，每个 Demo 一个子目录
  · 一个 Demo 一个仓库          --repo 你/某仓库 --path .        （站点根目录就是这个 Demo）
  · 指定别的共用仓库            --repo 你/别的仓库

安全（代码级约束）：
  · 公开站点：没有 --confirm-public 一律拒绝并停在提示，不联网。每次发布都必须带，不记忆、不缓存
  · 令牌只读环境变量 GITHUB_TOKEN（或 GH_TOKEN），只放请求头，不打印、不写文件
  · 401 立即停止，不重试
  · 目标子目录已存在默认拒绝，必须 --update 才会整目录替换（只替换该子目录，不动仓库里其他 Demo）
  · 只请求 https://api.github.com；回环地址（http://127.0.0.1）仅用于测试 mock
  · 发布前先做自检（spec 无错误、页面无外链资源、有 index.html 与 style.css）

所需令牌权限：
  · 细粒度令牌：对目标仓库授予 Contents（读写）和 Pages（读写）；要自动创建仓库还需账号级 Administration（读写）
  · 经典令牌：public_repo（公开仓库）
只用标准库，不依赖 git 命令或 requests。
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from lib import demo
from lib import i18n
from lib.common import get_secret

NAME = "github-pages"
API_BASE = "https://api.github.com"
TOKEN_VARS = ("GITHUB_TOKEN", "GH_TOKEN")
DEFAULT_REPO_NAME = "prd-demos"
BRANCH = "gh-pages"
WAIT_SECONDS = 120

PUBLIC_WARNING = """⚠️  GitHub Pages 站点是【公开】的：任何拿到链接的人都能打开，不需要登录。
    原型里的页面文案、业务规则、界面设计都会被看到。
    · 涉及未发布的业务、对外保密的信息，请不要发布到这里（改用打包 prototype.zip 交付，或自己的内部托管）
    · 站点发布后仍可通过删除仓库里的子目录来下线，但链接可能已被他人保存或被搜索引擎收录

确认可以公开发布，请重新运行并加上 --confirm-public。"""

PUBLIC_WARNING_EN = """⚠️  A GitHub Pages site is PUBLIC: anyone with the link can open it, no login needed.
    The page copy, business rules and interface design of the prototype will be visible.
    · Do not publish unreleased business or confidential information here (deliver the prototype.zip package, or use your own internal hosting instead)
    · After publishing you can take the site offline by deleting the sub-directory in the repository, but the link may already have been saved by others or indexed by search engines

If you are sure it may be published publicly, rerun with --confirm-public."""


class PublishError(Exception):
    pass


class NoTokenError(PublishError):
    """令牌未配置：退出码 2（与语言无关，不再靠中文子串判断）。"""


# ───────────────────────── 地址与 HTTP ─────────────────────────
def api_base():
    b = os.environ.get("PRDKIT_GITHUB_API", API_BASE).rstrip("/")
    if b == API_BASE:
        return b
    u = urllib.parse.urlparse(b)
    if u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost"):
        return b
    raise PublishError(i18n.t(f"PRDKIT_GITHUB_API 只允许 {API_BASE} 或本机回环地址（测试用），当前：{b}", f"PRDKIT_GITHUB_API only allows {API_BASE} or a local loopback address (for tests), got: {b}"))


def _opener(base):
    if urllib.parse.urlparse(base).hostname in ("127.0.0.1", "localhost"):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def _token():
    for v in TOKEN_VARS:
        val, _src = get_secret(v)
        if val:
            return val
    return ""


def _call(method, path, token, payload=None, timeout=60):
    base = api_base()
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "prdkit"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with _opener(base).open(req, timeout=timeout) as r:
            body = r.read()
            return r.status, (json.loads(body.decode("utf-8")) if body else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode("utf-8"))
        except Exception:
            return e.code, {}
    except urllib.error.URLError as ex:
        raise PublishError(i18n.t(f"网络错误：{ex.reason}", f"Network error: {ex.reason}"))
    except OSError as ex:
        raise PublishError(i18n.t(f"网络错误：{ex}", f"Network error: {ex}"))


def explain(status, body, what=""):
    msg = (body or {}).get("message", "") if isinstance(body, dict) else ""
    en = i18n.cur() == "en"
    tail = ((f" (server: {msg})" if en else f"（服务端：{msg}）") if msg else "")
    table = ({
        401: "The token is invalid or expired (401). Do not retry: create a new token and configure GITHUB_TOKEN (see references/publish.md)",
        403: "No permission, or rate-limited (403). Check that the token grants read/write on Contents and Pages; try again later",
        404: "The resource does not exist, or the token cannot see it (404). Check the repository name and that the token is authorised for it",
        409: "The repository is empty or the branch state conflicts (409)",
        422: "The request was not accepted (422); common causes: the repository name is taken, or Pages is already enabled with a different configuration",
    } if en else {
        401: "令牌无效或已过期（401）。不要重试：请重新创建令牌并配置 GITHUB_TOKEN（见 references/publish.md）",
        403: "没有权限，或触发了频率限制（403）。检查令牌是否授予了 Contents 与 Pages 的读写权限；稍后再试",
        404: "资源不存在，或令牌看不到它（404）。检查仓库名、令牌是否授权了该仓库",
        409: "仓库为空或分支状态冲突（409）",
        422: "请求不被接受（422），常见原因：仓库名已被占用、Pages 已开启但配置不同",
    })
    return (f"{what}{': ' if en else '：'}" if what else "") + table.get(status, (f"The server returned HTTP {status}" if en else f"服务端返回 HTTP {status}")) + tail


def _ok(status, body, what, allow=()):
    if 200 <= status < 300 or status in allow:
        return
    raise PublishError(explain(status, body, what))


# ───────────────────────── 目标解析 ─────────────────────────
_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9\-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9._\-]{1,100}$")
_PATH_SEG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*$")


def normalize_path(path, default_name):
    """子目录：None → 默认名；'.' 或 '/' → 站点根目录（返回 ''）；否则校验每一段。"""
    if path is None:
        path = default_name
    path = str(path).strip()
    if path in (".", "/", "./"):
        return ""
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts or any(p in (".", "..") or not _PATH_SEG.match(p) or p.startswith(".") for p in parts):
        raise PublishError(i18n.t(f"子目录只能由字母、数字、点、连字符、下划线组成（可用 / 分层，不能以点开头）：{path!r}", f"The sub-directory may only contain letters, digits, dots, hyphens and underscores (use / for levels, no leading dot): {path!r}"))
    return "/".join(parts)


def site_url(owner, repo, path, html_url=None):
    if html_url:
        base = html_url.rstrip("/")
    elif repo.lower() == f"{owner.lower()}.github.io":
        base = f"https://{owner}.github.io"
    else:
        base = f"https://{owner}.github.io/{repo}"
    return base + ("/" + path if path else "") + "/"


# ───────────────────────── 发布 ─────────────────────────
def _collect(proj):
    files = demo.collect(proj)
    if not files:
        raise PublishError(i18n.t("prototype/ 里没有可发布的文件", "There are no publishable files in prototype/"))
    return files


def _get_login(token):
    st, body = _call("GET", "/user", token)
    if st == 401:
        raise PublishError(explain(401, body))
    _ok(st, body, i18n.t("读取账号信息", "Reading account info"))
    return body["login"]


def _cannot_create_msg(repo):
    url = f"https://github.com/new?name={repo}&visibility=public"
    return i18n.t(
        f"没能找到也没能自动创建仓库 {repo}（令牌无权创建，或者令牌看不到它）。按你的情况选一种：\n"
        f"  A. 仓库还没建：打开下面的链接，建一个公开仓库（名称保持 {repo}）：\n"
        f"{url}\n"
        f"  B. 仓库已经建好：多半是令牌看不到它。到令牌设置里检查：Repository access 要包含它；"
        f"Resource owner 要是仓库所在的个人账号（不是组织）；经典令牌要勾选 repo（私有仓库）或 public_repo（公开仓库）。\n"
        f"  另外：免费账号无法为私有仓库开启 Pages，请把仓库设为公开。\n"
        f"  处理好后回复“好了”，我会重新发布。",
        f"Could not find or automatically create the repository {repo} (the token cannot create repositories, or it cannot see it). Pick the case that fits:\n"
        f"  A. The repository does not exist yet: open the link below and create a public repository (keep the name {repo}):\n"
        f"{url}\n"
        f"  B. The repository already exists: the token most likely cannot see it. In the token settings check that Repository access includes it, "
        f"that Resource owner is the personal account that owns the repository (not an organization), and, for a classic token, "
        f"tick repo (private repository) or public_repo (public repository).\n"
        f"  Also: GitHub Free cannot publish Pages from a private repository, so make the repository public.\n"
        f"  Once that is done, reply \"done\" and I will publish again.")


def _ensure_repo(token, owner, repo, create_ok, login):
    st, body = _call("GET", f"/repos/{owner}/{repo}", token)
    if st == 200:
        return body, False
    if st != 404:
        raise PublishError(explain(st, body, i18n.t("查询仓库", "Querying the repository")))
    if not create_ok:
        raise PublishError(i18n.t(f"仓库 {owner}/{repo} 不存在。默认专用仓库会自动创建；自定义仓库请先在 GitHub 上创建好。", f"Repository {owner}/{repo} does not exist. The default dedicated repository is created automatically; create a custom repository on GitHub first."))
    if owner.lower() != login.lower():
        raise PublishError(i18n.t(f"仓库 {owner}/{repo} 不存在，且不是你自己账号下的仓库，不会自动创建。请先建好并授权令牌。", f"Repository {owner}/{repo} does not exist and is not under your own account, so it will not be created automatically. Create it first and authorise the token."))
    st, body = _call("POST", "/user/repos", token, {
        "name": repo, "private": False, "auto_init": True,
        "description": "PRD prototype demos published by prdkit"})
    if st in (403, 404):       # 令牌没有创建仓库的权限：告诉用户怎么办，而不是笼统地让他去查 Contents / Pages
        raise PublishError(_cannot_create_msg(repo))
    _ok(st, body, i18n.t("创建仓库", "Creating the repository"))
    return body, True


def _branch_state(token, owner, repo):
    """返回 (commit_sha, tree_sha, {path: blob_sha})；分支不存在返回 (None, None, {})。"""
    st, body = _call("GET", f"/repos/{owner}/{repo}/git/ref/heads/{BRANCH}", token)
    if st == 404 or st == 409:
        return None, None, {}
    _ok(st, body, i18n.t("读取 gh-pages 分支", "Reading the gh-pages branch"))
    commit_sha = body["object"]["sha"]
    st, c = _call("GET", f"/repos/{owner}/{repo}/git/commits/{commit_sha}", token)
    _ok(st, c, i18n.t("读取提交", "Reading the commit"))
    tree_sha = c["tree"]["sha"]
    st, t = _call("GET", f"/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1", token)
    _ok(st, t, i18n.t("读取文件树", "Reading the file tree"))
    if t.get("truncated"):
        raise PublishError(i18n.t("仓库文件过多，无法安全地替换子目录；请换一个专用仓库", "The repository has too many files to replace a sub-directory safely; use a dedicated repository"))
    return commit_sha, tree_sha, {e["path"]: e["sha"] for e in t.get("tree", []) if e.get("type") == "blob"}


def _under(path, prefix):
    return True if not prefix else (path == prefix or path.startswith(prefix + "/"))


def _enable_pages(token, owner, repo):
    st, body = _call("GET", f"/repos/{owner}/{repo}/pages", token)
    if st == 200:
        src = (body.get("source") or {})
        if src.get("branch") != BRANCH:
            print(i18n.t(f"⚠️  该仓库的 Pages 已开启，但发布源是 {src.get('branch')}（不是 {BRANCH}）。"
                         f"本次不改动现有设置；请到仓库 Settings → Pages 把发布源改为 {BRANCH} 分支，站点才会显示新内容。",
                         f"⚠️  Pages is already enabled for this repository, but its source is {src.get('branch')} (not {BRANCH}). "
                         f"Existing settings are left untouched; go to the repository Settings → Pages and set the source to the {BRANCH} branch, otherwise the site will not show the new content."))
        return body.get("html_url")
    if st != 404:
        raise PublishError(explain(st, body, i18n.t("读取 Pages 状态", "Reading the Pages status")))
    st, body = _call("POST", f"/repos/{owner}/{repo}/pages", token, {"source": {"branch": BRANCH, "path": "/"}})
    if st == 409 or st == 422:       # 并发下已被开启
        st2, b2 = _call("GET", f"/repos/{owner}/{repo}/pages", token)
        if st2 == 200:
            return b2.get("html_url")
    _ok(st, body, i18n.t("开启 GitHub Pages", "Enabling GitHub Pages"))
    return body.get("html_url")


def _wait_online(url, seconds):
    base = api_base()
    deadline = time.time() + seconds
    op = _opener(base)
    while time.time() < deadline:
        try:
            with op.open(urllib.request.Request(url + "index.html", headers={"User-Agent": "prdkit"}), timeout=10) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False


def cmd_publish(proj, repo=None, path=None, confirm_public=False, update=False, dry_run=False, no_wait=False):
    try:
        data = proj.load_screens()
        default_name = demo.deliver_name(proj, data)
        sub = normalize_path(path, default_name)
        if repo and not _REPO_RE.match(repo):
            raise PublishError(i18n.t(f"--repo 需为 用户/仓库 形式，当前：{repo!r}", f"--repo must look like user/repo, got: {repo!r}"))
        demo.precheck(proj)
        zpath, n, size = demo.build_zip(proj, proj.state / "github-pages" / f"{default_name}.zip")
        files = _collect(proj)

        if i18n.cur() == "en":
            print(f"repository: {repo or '<your account>/' + DEFAULT_REPO_NAME}    sub-directory: {sub or '(site root)'}    {n} files    {size / 1024:.0f}KB")
        else:
            print(f"仓库：{repo or '<你的账号>/' + DEFAULT_REPO_NAME}    子目录：{sub or '（站点根目录）'}    文件 {n} 个    {size / 1024:.0f}KB")
        if dry_run:
            print(i18n.t("（dry-run）已完成自检与打包，未联网、未创建或修改任何东西。", "(dry-run) Self-check and packing are done; nothing was sent over the network, created or modified."))
            if not confirm_public:
                print(i18n.t("实际发布前会再次提示：这是公开站点，需 --confirm-public。", "Before the real publish you will be warned again: this is a public site and needs --confirm-public."))
            return 0
        if not confirm_public:
            print(i18n.t(PUBLIC_WARNING, PUBLIC_WARNING_EN))
            return 3
        token = _token()
        if not token:
            raise NoTokenError(i18n.t("未配置 GITHUB_TOKEN。GitHub Pages 发布是可选项：可以配置后重试，也可以改用 prdkit demo local 打包交付。配置步骤见 references/publish.md",
                                      "GITHUB_TOKEN is not configured. Publishing to GitHub Pages is optional: configure it and retry, or deliver with prdkit demo local instead. Setup steps: references/publish.md"))

        login = _get_login(token)
        owner, rname = (repo.split("/", 1) if repo else (login, DEFAULT_REPO_NAME))
        rinfo, created = _ensure_repo(token, owner, rname, create_ok=True, login=login)
        if rinfo.get("private"):
            print(i18n.t("⚠️  这个仓库是私有的：免费账号无法为私有仓库开启 Pages，且开启后站点依然是公开的。",
                         "⚠️  This repository is private: free accounts cannot enable Pages for a private repository, and the site is still public once enabled."))
        if created:
            print(i18n.t(f"✅ 已创建公开仓库 {owner}/{rname}", f"✅ Created the public repository {owner}/{rname}"))

        head, base_tree, existing = _branch_state(token, owner, rname)
        old = [p for p in existing if _under(p, sub) and p != ".nojekyll"] if sub else \
              [p for p in existing if p != ".nojekyll"]
        if old and not update:
            if i18n.cur() == "en":
                where = f"The sub-directory {sub}" if sub else "The site root"
                scope = "only this sub-directory is replaced, other demos are untouched" if sub else "everything currently on the gh-pages branch is cleared"
                raise PublishError(f"{where} already has content; publishing was refused to avoid an accidental overwrite.\n"
                                   f"  · To replace the whole directory ({scope}): add --update\n"
                                   f"  · To publish as a new version: use a different --path (e.g. put the version in the name)")
            where = f"子目录 {sub}" if sub else "站点根目录"
            scope = "只替换这一个子目录，不动其他 Demo" if sub else "会清除 gh-pages 分支上现有的全部内容"
            raise PublishError(f"{where} 已有内容，为避免误覆盖已拒绝发布。\n"
                               f"  · 确认要整目录替换（{scope}）：加 --update\n"
                               f"  · 发布为新版本：换一个 --path（如在名称里带上版本号）")

        entries = []
        new_paths = set()
        for p, rel in files:
            st, blob = _call("POST", f"/repos/{owner}/{rname}/git/blobs", token,
                             {"content": base64.b64encode(p.read_bytes()).decode("ascii"), "encoding": "base64"}, timeout=120)
            _ok(st, blob, i18n.t(f"上传 {rel}", f"Uploading {rel}"))
            full = f"{sub}/{rel}" if sub else rel
            new_paths.add(full)
            entries.append({"path": full, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        if ".nojekyll" not in existing:
            st, blob = _call("POST", f"/repos/{owner}/{rname}/git/blobs", token, {"content": "", "encoding": "utf-8"})
            _ok(st, blob, i18n.t("上传 .nojekyll", "Uploading .nojekyll"))
            entries.append({"path": ".nojekyll", "mode": "100644", "type": "blob", "sha": blob["sha"]})
        for p in old:
            if p not in new_paths:
                entries.append({"path": p, "mode": "100644", "type": "blob", "sha": None})

        tree_payload = {"tree": entries}
        if base_tree:
            tree_payload["base_tree"] = base_tree
        st, tree = _call("POST", f"/repos/{owner}/{rname}/git/trees", token, tree_payload, timeout=120)
        _ok(st, tree, i18n.t("创建文件树", "Creating the file tree"))
        msg = f"Publish {default_name} via prdkit"
        st, commit = _call("POST", f"/repos/{owner}/{rname}/git/commits", token,
                           {"message": msg, "tree": tree["sha"], "parents": [head] if head else []})
        _ok(st, commit, i18n.t("创建提交", "Creating the commit"))
        if head:
            st, ref = _call("PATCH", f"/repos/{owner}/{rname}/git/refs/heads/{BRANCH}", token, {"sha": commit["sha"]})
        else:
            st, ref = _call("POST", f"/repos/{owner}/{rname}/git/refs", token, {"ref": f"refs/heads/{BRANCH}", "sha": commit["sha"]})
        _ok(st, ref, i18n.t("更新 gh-pages 分支", "Updating the gh-pages branch"))
        print(i18n.t(f"✅ 已推送 {len(files)} 个文件到 {owner}/{rname}@{BRANCH}", f"✅ Pushed {len(files)} files to {owner}/{rname}@{BRANCH}"))

        html_url = _enable_pages(token, owner, rname)
        url = site_url(owner, rname, sub, html_url)
        demo.record_online(proj, url, publisher=NAME, extra={"repo": f"{owner}/{rname}", "path": sub})
        print(i18n.t(f"✅ 已记录在线 Demo：{url}", f"✅ Online demo recorded: {url}"))
        print(i18n.t("⚠️  这是公开地址：任何拿到链接的人都能打开。", "⚠️  This is a public address: anyone with the link can open it."))
        if no_wait:
            print(i18n.t("（--no-wait）未等待站点生效；通常 1~2 分钟后可打开，期间会显示 404。",
                         "(--no-wait) Did not wait for the site to go live; it usually opens within 1-2 minutes, showing 404 until then."))
        elif _wait_online(url, WAIT_SECONDS):
            print(i18n.t("✅ 站点已生效，可以打开。", "✅ The site is live and can be opened."))
        else:
            print(i18n.t("ℹ️  站点还在生效中（首次开启 Pages 通常需要 1~2 分钟），稍后再打开链接；期间显示 404 属正常。",
                         "ℹ️  The site is still going live (enabling Pages for the first time usually takes 1-2 minutes); open the link a bit later - a 404 in the meantime is normal."))
        print(i18n.t("下一步：prdkit.py links --apply  → 把 PRD 里的关联原型与附录 B 切换为在线链接",
                     "Next: prdkit.py links --apply  -> switch the prototype lines and Appendix B in the PRD to the online links"))
        return 0
    except PublishError as e:
        print(f"❌ {e}")
        return 2 if isinstance(e, NoTokenError) else 1
    except demo.DemoError as e:
        print(f"❌ {e}")
        return 1
