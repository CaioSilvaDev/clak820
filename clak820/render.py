"""Desenha o painel 128×128 com Pillow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import protocol as p

SIZE = p.SIZE
SS = 4  # supersampling do anel

BG = (0, 0, 0)
CLAUDE = (217, 119, 87)  # laranja Claude
TEXT = (235, 235, 235)
MUTED = (150, 150, 150)
TRACK = (45, 45, 45)
GREEN = (80, 200, 120)
YELLOW = (240, 190, 60)
RED = (235, 75, 65)

FONTS = Path("C:/Windows/Fonts")


def _font(names: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        try:
            return ImageFont.truetype(str(FONTS / name), size)
        except OSError:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def _big(size: int):
    return _font(("bahnschrift.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"), size)


def _small(size: int):
    return _font(("seguisb.ttf", "segoeui.ttf", "DejaVuSans.ttf"), size)


@dataclass(frozen=True)
class Panel:
    """Tudo o que aparece na tela; se for igual ao último enviado, não reenvia."""

    pct: int | None  # % da janela de 5h (None = desconhecido)
    reset: str  # "21:30" ou "--:--"
    tokens: str  # "12.3M"


def color_for(pct: int | None) -> tuple[int, int, int]:
    if pct is None:
        return MUTED
    return GREEN if pct < 50 else YELLOW if pct < 80 else RED


def _center(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill) -> None:
    w = draw.textlength(text, font=font)
    draw.text(((SIZE - w) / 2, y), text, font=font, fill=fill)


def render(panel: Panel) -> Image.Image:
    color = color_for(panel.pct)

    # Anel em alta resolução, reduzido depois para ficar suave.
    ring = Image.new("RGB", (SIZE * SS, SIZE * SS), BG)
    rd = ImageDraw.Draw(ring)
    box = [x * SS for x in (26, 18, 102, 94)]
    width = 8 * SS
    rd.arc(box, 0, 360, fill=TRACK, width=width)
    if panel.pct:
        end = -90 + 360 * min(panel.pct, 100) / 100
        rd.arc(box, -90, end, fill=color, width=width)
    img = ring.resize((SIZE, SIZE), Image.LANCZOS)

    d = ImageDraw.Draw(img)
    _center(d, 0, "CLAUDE · 5h", _small(13), CLAUDE)

    pct_text = f"{panel.pct}%" if panel.pct is not None else "--"
    font = _big(26 if len(pct_text) <= 3 else 22)
    l, t, r, b = d.textbbox((0, 0), pct_text, font=font)
    d.text((64 - (r - l) / 2 - l, 56 - (b - t) / 2 - t), pct_text, font=font, fill=TEXT)

    _center(d, 96, f"reset {panel.reset}", _small(13), MUTED)
    _center(d, 111, f"hoje {panel.tokens} tok", _small(13), TEXT)
    return img


def fit_image(img: Image.Image) -> Image.Image:
    """Qualquer imagem → 128×128 RGB (corta para preencher, transparência vira preto)."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, rgba)
    return ImageOps.fit(img.convert("RGB"), (SIZE, SIZE), Image.LANCZOS)


def to_frame(img: Image.Image) -> p.Frame:
    img = fit_image(img) if img.size != (SIZE, SIZE) or img.mode != "RGB" else img
    return p.Frame(p.rgb565(img.tobytes()))
