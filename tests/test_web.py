from inky_frame.config import Config, get_selected_album
from inky_frame.immich import Album
from inky_frame.web import create_app
from tests.conftest import FakeImmich


def _cfg(tmp_path):
    return Config(immich_url="http://x", api_key="k",
                  state_file=str(tmp_path / "state.json"),
                  cache_dir=str(tmp_path / "cache"))


def test_index_lists_albums(tmp_path):
    immich = FakeImmich(albums=[Album("a1", "Urlaub", "t1")])
    app = create_app(immich, _cfg(tmp_path))
    body = app.test_client().get("/").get_data(as_text=True)
    assert "Urlaub" in body
    assert "/thumb/t1" in body


def test_select_writes_state_and_calls_refresh(tmp_path):
    calls = []
    cfg = _cfg(tmp_path)
    app = create_app(FakeImmich(), cfg, on_refresh=lambda: calls.append(1))
    resp = app.test_client().post("/select", data={"album_id": "a9"})
    assert resp.status_code in (302, 303)
    assert get_selected_album(cfg.state_file) == "a9"
    assert calls == [1]


def test_select_redirects_even_if_refresh_fails(tmp_path):
    cfg = _cfg(tmp_path)

    def failing_refresh():
        raise RuntimeError("boom")

    app = create_app(FakeImmich(), cfg, on_refresh=failing_refresh)
    resp = app.test_client().post("/select", data={"album_id": "a9"})
    assert resp.status_code in (302, 303)
    assert get_selected_album(cfg.state_file) == "a9"


def test_thumb_proxies_immich_bytes(tmp_path):
    immich = FakeImmich(image_bytes=b"IMGBYTES")
    app = create_app(immich, _cfg(tmp_path))
    resp = app.test_client().get("/thumb/t1")
    assert resp.status_code == 200
    assert resp.data == b"IMGBYTES"
