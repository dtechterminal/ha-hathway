"""Draw the generic integration icon (Wi-Fi arcs over a quota bar). Not Hathway's logo."""
import sys
from PIL import Image, ImageDraw


def icon(size: int) -> Image.Image:
    s = size / 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(56 * s), fill=(14, 116, 144, 255))
    cx, cy = 128 * s, 150 * s
    for r in (92, 62, 32):
        d.arc([cx - r * s, cy - r * s, cx + r * s, cy + r * s], 225, 315,
              fill=(255, 255, 255, 255), width=int(16 * s))
    d.ellipse([cx - 11 * s, cy - 11 * s, cx + 11 * s, cy + 11 * s], fill=(255, 255, 255, 255))
    d.rounded_rectangle([44 * s, 190 * s, 212 * s, 214 * s], radius=int(12 * s),
                        fill=(94, 178, 199, 255))
    d.rounded_rectangle([44 * s, 190 * s, 150 * s, 214 * s], radius=int(12 * s),
                        fill=(255, 255, 255, 255))
    return img


out = sys.argv[1]
icon(256).save(f"{out}/icon.png", optimize=True)
icon(512).save(f"{out}/icon@2x.png", optimize=True)
