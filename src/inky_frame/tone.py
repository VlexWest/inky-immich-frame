"""Photo preparation for a six-colour e-ink panel.

The panel has very little dynamic range and dithering softens every edge, so a
photo straight from the camera comes out flat and muddy. These are the usual
darkroom fixes, applied before dithering.
"""
from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


@dataclass(frozen=True)
class ToneParams:
    cutoff: float = 1.0   # % of darkest/brightest pixels clipped by autocontrast
    colour: float = 1.3   # 1.0 = unchanged saturation
    gamma: float = 1.0    # >1 brightens midtones
    sharpen: int = 60     # UnsharpMask percent, 0 = off


NEUTRAL = ToneParams(cutoff=0.0, colour=1.0, gamma=1.0, sharpen=0)


def enhance(img: Image.Image, params: ToneParams = ToneParams()) -> Image.Image:
    out = img.convert("RGB")
    if params.cutoff > 0:
        # preserve_tone stretches luminance only, so a sunset stays orange
        # instead of being colour-balanced to grey.
        out = ImageOps.autocontrast(out, cutoff=params.cutoff, preserve_tone=True)
    if params.colour != 1.0:
        out = ImageEnhance.Color(out).enhance(params.colour)
    if params.gamma != 1.0:
        lut = [round(255 * (i / 255) ** (1 / params.gamma)) for i in range(256)]
        out = out.point(lut * 3)
    if params.sharpen > 0:
        out = out.filter(ImageFilter.UnsharpMask(radius=1.5, percent=params.sharpen, threshold=2))
    return out
