import io
import os
import random
import threading

from PIL import Image, ImageFilter, ImageOps

from .config import Config, get_pinned_asset, get_selected_album
from .display import Display
from .immich import Asset, ImmichClient


MAT_COLOUR = (255, 255, 255)
BLUR_RADIUS = 8


def _pad_blur(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Fill the leftover with a blurred, cropped copy of the photo itself."""
    bkg = ImageOps.fit(img, size, method=Image.LANCZOS)
    bkg = bkg.filter(ImageFilter.BoxBlur(BLUR_RADIUS))
    fitted = ImageOps.contain(img, size, method=Image.LANCZOS)
    bkg.paste(
        fitted,
        ((size[0] - fitted.size[0]) // 2, (size[1] - fitted.size[1]) // 2),
    )
    return bkg


def process_image(
    data: bytes, width: int, height: int, background: str = "white"
) -> Image.Image:
    """Fit the whole photo onto the panel, filling what's left over.

    The panel is landscape; a portrait photo cannot fill it without losing
    height, and the height it loses is where faces are. So nothing is ever
    cropped — the leftover is either a white mat, the way a real picture frame
    does it, or a blurred copy of the photo behind it.

    An unrecognised `background` falls back to the mat rather than raising: a
    typo in config.yaml must not leave the frame blank.
    """
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if background == "blur":
        return _pad_blur(img, (width, height))
    return ImageOps.pad(
        img, (width, height), method=Image.LANCZOS, color=MAT_COLOUR
    )


def pick_asset(assets: list[Asset], rng: random.Random) -> Asset | None:
    images = [a for a in assets if a.type == "IMAGE"]
    if not images:
        return None
    return rng.choice(images)


def request_scheduled_render(renderer: "Renderer", worker) -> bool:
    """Scheduler entry point.

    While a photo is pinned the frame is meant to stay put, so the scheduled
    render is skipped rather than redrawing the identical image.
    """
    if renderer.is_pinned():
        return False
    worker.request()
    return True


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

    def is_pinned(self) -> bool:
        return get_pinned_asset(self.config.state_file) is not None

    def render_once(self) -> bool:
        with self._lock:
            cache_path = self._cache_path()
            try:
                album_id = get_selected_album(self.config.state_file)
                if not album_id:
                    raise RuntimeError("no album selected")
                pinned = get_pinned_asset(self.config.state_file)
                if pinned:
                    asset_id = pinned
                else:
                    assets = self.immich.get_album_assets(album_id)
                    asset = pick_asset(assets, self.rng)
                    if asset is None:
                        raise RuntimeError("album has no images")
                    asset_id = asset.id
                data = self.immich.download_asset(asset_id, size="preview")
                img = process_image(
                    data, self.config.width, self.config.height,
                    background=self.config.background,
                )
                img.save(cache_path)
            except Exception:
                if not os.path.exists(cache_path):
                    raise
                img = Image.open(cache_path).convert("RGB")
            self.display.show(img)
            return True
