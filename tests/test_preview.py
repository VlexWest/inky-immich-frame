import importlib.util
import pathlib

from tests.conftest import make_jpeg_bytes

_spec = importlib.util.spec_from_file_location(
    "preview", pathlib.Path(__file__).parent.parent / "tools" / "preview.py")
preview = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preview)


def test_four_labelled_variants_at_panel_size():
    vs = preview.variants(make_jpeg_bytes())
    assert [label for label, _ in vs][0].startswith("today")
    assert len(vs) == 4 and all(img.size == (800, 480) for _, img in vs)


def test_sheet_is_a_two_by_two_grid():
    vs = preview.variants(make_jpeg_bytes())
    s = preview.sheet(vs)
    assert s.size[0] == 1600 and s.size[1] > 960


def test_cli_writes_one_png_per_photo(tmp_path):
    photo = tmp_path / "a.jpg"
    photo.write_bytes(make_jpeg_bytes())
    preview.main([str(photo), "--out", str(tmp_path / "out")])
    assert (tmp_path / "out" / "a.png").exists()
