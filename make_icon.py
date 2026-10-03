# -*- coding: utf-8 -*-
"""生成 MathLab 图标 (assets/mathlab.ico), 纯 PIL 绘制"""
import os

from PIL import Image, ImageDraw, ImageFont

CLAY = (217, 119, 87)
CLAY_DK = (176, 87, 48)
PAPER = (250, 249, 245)


def draw(size):
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(S * 0.24)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=CLAY)
    # 顶部高光
    d.rounded_rectangle([int(S * 0.08), int(S * 0.06), int(S * 0.92), int(S * 0.5)],
                        radius=int(S * 0.18), fill=(232, 160, 130, 90))
    # π 符号
    fpath = "C:/Windows/Fonts/georgiab.ttf"
    try:
        f = ImageFont.truetype(fpath, int(S * 0.62))
    except Exception:
        f = ImageFont.load_default()
    bbox = d.textbbox((0, 0), "π", font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((S - w) / 2 - bbox[0], (S - h) / 2 - bbox[1] + int(S * 0.02)),
           "π", font=f, fill=PAPER)
    # 右下角小加号
    px, py, L, W = int(S * 0.74), int(S * 0.76), int(S * 0.16), max(2, int(S * 0.045))
    d.rectangle([px - L // 2, py - W // 2, px + L // 2, py + W // 2], fill=CLAY_DK)
    d.rectangle([px - W // 2, py - L // 2, px + W // 2, py + L // 2], fill=CLAY_DK)
    return img.resize((size, size), Image.LANCZOS)


def main():
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(outdir, exist_ok=True)
    ico = os.path.join(outdir, "mathlab.ico")
    png = os.path.join(outdir, "mathlab.png")
    base = draw(256)
    base.save(png)
    base.save(ico, format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon ->", ico)
    print("png  ->", png)


if __name__ == "__main__":
    main()
