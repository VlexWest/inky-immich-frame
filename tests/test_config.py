import json
from inky_frame.config import (
    Config, load_config, get_selected_album, set_selected_album,
)


def test_load_config_reads_yaml_and_defaults(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text('immich_url: "http://x:2283"\napi_key: "k"\n')
    cfg = load_config(str(p))
    assert cfg.immich_url == "http://x:2283"
    assert cfg.api_key == "k"
    assert cfg.width == 800 and cfg.height == 480
    assert cfg.refresh_times == ["07:30", "12:30"]


def test_selected_album_missing_returns_none(tmp_path):
    assert get_selected_album(str(tmp_path / "nope.json")) is None


def test_selected_album_roundtrip(tmp_path):
    sf = str(tmp_path / "sub" / "state.json")
    set_selected_album(sf, "album-123")
    assert get_selected_album(sf) == "album-123"
    assert json.loads(open(sf).read())["album_id"] == "album-123"
