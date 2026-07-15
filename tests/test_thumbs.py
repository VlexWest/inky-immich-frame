import pytest

from inky_frame.thumbs import ThumbnailCache
from tests.conftest import FakeImmich


class CountingImmich(FakeImmich):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.downloads = 0

    def download_asset(self, asset_id, size="preview"):
        self.downloads += 1
        return super().download_asset(asset_id, size=size)


def test_first_get_downloads_and_stores(tmp_path):
    immich = CountingImmich(image_bytes=b"JPEGBYTES")
    cache = ThumbnailCache(immich, str(tmp_path))
    assert cache.get("a1") == b"JPEGBYTES"
    assert immich.downloads == 1
    assert (tmp_path / "thumbs" / "a1.jpg").read_bytes() == b"JPEGBYTES"


def test_second_get_comes_from_disk(tmp_path):
    """A 200-tile grid must not ask Immich again on every visit."""
    immich = CountingImmich(image_bytes=b"JPEGBYTES")
    cache = ThumbnailCache(immich, str(tmp_path))
    cache.get("a1")
    assert cache.get("a1") == b"JPEGBYTES"
    assert immich.downloads == 1


def test_it_asks_immich_for_the_thumbnail_size(tmp_path):
    seen = {}

    class SizeSpy(FakeImmich):
        def download_asset(self, asset_id, size="preview"):
            seen["size"] = size
            return b"X"

    ThumbnailCache(SizeSpy(), str(tmp_path)).get("a1")
    assert seen["size"] == "thumbnail"


def test_failure_propagates_and_stores_nothing(tmp_path):
    cache = ThumbnailCache(FakeImmich(fail_download=True), str(tmp_path))
    with pytest.raises(Exception):
        cache.get("a1")
    assert not (tmp_path / "thumbs" / "a1.jpg").exists()


def test_asset_id_cannot_escape_the_cache_dir(tmp_path):
    """asset_id arrives from the URL — it must not build a path outside."""
    cache = ThumbnailCache(FakeImmich(image_bytes=b"X"), str(tmp_path))
    with pytest.raises(ValueError):
        cache.get("../../etc/passwd")
