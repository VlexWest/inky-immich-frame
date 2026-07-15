import random

import pytest
from PIL import Image

from inky_frame.config import Config, set_selected_album, set_pinned_asset
from inky_frame.display import FakeDisplay
from inky_frame.immich import Asset
from inky_frame.renderer import process_image, pick_asset, Renderer, request_scheduled_render
from tests.conftest import FakeImmich, make_jpeg_bytes


def _config(tmp_path):
    return Config(
        immich_url="http://x",
        api_key="k",
        cache_dir=str(tmp_path / "cache"),
        state_file=str(tmp_path / "state.json"),
    )


def test_process_image_fits_to_panel(jpeg_bytes):
    img = process_image(jpeg_bytes, 800, 480)
    assert img.size == (800, 480)
    assert img.mode == "RGB"


def test_pick_asset_ignores_video_and_is_seeded():
    assets = [Asset("v", "VIDEO"), Asset("a", "IMAGE"), Asset("b", "IMAGE")]
    chosen = pick_asset(assets, random.Random(0))
    assert chosen.type == "IMAGE"
    # deterministic with same seed
    assert pick_asset(assets, random.Random(0)).id == chosen.id


def test_pick_asset_none_when_no_images():
    assert pick_asset([Asset("v", "VIDEO")], random.Random(0)) is None


def test_render_once_success(tmp_path, image_assets):
    cfg = _config(tmp_path)
    set_selected_album(cfg.state_file, "album-1")
    immich = FakeImmich(assets=image_assets, image_bytes=make_jpeg_bytes())
    display = FakeDisplay()
    r = Renderer(immich, display, cfg, rng=random.Random(0))
    assert r.render_once() is True
    assert display.last_image.size == (800, 480)


def test_render_once_falls_back_to_cache_on_failure(tmp_path, image_assets):
    cfg = _config(tmp_path)
    set_selected_album(cfg.state_file, "album-1")
    display = FakeDisplay()
    # first: successful render populates the cache
    Renderer(FakeImmich(assets=image_assets, image_bytes=make_jpeg_bytes()),
             display, cfg, rng=random.Random(0)).render_once()
    # second: network fails -> must reuse cached image, not raise
    r2 = Renderer(FakeImmich(assets=image_assets, fail_download=True), FakeDisplay(), cfg)
    assert r2.render_once() is True


def test_render_once_raises_when_failure_and_no_cache(tmp_path, image_assets):
    cfg = _config(tmp_path)
    set_selected_album(cfg.state_file, "album-1")
    r = Renderer(FakeImmich(assets=image_assets, fail_download=True), FakeDisplay(), cfg)
    with pytest.raises(Exception):
        r.render_once()


class FakeWorker:
    def __init__(self):
        self.requests = 0

    def request(self):
        self.requests += 1
        return True


class RecordingImmich(FakeImmich):
    """Remembers which asset was actually downloaded."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.downloaded = []

    def download_asset(self, asset_id, size="preview"):
        self.downloaded.append(asset_id)
        return super().download_asset(asset_id, size=size)


def test_render_once_renders_the_pinned_asset(tmp_path, image_assets):
    cfg = _config(tmp_path)
    set_selected_album(cfg.state_file, "album-1")
    set_pinned_asset(cfg.state_file, "i2")
    immich = RecordingImmich(assets=image_assets, image_bytes=make_jpeg_bytes())
    r = Renderer(immich, FakeDisplay(), cfg, rng=random.Random(0))
    assert r.render_once() is True
    assert immich.downloaded == ["i2"]


def test_render_once_picks_at_random_when_nothing_is_pinned(tmp_path, image_assets):
    cfg = _config(tmp_path)
    set_selected_album(cfg.state_file, "album-1")
    immich = RecordingImmich(assets=image_assets, image_bytes=make_jpeg_bytes())
    r = Renderer(immich, FakeDisplay(), cfg, rng=random.Random(0))
    r.render_once()
    assert immich.downloaded[0] in {"i1", "i2"}


def test_is_pinned_reflects_state(tmp_path):
    cfg = _config(tmp_path)
    r = Renderer(FakeImmich(), FakeDisplay(), cfg)
    assert r.is_pinned() is False
    set_pinned_asset(cfg.state_file, "i1")
    assert r.is_pinned() is True


def test_scheduled_render_skips_while_pinned(tmp_path):
    """Redrawing an identical image costs 40s and e-ink cycles for nothing."""
    cfg = _config(tmp_path)
    set_pinned_asset(cfg.state_file, "i1")
    r = Renderer(FakeImmich(), FakeDisplay(), cfg)
    w = FakeWorker()
    assert request_scheduled_render(r, w) is False
    assert w.requests == 0


def test_scheduled_render_runs_when_rotating(tmp_path):
    cfg = _config(tmp_path)
    set_selected_album(cfg.state_file, "album-1")
    r = Renderer(FakeImmich(), FakeDisplay(), cfg)
    w = FakeWorker()
    assert request_scheduled_render(r, w) is True
    assert w.requests == 1


def _striped_jpeg(w, h):
    """A photo with a distinctive band at the very top and very bottom.
    A cover-crop of a portrait eats both; a contain-fit must keep them."""
    import io
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (w, h), (40, 90, 160))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, h // 12], fill=(255, 0, 0))            # top band
    d.rectangle([0, h - h // 12, w, h], fill=(0, 200, 0))        # bottom band
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _has_colour(img, want, tol=60):
    for px in img.convert("RGB").getcolors(maxcolors=1 << 24) or []:
        if all(abs(c - t) < tol for c, t in zip(px[1], want)):
            return True
    return False


def test_a_portrait_photo_is_never_cropped():
    """The panel is landscape. A portrait photo cannot fill it without losing
    something, and what it loses is faces - so nothing is cut at all."""
    img = process_image(_striped_jpeg(480, 800), 800, 480)
    assert img.size == (800, 480)
    assert _has_colour(img, (255, 0, 0)), "top of the photo was cropped away"
    assert _has_colour(img, (0, 200, 0)), "bottom of the photo was cropped away"


def test_a_portrait_photo_gets_white_bars_not_stretched():
    img = process_image(_striped_jpeg(480, 800), 800, 480)
    # the outer edges are the mat...
    assert img.getpixel((2, 240)) == (255, 255, 255)
    assert img.getpixel((797, 240)) == (255, 255, 255)
    # ...and the photo keeps its shape: its top band sits at the top, not stretched
    assert _has_colour(img, (255, 0, 0))


def test_a_landscape_photo_still_fills_the_panel():
    """5:3 is close to the panel's 5:3 - it should use the full width."""
    img = process_image(_striped_jpeg(1000, 600), 800, 480)
    assert img.size == (800, 480)
    assert img.getpixel((400, 240)) != (255, 255, 255)
    assert img.getpixel((2, 240)) != (255, 255, 255)


def test_background_defaults_to_the_white_mat():
    img = process_image(_striped_jpeg(480, 800), 800, 480)
    assert img.getpixel((2, 240)) == (255, 255, 255)


def test_blur_background_fills_the_bars_with_the_photo_itself():
    """InkyPi's approach: a blurred, cropped copy behind the whole photo."""
    img = process_image(_striped_jpeg(480, 800), 800, 480, background="blur")
    assert img.size == (800, 480)
    # the bars are no longer white...
    assert img.getpixel((2, 240)) != (255, 255, 255)
    assert img.getpixel((797, 240)) != (255, 255, 255)
    # ...and the photo itself is still complete, nothing cropped
    assert _has_colour(img, (255, 0, 0)), "top of the photo was cropped away"
    assert _has_colour(img, (0, 200, 0)), "bottom of the photo was cropped away"


def test_an_unknown_background_falls_back_to_white():
    """A typo in config.yaml must not blank the frame."""
    img = process_image(_striped_jpeg(480, 800), 800, 480, background="rainbow")
    assert img.getpixel((2, 240)) == (255, 255, 255)


def test_blur_leaves_a_fitting_photo_untouched():
    img = process_image(_striped_jpeg(1000, 600), 800, 480, background="blur")
    assert img.size == (800, 480)
