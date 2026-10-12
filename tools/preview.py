"""Render photos the way the frame would show them, side by side.

    python tools/preview.py photo.jpg more/*.jpg --out preview

Simulated with the colours Pimoroni measured on the panel, so it is close to
the real thing but not identical; check the winner on the frame itself.
"""
import argparse
import pathlib

from PIL import Image, ImageDraw

from inky_frame.panel import simulate, simulate_driver, to_panel
from inky_frame.renderer import process_image
from inky_frame.tone import NEUTRAL, ToneParams

W, H, LABEL = 800, 480, 28


def variants(data: bytes, background: str = "white") -> list[tuple[str, Image.Image]]:
    plain = process_image(data, W, H, background, tone=NEUTRAL)
    toned = process_image(data, W, H, background, tone=ToneParams())
    return [
        ("today: driver, sat 0.5", simulate_driver(plain, 0.5)),
        ("panel, sat 0.5, no tone", simulate(to_panel(plain, 0.5))),
        ("panel, sat 0.5, tone", simulate(to_panel(toned, 0.5))),
        ("panel, sat 1.0, tone", simulate(to_panel(toned, 1.0))),
    ]


def sheet(panels: list[tuple[str, Image.Image]]) -> Image.Image:
    out = Image.new("RGB", (2 * W, 2 * (H + LABEL)), "white")
    draw = ImageDraw.Draw(out)
    for i, (label, img) in enumerate(panels):
        x, y = (i % 2) * W, (i // 2) * (H + LABEL)
        draw.text((x + 8, y + 8), label, fill="black")
        out.paste(img, (x, y + LABEL))
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photos", nargs="+")
    parser.add_argument("--out", default="preview")
    parser.add_argument("--background", default="white", choices=["white", "blur", "fill"])
    args = parser.parse_args(argv)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for photo in args.photos:
        path = pathlib.Path(photo)
        sheet(variants(path.read_bytes(), args.background)).save(out_dir / f"{path.stem}.png")
        print(out_dir / f"{path.stem}.png")


if __name__ == "__main__":
    main()
