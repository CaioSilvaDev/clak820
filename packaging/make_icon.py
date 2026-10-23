"""Gera assets/icon.ico e docs/preview.png a partir do próprio renderizador."""

from pathlib import Path

from PIL import Image, ImageDraw

from clak820.render import BG, CLAUDE, GREEN, TRACK, Panel, render

ROOT = Path(__file__).resolve().parent.parent


def icon() -> Image.Image:
    s = 1024
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 40, s - 40, s - 40], radius=200, fill=BG + (255,))
    box = [210, 210, s - 210, s - 210]
    d.arc(box, 0, 360, fill=TRACK, width=110)
    d.arc(box, -90, 160, fill=GREEN, width=110)
    d.ellipse([s / 2 - 70, s / 2 - 70, s / 2 + 70, s / 2 + 70], fill=CLAUDE)
    return img


def main() -> None:
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "docs").mkdir(exist_ok=True)
    icon().save(ROOT / "assets" / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon().resize((256, 256), Image.LANCZOS).save(ROOT / "assets" / "icon.png")
    for name, panel in {
        "preview.png": Panel(42, "21:30", "12.3M"),
        "preview-high.png": Panel(87, "18:05", "48.6M"),
    }.items():
        render(panel).resize((384, 384), Image.NEAREST).save(ROOT / "docs" / name)
    print("ok")


if __name__ == "__main__":
    main()
