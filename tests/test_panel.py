from PIL import Image, ImageDraw

from inky_frame.panel import (
    MEASURED, PURE, blend_palette, simulate, simulate_driver, to_panel,
)


def _driver_indices(p_img):
    """The driver's P-mode path, copied from inky_e673.set_image (minus numpy)."""
    pal = Image.new("P", (1, 1))
    flat = [c for rgb in PURE + [(255, 255, 255)] for c in rgb]
    pal.putpalette(flat)
    dither = Image.Dither.NONE if len(p_img.palette.colors) == 6 else Image.Dither.FLOYDSTEINBERG
    return list(p_img.convert("RGB").quantize(6, palette=pal, dither=dither).get_flattened_data())


def _photo(w=160, h=96):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for x in range(w):
        for y in range(h):
            d.point((x, y), fill=(x * 255 // w, y * 255 // h, 255 - x * 255 // w))
    return img


def test_blend_matches_the_driver_arithmetic():
    assert blend_palette(0.5)[1] == (208, 209, 210)
    assert blend_palette(1.0) == MEASURED
    assert blend_palette(0.0) == PURE
    assert blend_palette(7) == MEASURED and blend_palette(-1) == PURE


def test_to_panel_returns_six_pure_colours():
    out = to_panel(_photo())
    assert out.mode == "P" and out.size == (160, 96)
    pal = out.getpalette()[:18]
    assert [tuple(pal[i:i + 3]) for i in range(0, 18, 3)] == PURE
    assert max(out.get_flattened_data()) <= 5


def test_driver_remap_keeps_every_index():
    """The driver re-quantizes P images against the pure palette; with pure
    colours in ours, every index must survive unchanged (blue stays blue)."""
    out = to_panel(_photo())
    assert _driver_indices(out) == list(out.get_flattened_data())


def test_pure_white_maps_to_solid_white():
    out = to_panel(Image.new("RGB", (40, 40), (255, 255, 255)))
    assert set(out.get_flattened_data()) == {1}


def test_pure_black_maps_to_solid_black():
    out = to_panel(Image.new("RGB", (40, 40), (0, 0, 0)))
    assert set(out.get_flattened_data()) == {0}


def test_a_blue_sky_contains_blue():
    out = to_panel(Image.new("RGB", (40, 40), (40, 70, 200)))
    assert 4 in set(out.get_flattened_data())


def test_simulate_shows_measured_colours():
    sim = simulate(to_panel(Image.new("RGB", (8, 8), (255, 255, 255))))
    assert sim.mode == "RGB" and sim.getpixel((0, 0)) == MEASURED[1]


def test_simulate_driver_is_rgb_in_measured_colours():
    sim = simulate_driver(_photo())
    assert sim.mode == "RGB" and sim.size == (160, 96)
    assert set(sim.get_flattened_data()) <= set(MEASURED)
