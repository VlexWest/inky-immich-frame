import io
import os
import random
import threading

from PIL import Image, ImageOps

from .config import Config, get_selected_album
from .display import Display
from .immich import Asset, ImmichClient


def process_image(data: bytes, width: int, height: int) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    return ImageOps.fit(img, (width, height), method=Image.LANCZOS)


def pick_asset(assets: list[Asset], rng: random.Random) -> Asset | None:
    images = [a for a in assets if a.type == "IMAGE"]
    if not images:
        return None
    return rng.choice(images)


class Renderer:
    def __init__(
        self,
        immich: ImmichClient,
        display: Display,
        config: Config,
        rng: random.Random | None = None,
    ) -> None:
        self.immich = immich
        self.display = display
        self.config = config
        self.rng = rng or random.Random()
        self._lock = threading.Lock()

    def _cache_path(self) -> str:
        os.makedirs(self.config.cache_dir, exist_ok=True)
        return os.path.join(self.config.cache_dir, "last.png")

    def render_once(self) -> bool:
        with self._lock:
            cache_path = self._cache_path()
            try:
                album_id = get_selected_album(self.config.state_file)
                if not album_id:
                    raise RuntimeError("no album selected")
                assets = self.immich.get_album_assets(album_id)
                asset = pick_asset(assets, self.rng)
                if asset is None:
                    raise RuntimeError("album has no images")
                data = self.immich.download_asset(asset.id, size="preview")
                img = process_image(data, self.config.width, self.config.height)
                img.save(cache_path)
            except Exception:
                if not os.path.exists(cache_path):
                    raise
                img = Image.open(cache_path).convert("RGB")
            self.display.show(img)
            return True
