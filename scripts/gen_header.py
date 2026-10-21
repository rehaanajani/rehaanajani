"""Render the profile header as SVG, with all text outlined to paths.

GitHub serves README images through a sanitising proxy that blocks web fonts,
so every glyph is converted to a path here. CSS animation inside the SVG still
runs, which is what keeps the live dot pulsing.

The bottom-right line is the live part: update.py passes in the most recent
thing shipped, and the scheduled workflow re-renders both themes.
"""
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "assets"

W, H = 1280, 300
PAD = 64

_fonts = {}


def font(kind):
    if kind not in _fonts:
        if kind == "display":
            f = instancer.instantiateVariableFont(TTFont(FONTS / "Archivo[wdth,wght].ttf"), {"wdth": 125, "wght": 900})
        else:
            f = instancer.instantiateVariableFont(TTFont(FONTS / "GeistMono[wght].ttf"), {"wght": 400})
        _fonts[kind] = f
    return _fonts[kind]


def text_path(kind, text, size, x, y, tracking=0.0):
    """Return (svg path d, advance width) for text with its baseline at y."""
    f = font(kind)
    gs, cmap = f.getGlyphSet(), f.getBestCmap()
    scale = size / f["head"].unitsPerEm
    pen = SVGPathPen(gs)
    cursor = x
    for ch in text:
        name = cmap.get(ord(ch))
        if name is None:
            continue
        glyph = gs[name]
        glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, y)))
        cursor += glyph.width * scale + tracking * size
    return pen.getCommands(), cursor - x


def right_aligned(kind, text, size, y, tracking):
    _, w = text_path(kind, text, size, 0, 0, tracking)
    d, _ = text_path(kind, text, size, W - PAD - w, y, tracking)
    return d, W - PAD - w


def dot_field(fg, opacity):
    gap = 22
    cells = "".join(
        f'<rect x="{11 + i * gap}" y="{11 + j * gap}" width="1.4" height="1.4"/>'
        for j in range(H // gap + 1)
        for i in range(W // gap + 2)
    )
    return f'<g fill="{fg}" opacity="{opacity}" mask="url(#fade)">{cells}</g>'


def render(theme, live):
    dark = theme == "dark"
    bg = "#000000" if dark else "#ffffff"
    fg = "#ffffff" if dark else "#0a0a0a"
    dim = "#878787" if dark else "#8a8a8a"
    line = "#292929" if dark else "#e2e2e2"
    live_c = "#3ddc84" if dark else "#1a7f37"

    name_d, _ = text_path("display", "REHAAN AJANI", 92, PAD, 190, tracking=-0.02)
    role_d, _ = text_path("mono", "FOUNDER  ·  AI ENGINEER  ·  CHENNAI", 14, PAD, 92, tracking=0.08)
    co_d, _ = right_aligned("mono", "NOETOS  /  MANTRA  /  TGOI", 14, 92, 0.08)
    tag_d, _ = text_path("mono", "SRM KTR  ·  B.TECH CSE (AI & ML)", 14, PAD, 252, tracking=0.08)
    live_d, live_x = right_aligned("mono", live, 14, 252, 0.08)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Rehaan Ajani. Founder, AI engineer, Chennai. {live.title()}.">
  <style>
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
    @keyframes ring {{ 0% {{ r: 4px; opacity: 0.55; }} 100% {{ r: 12px; opacity: 0; }} }}
    @keyframes drift {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-22px); }} }}
    .live {{ animation: pulse 2.4s ease-in-out infinite; }}
    .ring {{ animation: ring 2.4s ease-out infinite; }}
    .field {{ animation: drift 8s linear infinite; }}
    @media (prefers-reduced-motion: reduce) {{ .live, .ring, .field {{ animation: none; }} }}
  </style>
  <defs>
    <radialGradient id="g" cx="80%" cy="28%" r="68%">
      <stop offset="0" stop-color="#fff" stop-opacity="1"/>
      <stop offset="0.78" stop-color="#fff" stop-opacity="0"/>
    </radialGradient>
    <mask id="fade"><rect width="{W}" height="{H}" fill="url(#g)"/></mask>
  </defs>
  <rect width="{W}" height="{H}" rx="18" fill="{bg}"/>
  <g class="field">{dot_field(fg, 0.22 if dark else 0.3)}</g>
  <path d="{role_d}" fill="{dim}"/>
  <path d="{co_d}" fill="{dim}"/>
  <path d="{name_d}" fill="{fg}"/>
  <line x1="{PAD}" y1="218" x2="{W - PAD}" y2="218" stroke="{line}" stroke-width="1"/>
  <path d="{tag_d}" fill="{dim}"/>
  <circle class="ring" cx="{live_x - 18:.1f}" cy="247" r="4" fill="none" stroke="{live_c}" stroke-width="1.5"/>
  <circle class="live" cx="{live_x - 18:.1f}" cy="247" r="4" fill="{live_c}"/>
  <path d="{live_d}" fill="{fg}"/>
</svg>
'''


def write(live):
    for theme in ("dark", "light"):
        (OUT / f"header-{theme}.svg").write_text(render(theme, live))


if __name__ == "__main__":
    import sys

    write(sys.argv[1] if len(sys.argv) > 1 else "SHIPPING AT NOETOS")
    print("ok")
