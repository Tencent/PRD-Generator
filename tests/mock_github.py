# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""GitHub REST API 的本地 mock（仅用于回归测试，覆盖 github_pages 发布器用到的 git data / repos / pages 接口子集）。

特殊行为：
  · 令牌必须是 GOOD_TOKEN，否则 401
  · 仓库 someone-else/* 不存在
状态保存在内存里，供测试断言：mock.repos[(owner, name)] = {"branches": {"gh-pages": commit}, "pages": bool}
"""
import hashlib
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

GOOD_TOKEN = "ghp_regress_good_token_0123456789"
LOGIN = "tester"


class MockGitHub:
    def __init__(self):
        self.requests = []        # [(method, path)]
        self.repos = {}           # (owner, name) -> {"branches": {}, "pages": False}
        self.blobs = {}           # sha -> bytes
        self.trees = {}           # sha -> {path: blob_sha}
        self.commits = {}         # sha -> {"tree": sha, "parents": [...]}
        self.auth_seen = []
        self.deny_create = None   # 设为 403 / 404：模拟令牌无权创建仓库（默认 None = 允许）
        self._srv = None

    # ── 便捷读取 ──
    def branch_files(self, owner, name):
        r = self.repos[(owner, name)]
        c = r["branches"].get("gh-pages")
        return dict(self.trees[self.commits[c]["tree"]]) if c else {}

    def inject(self, owner, name, path, data=b"stale"):
        """直接往 gh-pages 分支塞一个文件（模拟线上已有的旧文件）。"""
        r = self.repos[(owner, name)]
        files = self.branch_files(owner, name)
        sha = hashlib.sha1(data).hexdigest()
        self.blobs[sha] = data
        files[path] = sha
        ts = hashlib.sha1(json.dumps(files, sort_keys=True).encode()).hexdigest()
        self.trees[ts] = files
        cs = hashlib.sha1((ts + "inject").encode()).hexdigest()
        self.commits[cs] = {"tree": ts, "parents": []}
        r["branches"]["gh-pages"] = cs

    # ── 服务 ──
    def start(self):
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None):
                body = json.dumps(obj if obj is not None else {}).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _handle(self, method):
                n = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
                path = self.path
                mock.requests.append((method, path))
                mock.auth_seen.append(self.headers.get("Authorization", ""))
                if self.headers.get("Authorization") != "Bearer " + GOOD_TOKEN:
                    return self._send(401, {"message": "Bad credentials"})
                p = path.split("?")[0]

                if method == "GET" and p == "/user":
                    return self._send(200, {"login": LOGIN})
                if method == "POST" and p == "/user/repos":
                    if mock.deny_create:
                        return self._send(mock.deny_create, {"message": "Resource not accessible by personal access token"})
                    mock.repos[(LOGIN, payload["name"])] = {"branches": {}, "pages": False}
                    return self._send(201, {"name": payload["name"], "private": payload.get("private", False)})

                m = re.match(r"^/repos/([^/]+)/([^/]+)(/.*)?$", p)
                if not m:
                    return self._send(404, {"message": "Not Found"})
                owner, name, rest = m.group(1), m.group(2), m.group(3) or ""
                repo = mock.repos.get((owner, name))
                if repo is None:
                    return self._send(404, {"message": "Not Found"})

                if method == "GET" and rest == "":
                    return self._send(200, {"name": name, "private": False})
                if rest == "/git/blobs" and method == "POST":
                    data = payload["content"].encode()
                    if payload.get("encoding") == "base64":
                        import base64
                        data = base64.b64decode(payload["content"])
                    sha = hashlib.sha1(data).hexdigest()
                    mock.blobs[sha] = data
                    return self._send(201, {"sha": sha})
                if rest == "/git/ref/heads/gh-pages" and method == "GET":
                    c = repo["branches"].get("gh-pages")
                    return self._send(200, {"object": {"sha": c}}) if c else self._send(404, {"message": "Not Found"})
                mm = re.match(r"^/git/commits/([0-9a-f]+)$", rest)
                if mm and method == "GET":
                    return self._send(200, {"tree": {"sha": mock.commits[mm.group(1)]["tree"]}})
                mm = re.match(r"^/git/trees/([0-9a-f]+)$", rest)
                if mm and method == "GET":
                    t = mock.trees[mm.group(1)]
                    return self._send(200, {"truncated": False, "tree": [{"path": k, "type": "blob", "sha": v} for k, v in t.items()]})
                if rest == "/git/trees" and method == "POST":
                    files = dict(mock.trees[payload["base_tree"]]) if payload.get("base_tree") else {}
                    for e in payload["tree"]:
                        if e["sha"] is None:
                            files.pop(e["path"], None)
                        else:
                            files[e["path"]] = e["sha"]
                    sha = hashlib.sha1(json.dumps(files, sort_keys=True).encode()).hexdigest()
                    mock.trees[sha] = files
                    return self._send(201, {"sha": sha})
                if rest == "/git/commits" and method == "POST":
                    sha = hashlib.sha1((payload["tree"] + payload["message"] + str(len(mock.commits))).encode()).hexdigest()
                    mock.commits[sha] = {"tree": payload["tree"], "parents": payload.get("parents", [])}
                    return self._send(201, {"sha": sha})
                if rest == "/git/refs" and method == "POST":
                    repo["branches"][payload["ref"].split("/")[-1]] = payload["sha"]
                    return self._send(201, {})
                if rest == "/git/refs/heads/gh-pages" and method == "PATCH":
                    repo["branches"]["gh-pages"] = payload["sha"]
                    return self._send(200, {})
                if rest == "/pages" and method == "GET":
                    if not repo["pages"]:
                        return self._send(404, {"message": "Not Found"})
                    return self._send(200, {"html_url": f"https://{owner}.github.io/{name}/", "source": {"branch": "gh-pages", "path": "/"}})
                if rest == "/pages" and method == "POST":
                    repo["pages"] = True
                    return self._send(201, {"html_url": f"https://{owner}.github.io/{name}/"})
                return self._send(404, {"message": "Not Found"})

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def do_PATCH(self):
                self._handle("PATCH")

        self._srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self._srv.server_port}"

    def stop(self):
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
