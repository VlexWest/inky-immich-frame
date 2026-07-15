import json
from inky_frame.config import (
    Config, load_config, get_selected_album, set_selected_album,
    get_language, set_language, get_pinned_asset, set_pinned_asset,
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


def test_language_defaults_to_german(tmp_path):
    assert get_language(str(tmp_path / "nope.json")) == "de"


def test_language_roundtrip(tmp_path):
    sf = str(tmp_path / "state.json")
    set_language(sf, "ru")
    assert get_language(sf) == "ru"


def test_language_and_album_do_not_clobber_each_other(tmp_path):
    sf = str(tmp_path / "state.json")
    set_selected_album(sf, "album-123")
    set_language(sf, "ru")
    assert get_selected_album(sf) == "album-123"
    assert get_language(sf) == "ru"

    # and the other way round: picking an album must keep the language
    set_selected_album(sf, "album-456")
    assert get_language(sf) == "ru"
    assert get_selected_album(sf) == "album-456"


def test_pinned_asset_defaults_to_none(tmp_path):
    assert get_pinned_asset(str(tmp_path / "nope.json")) is None


def test_pinned_asset_roundtrip(tmp_path):
    sf = str(tmp_path / "state.json")
    set_pinned_asset(sf, "asset-1")
    assert get_pinned_asset(sf) == "asset-1"


def test_selecting_an_album_clears_the_pin(tmp_path):
    """Tapping an album is how the reader gets back to a rotating frame."""
    sf = str(tmp_path / "state.json")
    set_selected_album(sf, "album-1")
    set_pinned_asset(sf, "asset-1")
    set_selected_album(sf, "album-2")
    assert get_selected_album(sf) == "album-2"
    assert get_pinned_asset(sf) is None


def test_pinning_keeps_album_and_language(tmp_path):
    sf = str(tmp_path / "state.json")
    set_selected_album(sf, "album-1")
    set_language(sf, "ru")
    set_pinned_asset(sf, "asset-1")
    assert get_selected_album(sf) == "album-1"
    assert get_language(sf) == "ru"
    assert get_pinned_asset(sf) == "asset-1"
