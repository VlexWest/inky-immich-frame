from PIL import Image, ImageDraw

from inky_frame.tone import NEUTRAL, ToneParams, enhance


def _gradient(w=200, h=100):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for x in range(w):
        v = 60 + x * 120 // w  # a dull, low-contrast ramp 60..179
        d.line([(x, 0), (x, h)], fill=(v, v // 2 + 30, 200 - v // 2))
    return img


def test_neutral_params_leave_the_photo_untouched():
    img = _gradient()
    assert list(enhance(img, NEUTRAL).get_flattened_data()) == list(img.get_flattened_data())


def test_enhance_keeps_size_and_mode_and_does_not_mutate():
    img = _gradient()
    before = img.copy()
    out = enhance(img)
    assert out.size == img.size and out.mode == "RGB"
    assert list(img.get_flattened_data()) == list(before.get_flattened_data())


def test_autocontrast_stretches_a_dull_photo():
    out = enhance(_gradient(), ToneParams(cutoff=1.0, colour=1.0, gamma=1.0, sharpen=0))
    lo, hi = out.convert("L").getextrema()
    assert lo < 40 and hi > 190


def test_colour_boost_increases_saturation():
    img = _gradient()
    plain = enhance(img, ToneParams(cutoff=0.0, colour=1.0, gamma=1.0, sharpen=0))
    boosted = enhance(img, ToneParams(cutoff=0.0, colour=1.5, gamma=1.0, sharpen=0))
    sat = lambda im: sum(px[1] for px in im.convert("HSV").get_flattened_data())
    assert sat(boosted) > sat(plain)


def test_gamma_above_one_brightens_midtones():
    img = Image.new("RGB", (10, 10), (100, 100, 100))
    out = enhance(img, ToneParams(cutoff=0.0, colour=1.0, gamma=1.4, sharpen=0))
    assert out.getpixel((5, 5))[0] > 100


def test_a_flat_single_colour_photo_does_not_raise():
    img = Image.new("RGB", (50, 50), (90, 90, 90))
    assert enhance(img).size == (50, 50)
