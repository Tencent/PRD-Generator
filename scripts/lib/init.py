# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""init：新建项目骨架，spec/screens.json 由命令生成而不是手写（避免字段名、视口、schema 写错）。

  prdkit init <项目名> --name "产品名" --platform miniprogram|h5|app|web|admin [--version V1.0] [--root PRD根目录]

只创建目录和一份空 spec；不选风格（风格与配色要让用户确认）、不创建页面。
"""
import re
from pathlib import Path

from .common import SPEC_DIRNAME, FLOWS_DIRNAME, PROTO_DIRNAME, IMAGES_DIRNAME, dump_json, find_workspace, prd_roots
from . import i18n

VIEWPORT = {
    "miniprogram": {"width": 390, "height": 844, "dpr": 2},
    "h5": {"width": 390, "height": 844, "dpr": 2},
    "app": {"width": 390, "height": 844, "dpr": 2},
    "web": {"width": 1440, "height": 900, "dpr": 1},
    "admin": {"width": 1440, "height": 900, "dpr": 1},
}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


def run(dir_name, name, platform, version="V1.0", root=None, lang="zh"):
    if not NAME_RE.match(dir_name):
        print(i18n.t(f"❌ 项目目录名只能用小写英文、数字、连字符（如 quiz-challenge），当前：{dir_name!r}",
                     f"❌ The project directory name may only use lowercase letters, digits and hyphens (e.g. quiz-challenge), got: {dir_name!r}"))
        return 2
    if platform not in VIEWPORT:
        print(i18n.t(f"❌ platform 需为 {sorted(VIEWPORT)} 之一", f"❌ platform must be one of {sorted(VIEWPORT)}"))
        return 2
    if root:
        base = Path(root).expanduser()
    else:
        ws = find_workspace()
        cands = prd_roots(ws)
        base = next((c for c in cands if c.is_dir() and c.name == "prd"), ws / ".codebuddy" / "docs" / "prd")
    proj = base / dir_name
    if (proj / SPEC_DIRNAME / "screens.json").exists():
        print(i18n.t(f"❌ {proj} 已存在项目。迭代新版本请用新目录名（如 {dir_name}-v2），保留旧版本。",
                     f"❌ A project already exists at {proj}. For a new version use a new directory name (e.g. {dir_name}-v2) and keep the old version."))
        return 1
    for d in (SPEC_DIRNAME + "/" + FLOWS_DIRNAME, PROTO_DIRNAME + "/pages", PROTO_DIRNAME + "/assets", IMAGES_DIRNAME):
        (proj / d).mkdir(parents=True, exist_ok=True)
    spec = {"schema": 1, "name": name, "version": version, "platform": platform,
            "viewport": VIEWPORT[platform], "chapters": [], "screens": []}
    if lang != "zh":          # zh 是缺省：不写 lang 字段，保证中文项目的 spec 与历史版本逐字一致
        spec = {"schema": 1, "lang": lang, **{k: v for k, v in spec.items() if k != "schema"}}
    dump_json(proj / SPEC_DIRNAME / "screens.json", spec)
    print(i18n.t(f"✅ 已创建项目：{proj}", f"✅ Project created: {proj}"))
    print(i18n.t("   下一步：按用户确认的范围，在 spec/screens.json 登记章节与页面，写 spec/flows/*.json，然后 prdkit.py check map",
                 "   Next: register chapters and pages in spec/screens.json for the scope the user confirmed, write spec/flows/*.json, then run prdkit.py check map"))
    return 0
