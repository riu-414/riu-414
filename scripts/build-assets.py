"""
README 用の静的 SVG（バナー / セクション見出し / CTA ボタン）を生成する。

GitHub の README では Web フォントが使えないため、Zen Old Mincho の
グリフをパスに変換して SVG に埋め込んでいる。文言や色を変えたら再実行する。

    pip install fonttools
    python scripts/build-assets.py
"""

import urllib.request
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/zenoldmincho/ZenOldMincho-Regular.ttf"
FONT_PATH = ROOT / ".cache" / "ZenOldMincho-Regular.ttf"

THEMES = {
    "dark": {
        "bg": "#2A2620", "fg": "#F4EFE6", "sub": "#938B7F", "acc": "#C58A5F",
        "grid": "#F4EFE6", "grid_op": ".06",
        # GitHub のページ背景上に置く見出し用
        "h_fg": "#F4EFE6", "h_sub": "#9198A1", "h_line": "#3D444D", "h_acc": "#C58A5F",
    },
    "light": {
        "bg": "#F6F2EB", "fg": "#2A2620", "sub": "#57514A", "acc": "#A85E36",
        "grid": "#2A2620", "grid_op": ".07",
        "h_fg": "#2A2620", "h_sub": "#59636E", "h_line": "#D1D9E0", "h_acc": "#A85E36",
    },
}

SECTIONS = [
    ("about", "01", "About", "わたしについて"),
    ("skills", "02", "Skills", "スキル"),
    ("works", "03", "Works", "制作実績"),
    ("blog", "04", "Blog", "最新記事"),
    ("activity", "05", "Activity", "コントリビューション"),
    ("contact", "06", "Contact", "お問い合わせ"),
]


def load_font() -> TTFont:
    if not FONT_PATH.exists():
        FONT_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    return TTFont(FONT_PATH)


class Typesetter:
    def __init__(self, font: TTFont):
        self.font = font
        self.cmap = font.getBestCmap()
        self.glyphs = font.getGlyphSet()
        self.upem = font["head"].unitsPerEm

    def width(self, text: str, size: float, tracking: float = 0) -> float:
        scale = size / self.upem
        w = sum(self.glyphs[self.cmap[ord(ch)]].width * scale + tracking for ch in text)
        return w - tracking if text else 0

    def path(self, text: str, size: float, x: float, y: float, tracking: float = 0, anchor: str = "start") -> str:
        """テキストを SVG の path データに変換する。y はベースライン。"""
        if anchor == "end":
            x -= self.width(text, size, tracking)
        elif anchor == "middle":
            x -= self.width(text, size, tracking) / 2
        scale = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        cursor = x
        for ch in text:
            glyph = self.glyphs[self.cmap[ord(ch)]]
            glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, y)))
            cursor += glyph.width * scale + tracking
        return pen.getCommands()


def svg(width: int, height: int, body: str, label: str, style: str = "") -> str:
    style_block = f"<style>{style}</style>" if style else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">'
        f"<title>{label}</title>{style_block}{body}</svg>\n"
    )


def banner(ts: Typesetter, c: dict) -> str:
    w, h = 900, 260
    grid = "".join(f"M0 {y}H{w}" for y in (65, 130, 195)) + "".join(f"M{x} 0V{h}" for x in range(150, w, 150))
    name_w = ts.width("Yuya Osugi", 60)
    body = f"""
<rect width="{w}" height="{h}" rx="6" fill="{c['bg']}"/>
<path d="{grid}" stroke="{c['grid']}" stroke-opacity="{c['grid_op']}" fill="none"/>
<g class="f f1"><path fill="{c['acc']}" d="{ts.path('FRONT-END ENGINEER  /  NIIGATA', 12, 60, 78, tracking=4)}"/></g>
<g class="f f2"><path fill="{c['fg']}" d="{ts.path('Yuya Osugi', 60, 56, 150)}"/>
<circle cx="{56 + name_w + 8:.1f}" cy="146" r="4" fill="{c['acc']}"/></g>
<g class="f f3"><path fill="{c['fg']}" d="{ts.path('想いを、かたちにする。', 20, 60, 196, tracking=3)}"/></g>
<g class="f f4"><path fill="{c['sub']}" d="{ts.path('Turning intention into precise, beautiful code.', 12, 60, 222, tracking=1)}"/></g>
<g transform="translate(700 70)"><g class="f f5" fill="none" stroke="{c['acc']}" stroke-linecap="round" stroke-linejoin="round">
<circle class="spin" cx="70" cy="60" r="58" stroke-opacity=".5" stroke-dasharray="4 6"/>
<circle cx="70" cy="60" r="38" stroke-opacity=".3"/>
<path d="M52 44 36 60l16 16M88 44l16 16-16 16M78 38 62 82" stroke-width="2"/>
</g></g>"""
    style = (
        ".f{animation:up .9s cubic-bezier(.2,.7,.2,1) both}"
        ".f1{animation-delay:.1s}.f2{animation-delay:.3s}.f3{animation-delay:.6s}.f4{animation-delay:.8s}.f5{animation-delay:1s}"
        "@keyframes up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}"
        ".spin{transform-box:fill-box;transform-origin:center;animation:spin 40s linear infinite}"
        "@keyframes spin{to{transform:rotate(360deg)}}"
        "@media (prefers-reduced-motion:reduce){.f,.spin{animation:none}}"
    )
    return svg(w, h, body, "Yuya Osugi — 想いを、かたちにする。", style)


def heading(ts: Typesetter, c: dict, no: str, title: str, ja: str) -> str:
    w, h = 900, 64
    no_text = f"{no} —"
    no_w = ts.width(no_text, 13, tracking=3)
    body = f"""
<path fill="{c['h_acc']}" d="{ts.path(no_text, 13, 0, 44, tracking=3)}"/>
<path fill="{c['h_fg']}" d="{ts.path(title, 28, no_w + 14, 44)}"/>
<path fill="{c['h_sub']}" d="{ts.path(ja, 13, w, 44, tracking=1, anchor='end')}"/>
<rect y="{h - 1}" width="{w}" height="1" fill="{c['h_line']}"/>"""
    return svg(w, h, body, f"{no} — {title}（{ja}）")


def cta(ts: Typesetter, c: dict) -> str:
    w, h = 420, 56
    text = "お仕事のご依頼・ご相談はこちら  →"
    body = f"""
<rect width="{w}" height="{h}" rx="4" fill="#A85E36"/>
<path fill="#FFFFFF" d="{ts.path(text, 16, w / 2, 34, tracking=2, anchor='middle')}"/>"""
    return svg(w, h, body, "お仕事のご依頼・ご相談はこちら")


def main() -> None:
    ts = Typesetter(load_font())
    (OUT / "sections").mkdir(parents=True, exist_ok=True)
    for theme, c in THEMES.items():
        (OUT / f"banner-{theme}.svg").write_text(banner(ts, c), encoding="utf-8")
        for key, no, title, ja in SECTIONS:
            (OUT / "sections" / f"{key}-{theme}.svg").write_text(heading(ts, c, no, title, ja), encoding="utf-8")
    (OUT / "cta.svg").write_text(cta(ts, THEMES["light"]), encoding="utf-8")
    print(f"generated assets in {OUT}")


if __name__ == "__main__":
    main()
