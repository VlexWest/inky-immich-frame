"""Dithering for the Spectra 6 panel (Inky Impression 7.3", E673).

The driver can dither too, but only against a palette that is half pure RGB
and half what the panel really shows, and it gets the photo with no range
mapping. Here the photo is squeezed into the panel's real tonal range first,
dithered against the blended measured palette, and handed over as a 6-colour
P image in the driver's pure colours, which the driver passes through as is.
"""
from PIL import Image

# Index order is the driver's: black, white, yellow, red, blue, green.
PURE = [(0, 0, 0), (255, 255, 255), (255, 255, 0), (255, 0, 0), (0, 0, 255), (0, 255, 0)]
MEASURED = [(0, 0, 0), (161, 164, 165), (208, 190, 71), (156, 72, 75), (61, 59, 94), (58, 91, 70)]


def blend_palette(saturation: float) -> list[tuple[int, int, int]]:
    """Same arithmetic as the driver's _palette_blend, int() truncation included."""
    s = min(1.0, max(0.0, float(saturation)))
    return [
        tuple(int(m * s + p * (1.0 - s)) for m, p in zip(meas, pure))
        for meas, pure in zip(MEASURED, PURE)
    ]


def _palette_image(colours) -> Image.Image:
    pal = Image.new("P", (1, 1))
    pal.putpalette([c for rgb in colours for c in rgb])
    return pal


def _fit_range(img: Image.Image, black, white) -> Image.Image:
    luts = []
    for b, w in zip(black, white):
        luts += [round(b + v * (w - b) / 255) for v in range(256)]
    return img.point(luts)


def to_panel(img: Image.Image, saturation: float = 0.5) -> Image.Image:
    palette = blend_palette(saturation)
    rgb = _fit_range(img.convert("RGB"), palette[0], palette[1])
    out = rgb.quantize(6, palette=_palette_image(palette), dither=Image.Dither.FLOYDSTEINBERG)
    out.putpalette([c for rgb_ in PURE for c in rgb_])
    return out


def simulate(panel_img: Image.Image) -> Image.Image:
    shown = panel_img.copy()
    shown.putpalette([c for rgb in MEASURED for c in rgb])
    return shown.convert("RGB")


def simulate_driver(img: Image.Image, saturation: float = 0.5) -> Image.Image:
    """What the frame shows today: the driver's own RGB path."""
    q = img.convert("RGB").quantize(
        6, palette=_palette_image(blend_palette(saturation)),
        dither=Image.Dither.FLOYDSTEINBERG,
    )
    return simulate(q)
