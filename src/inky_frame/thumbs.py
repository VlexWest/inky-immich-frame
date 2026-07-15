import os
import re
import threading

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class ThumbnailCache:
    """Disk-backed thumbnails.

    An album screen shows 50-200 tiles, and each one is proxied
    phone -> Pi -> Immich. Keeping them on disk means Immich is asked once per
    photo, ever, instead of once per visit.
    """

    def __init__(self, immich, cache_dir: str) -> None:
        self._immich = immich
        self._dir = os.path.join(cache_dir, "thumbs")

    def _path(self, asset_id: str) -> str:
        if not _SAFE_ID.match(asset_id):
            raise ValueError(f"unsafe asset id: {asset_id!r}")
        return os.path.join(self._dir, f"{asset_id}.jpg")

    def get(self, asset_id: str) -> bytes:
        path = self._path(asset_id)
        try:
            with open(path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            pass

        data = self._immich.download_asset(asset_id, size="thumbnail")
        os.makedirs(self._dir, exist_ok=True)
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)   # never leave a half-written tile behind
        return data
