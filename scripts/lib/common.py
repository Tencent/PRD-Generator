# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""prdkit 公共模块：路径解析、项目定位、JSON 读写、输出编码。

铁律：本模块及所有脚本中不得出现写死的绝对路径。
所有路径均由以下信息在运行时推导：
  1. skill 目录   = 本文件向上两级（scripts/lib/common.py → skill 根）
  2. workspace    = 环境变量 PRDKIT_WORKSPACE > 自当前目录向上找 .git/.codebuddy > 当前目录
  3. PRD 根目录   = 环境变量 PRDKIT_PRD_ROOT > workspace/.prdkit.json 的 prd_root > 内置候选
  4. 项目目录     = 命令行显式给出的目录 > 按项目名在 PRD 根目录里搜索 > 自当前目录向上找
"""
import io
import json
import os
import re
import sys
from pathlib import Path

from . import i18n

SKILL_DIR = Path(__file__).resolve().parent.parent.parent

SPEC_DIRNAME = "spec"
SCREENS_FILE = "screens.json"
FLOWS_DIRNAME = "flows"
PROTO_DIRNAME = "prototype"
IMAGES_DIRNAME = "images"
STATE_DIRNAME = ".prdkit"


class ProjectNotFound(Exception):
    pass


def force_utf8():
    """避免非 UTF-8 终端下输出中文/符号时报错。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        enc = (getattr(stream, "encoding", None) or "").lower()
        if enc != "utf-8":
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                setattr(sys, name, io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace"))


def find_workspace(start=None):
    env = os.environ.get("PRDKIT_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    cur = Path(start or os.getcwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists() or (p / ".codebuddy").is_dir():
            return p
    return cur


def _read_json_safe(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def prd_roots(ws, explicit=None):
    """返回按优先级排序的 PRD 根目录候选（可能不存在，调用方自行判断）。"""
    roots = []
    for v in (explicit, os.environ.get("PRDKIT_PRD_ROOT")):
        if v:
            roots.append(Path(v).expanduser())
    cfg = _read_json_safe(ws / ".prdkit.json")
    if isinstance(cfg, dict) and cfg.get("prd_root"):
        r = Path(cfg["prd_root"]).expanduser()
        roots.append(r if r.is_absolute() else ws / r)
    roots += [
        ws / ".codebuddy" / "docs" / "prd",
        ws / ".codebuddy" / "projects",   # projects/<项目>/prd/<版本>
        ws / "docs" / "prd",
        ws / "prd",
        ws,
    ]
    seen, out = set(), []
    for r in roots:
        k = str(r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def is_project_dir(p):
    p = Path(p)
    return p.is_dir() and (
        (p / SPEC_DIRNAME / SCREENS_FILE).exists() or (p / PROTO_DIRNAME).is_dir()
    )


def _natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _version_children(p):
    kids = [c for c in Path(p).iterdir() if c.is_dir() and is_project_dir(c)] if Path(p).is_dir() else []
    return sorted(kids, key=lambda c: _natural_key(c.name), reverse=True)


class Project:
    """一个 PRD 版本目录的路径集合。"""

    def __init__(self, root, note=""):
        self.root = Path(root).resolve()
        self.note = note
        self.spec_dir = self.root / SPEC_DIRNAME
        self.screens_path = self.spec_dir / SCREENS_FILE
        self.flows_dir = self.spec_dir / FLOWS_DIRNAME
        self.proto = self.root / PROTO_DIRNAME
        self.images = self.root / IMAGES_DIRNAME
        self.state = self.root / STATE_DIRNAME

    @property
    def name(self):
        return self.root.name

    def prd_md(self):
        cands = sorted(self.root.glob("*-prd.md")) or sorted(self.root.glob("*.md"))
        return cands[0] if cands else None

    def load_screens(self):
        if not self.screens_path.exists():
            raise ProjectNotFound(i18n.t(f"缺少 {self.screens_path}（请先生成 spec，或用 migrate 从旧 flowmap-config.json 转换）",
                                         f"Missing {self.screens_path} (generate the spec first, or convert an old flowmap-config.json with migrate)"))
        return json.loads(self.screens_path.read_text(encoding="utf-8"))

    @property
    def lang(self):
        """项目语言（spec.lang；缺省或读不出 = zh，旧项目行为不变）。"""
        try:
            return i18n.lang_of(json.loads(self.screens_path.read_text(encoding="utf-8")))
        except Exception:
            return i18n.DEFAULT

    def flow_files(self):
        return sorted(self.flows_dir.glob("*.json")) if self.flows_dir.is_dir() else []


def _pick(base, note_prefix=""):
    if is_project_dir(base):
        return Project(base)
    kids = _version_children(base)
    if kids:
        note = f"{note_prefix}目录下有多个版本，已选用最新的 {kids[0].name}（可用 --project 指定具体目录）" if len(kids) > 1 else ""
        return Project(kids[0], note)
    return None


def resolve_project(arg=None, cwd=None, prd_root=None):
    """定位项目目录。arg 可以是目录路径或项目名；为空则自当前目录向上寻找。"""
    cwd_p = Path(cwd or os.getcwd()).resolve()
    ws = find_workspace(cwd_p)
    searched = []

    if arg:
        p = Path(arg).expanduser()
        if p.exists():
            hit = _pick(p.resolve())
            if hit:
                return hit
            searched.append(str(p.resolve()))
        for root in prd_roots(ws, prd_root):
            for base in (root / arg, root / arg / "prd"):
                searched.append(str(base))
                if base.is_dir():
                    hit = _pick(base)
                    if hit:
                        return hit
        raise ProjectNotFound(i18n.t("找不到项目：%s\n已搜索：\n  %s\n提示：可直接传入项目版本目录的路径，或设置 PRDKIT_PRD_ROOT。",
                                     "Project not found: %s\nSearched:\n  %s\nHint: pass the path of the project version directory directly, or set PRDKIT_PRD_ROOT.") % (arg, "\n  ".join(dict.fromkeys(searched))))

    for p in [cwd_p, *cwd_p.parents]:
        if (p / SPEC_DIRNAME / SCREENS_FILE).exists():
            return Project(p)
    raise ProjectNotFound(i18n.t("未指定项目，且当前目录向上没有找到 spec/screens.json。请使用 --project <目录或项目名>。",
                                 "No project given, and no spec/screens.json was found above the current directory. Use --project <directory or project name>."))


_RC_FILES = (".bashrc", ".bash_profile", ".profile", ".zshrc", ".zprofile")


def get_secret(var):
    """读取凭证，返回 (值, 来源)；未配置返回 ("", "")。

    AI 通过非交互 shell 执行命令时，~/.bashrc 不会被加载，环境变量会“丢失”。
    所以：先看进程环境变量；没有就以纯文本方式解析 shell 配置文件里的 export 行
    （不执行文件内容；同一变量出现多次以最后一次为准，与 shell 行为一致）。
    绝不打印凭证内容。
    """
    val = os.environ.get(var, "").strip()
    if val:
        return val, "环境变量"
    pat = re.compile(r"""^\s*export\s+%s=(?:"([^"]*)"|'([^']*)'|(\S+))\s*(?:#.*)?$""" % re.escape(var))
    for rc in _RC_FILES:
        path = Path.home() / rc
        if not path.is_file():
            continue
        found = ""
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = pat.match(line)
                if m:
                    found = next(g for g in m.groups() if g is not None).strip()
        except Exception:
            continue
        if found:
            return found, f"~/{rc}"
    return "", ""


def count_secret_definitions(var):
    """统计各 shell 配置文件里该变量被 export 了几次（用于提示重复配置）。"""
    pat = re.compile(r"^\s*export\s+%s=" % re.escape(var))
    out = {}
    for rc in _RC_FILES:
        path = Path.home() / rc
        if path.is_file():
            n = sum(1 for l in path.read_text(encoding="utf-8", errors="ignore").splitlines() if pat.match(l))
            if n:
                out[f"~/{rc}"] = n
    return out


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def md5_file(path):
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
