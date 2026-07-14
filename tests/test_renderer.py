import random

import pytest
from PIL import Image

from inky_frame.config import Config, set_selected_album
from inky_frame.display import FakeDisplay
from inky_frame.immich import Asset
from inky_frame.renderer import process_image, pick_asset, Renderer
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
