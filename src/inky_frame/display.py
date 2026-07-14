from typing import Protocol

from PIL import Image


class Display(Protocol):
    def show(self, image: Image.Image) -> None: ...


class FakeDisplay:
    """Test/dev display that just records the last image."""

    def __init__(self) -> None:
        self.last_image: Image.Image | None = None

    def show(self, image: Image.Image) -> None:
        self.last_image = image


class InkyDisplay:
    """Real Pimoroni Inky Impression. Imports the device library lazily so the
    rest of the app runs on a dev machine without the hardware."""

    def __init__(self, saturation: float = 0.5) -> None:
        from inky.auto import auto  # device-only import

        self._inky = auto()
        self._saturation = saturation

    def show(self, image: Image.Image) -> None:
        self._inky.set_image(image, saturation=self._saturation)
        self._inky.show()
