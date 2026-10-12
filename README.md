# inky-immich-frame

E-ink photo frame for a Raspberry Pi + Pimoroni Inky Impression 7.3" that shows
photos from an Immich album. Includes a phone-friendly album picker.

## Dev setup
```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## On the Pi
See `deploy/provision.md`.

## Comparing photo settings
`python tools/preview.py some.jpg --out preview` renders a photo four ways,
simulated with the panel's measured colours, so you can pick settings before
trying them on the frame.
