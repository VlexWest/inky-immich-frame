from PIL import Image
from inky_frame.display import FakeDisplay


def test_fake_display_records_last_image():
    d = FakeDisplay()
    assert d.last_image is None
    img = Image.new("RGB", (800, 480), "white")
    d.show(img)
    assert d.last_image is img
