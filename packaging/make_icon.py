"""Draw the app icon and save it as PNG (window), ICO (Windows) and ICNS (macOS).

    python packaging/make_icon.py      # needs Pillow
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
S = 1024


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Rounded dark tile with the app's accent colour
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=220, fill=(30, 31, 34, 255))
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=220, outline=(88, 101, 242, 255), width=36)
    # A world: sky circle with grass and dirt bands
    cx, cy, r = S // 2, S // 2 - 30, 300
    globe = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(globe)
    g.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(110, 190, 255, 255))
    g.rectangle((0, cy + 40, S, cy + 120), fill=(87, 209, 139, 255))
    g.rectangle((0, cy + 120, S, S), fill=(150, 95, 55, 255))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    img.paste(globe, (0, 0), mask)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(230, 230, 230, 255), width=24)
    # "Live" text bar underneath, like the on-stream label
    d.rounded_rectangle((250, 800, S - 250, 900), radius=50, fill=(88, 101, 242, 255))
    for i, x in enumerate(range(320, S - 320, 90)):
        d.rounded_rectangle((x, 835, x + 60, 865), radius=15, fill=(255, 255, 255, 255))
    return img


if __name__ == "__main__":
    img = draw()
    img.save(OUT / "icon.png")
    img.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(OUT / "icon.icns")
    print("wrote icon.png, icon.ico, icon.icns to", OUT)
