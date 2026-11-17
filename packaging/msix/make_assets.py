"""MSIX / Microsoft Store için logo görsellerini üretir (Pillow).

Çıktı: packaging/msix/Assets/
  StoreLogo.png          50x50
  Square44x44Logo.png    44x44
  Square150x150Logo.png  150x150
  Wide310x150Logo.png    310x150
  StoreListing300.png    300x300  (Partner Center'a yüklenecek uygulama görseli)

Kullanım:  python packaging/msix/make_assets.py
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

OUT = pathlib.Path(__file__).resolve().parent / "Assets"
TOP = (30, 58, 138)      # #1E3A8A
BOTTOM = (14, 165, 163)  # #0EA5A3
WHITE = (255, 255, 255)


def _gradient(w: int, h: int) -> Image.Image:
    img = Image.new("RGBA", (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)) + (255,)
        for x in range(w):
            px[x, y] = c
    return img


def _shield(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float) -> None:
    """Basit kalkan + onay işareti."""
    w, h = size * 0.78, size
    top = cy - h / 2
    pts = [
        (cx - w / 2, top + h * 0.12),
        (cx, top),
        (cx + w / 2, top + h * 0.12),
        (cx + w / 2, top + h * 0.50),
        (cx, top + h),
        (cx - w / 2, top + h * 0.50),
    ]
    draw.polygon(pts, fill=WHITE)
    lw = max(2, int(size * 0.09))
    draw.line([(cx - w * 0.22, cy + h * 0.02), (cx - w * 0.04, cy + h * 0.18),
               (cx + w * 0.26, cy - h * 0.14)], fill=TOP, width=lw, joint="curve")


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def make(w: int, h: int, shield_ratio: float = 0.62, rounded: bool = False) -> Image.Image:
    # Küçük boyutlarda kenar yumuşatma için 4x çizip küçült.
    s = 4
    img = _gradient(w * s, h * s)
    d = ImageDraw.Draw(img)
    _shield(d, w * s / 2, h * s / 2, min(w, h) * s * shield_ratio)
    img = img.resize((w, h), Image.LANCZOS)
    if rounded:
        img = _rounded(img, radius=max(4, min(w, h) // 6))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make(50, 50).save(OUT / "StoreLogo.png")
    make(44, 44, 0.70).save(OUT / "Square44x44Logo.png")
    make(150, 150).save(OUT / "Square150x150Logo.png")
    make(310, 150, 0.62).save(OUT / "Wide310x150Logo.png")
    make(300, 300, 0.60, rounded=True).save(OUT / "StoreListing300.png")
    for p in sorted(OUT.glob("*.png")):
        print("yazildi:", p.name, Image.open(p).size)


if __name__ == "__main__":
    main()
