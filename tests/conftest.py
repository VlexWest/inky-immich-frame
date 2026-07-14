import io

import pytest
from PIL import Image

from inky_frame.immich import Asset


def make_jpeg_bytes(w=1200, h=800, color=(120, 60, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def jpeg_bytes():
    return make_jpeg_bytes()


class FakeImmich:
    """Duck-typed stand-in for ImmichClient."""

    def __init__(self, assets=None, image_bytes=b"", fail_download=False,
                 albums=None):
        self._assets = assets or []
        self._image_bytes = image_bytes
        self._fail_download = fail_download
        self._albums = albums or []

    def list_albums(self):
        return self._albums

    def get_album_assets(self, album_id):
        return self._assets

    def download_asset(self, asset_id, size="preview"):
        if self._fail_download:
            raise RuntimeError("network down")
        return self._image_bytes


@pytest.fixture
def image_assets():
    return [Asset(id="i1", type="IMAGE"), Asset(id="i2", type="IMAGE")]
