# Tencent is pleased to support the open source community by making PRD Generator available.
#
# Copyright (C) 2026 Tencent.  All rights reserved.
#
# PRD Generator is licensed under the MIT.
# See the LICENSE file in the project root for the full terms.
"""fontcheck：检查运行环境能否用 Chromium 正常渲染中文。

没有中文字体的机器上，Chromium 会把中文画成方块（豆腐块），截图和流程图都会“静默出乱码”，
而且不会报任何错。这里用 canvas 画几个常用字，如果它们的像素完全相同，说明都落成了同一个缺字方块。
"""

from . import i18n

SAMPLE = "扁龘鬱"
INSTALL_HINT = ("安装中文字体后重试：Debian/Ubuntu 用 `apt install fonts-noto-cjk`；"
                "CentOS/TencentOS 用 `yum install google-noto-sans-cjk-ttc-fonts`；macOS 和 Windows 自带，无需安装")

INSTALL_HINT_EN = ("Install a CJK font and retry: Debian/Ubuntu `apt install fonts-noto-cjk`; "
                   "CentOS/TencentOS `yum install google-noto-sans-cjk-ttc-fonts`; macOS and Windows ship with one")

_JS = """(chars) => {
  const out = [];
  for (const ch of chars) {
    const c = document.createElement('canvas'); c.width = 48; c.height = 48;
    const x = c.getContext('2d');
    x.fillStyle = '#fff'; x.fillRect(0, 0, 48, 48);
    x.fillStyle = '#000'; x.font = '32px "PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif';
    x.fillText(ch, 4, 36);
    out.push(Array.from(x.getImageData(0, 0, 48, 48).data).join(','));
  }
  return out;
}"""


def is_tofu(renders):
    """纯函数：几个不同的汉字渲染结果完全相同 → 都是缺字方块。"""
    return len(renders) >= 2 and len(set(renders)) == 1


def has_cjk_font(page=None):
    """返回 (是否可用, 说明)。page 省略时自己临时起一个 Chromium。

    英文项目（spec.lang = en）不需要中文字体：直接放行。若截图里仍放了中文文案，需要自行安装中文字体。"""
    if i18n.cur() == "en":
        return True, "English project: a CJK font is not required"
    if page is not None:
        return _probe(page)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        from . import browser as _browser
        b = _browser.launch(p)
        try:
            return _probe(b.new_page())
        finally:
            b.close()


def _probe(page):
    page.set_content("<html><body></body></html>")
    renders = page.evaluate(_JS, SAMPLE)
    if is_tofu(renders):
        return False, i18n.t("Chromium 渲染中文只得到缺字方块（没有中文字体）", "Chromium only renders missing-glyph boxes for Chinese text (no CJK font)")
    return True, i18n.t("中文字体可用", "A CJK font is available")


def require():
    """截图 / 流程图开跑前调用：缺字体就拒绝产出，避免静默出乱码图。"""
    ok, msg = has_cjk_font()
    if not ok:
        raise SystemExit(i18n.t(f"❌ {msg}。\n   {INSTALL_HINT}", f"❌ {msg}.\n   {INSTALL_HINT_EN}"))
