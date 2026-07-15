import json

from inky_frame.config import Config, get_language, get_pinned_asset, get_selected_album
from inky_frame.immich import Album
from inky_frame.web import create_app
from tests.conftest import FakeImmich


class FakeWorker:
    """Stand-in for RenderWorker: records requests, never blocks."""

    def __init__(self, busy=False, error=None, accept=True):
        self.requests = 0
        self._busy = busy
        self._error = error
        self._accept = accept

    def request(self):
        self.requests += 1
        return self._accept

    def status(self):
        return {"busy": self._busy, "error": self._error}


class FakeThumbs:
    def __init__(self, data=b"THUMB", fail=False):
        self._data = data
        self._fail = fail
        self.gets = []

    def get(self, asset_id):
        self.gets.append(asset_id)
        if self._fail:
            raise RuntimeError("immich unreachable")
        return self._data


def _cfg(tmp_path):
    return Config(immich_url="http://x", api_key="k",
                  state_file=str(tmp_path / "state.json"),
                  cache_dir=str(tmp_path / "cache"))


def test_index_lists_albums(tmp_path):
    immich = FakeImmich(albums=[Album("a1", "Urlaub", "t1")])
    app = create_app(immich, _cfg(tmp_path), FakeWorker(), FakeThumbs())
    body = app.test_client().get("/").get_data(as_text=True)
    assert "Urlaub" in body
    assert "/thumb/t1" in body


def test_select_writes_state_and_asks_for_a_render(tmp_path):
    cfg = _cfg(tmp_path)
    worker = FakeWorker()
    app = create_app(FakeImmich(), cfg, worker, FakeThumbs())
    resp = app.test_client().post("/select", data={"album_id": "a9"})
    assert resp.status_code in (302, 303)
    assert get_selected_album(cfg.state_file) == "a9"
    assert worker.requests == 1


def test_refresh_asks_for_a_render(tmp_path):
    worker = FakeWorker()
    app = create_app(FakeImmich(), _cfg(tmp_path), worker, FakeThumbs())
    resp = app.test_client().post("/refresh")
    assert resp.status_code in (302, 303)
    assert worker.requests == 1


def test_select_still_persists_when_worker_is_busy(tmp_path):
    cfg = _cfg(tmp_path)
    worker = FakeWorker(busy=True, accept=False)
    app = create_app(FakeImmich(), cfg, worker, FakeThumbs())
    resp = app.test_client().post("/select", data={"album_id": "a9"})
    assert resp.status_code in (302, 303)
    assert get_selected_album(cfg.state_file) == "a9"


def test_status_reports_worker_state_as_json(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(busy=True), FakeThumbs())
    resp = app.test_client().get("/status")
    assert resp.status_code == 200
    assert json.loads(resp.get_data(as_text=True)) == {"busy": True, "error": None}


def test_index_marks_busy_so_the_page_can_lock_the_buttons(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(busy=True), FakeThumbs())
    body = app.test_client().get("/").get_data(as_text=True)
    assert 'data-busy="true"' in body


def test_index_shows_a_friendly_message_when_the_last_render_failed(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(error="immich down"), FakeThumbs())
    body = app.test_client().get("/").get_data(as_text=True)
    assert "Bild konnte nicht geladen werden" in body
    # the raw technical error must not be shown to a non-technical reader
    assert "immich down" not in body


def test_thumb_proxies_the_cache_bytes(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(), FakeThumbs(data=b"IMGBYTES"))
    resp = app.test_client().get("/thumb/t1")
    assert resp.status_code == 200
    assert resp.data == b"IMGBYTES"


def test_page_is_german_by_default(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(), FakeThumbs())
    body = app.test_client().get("/").get_data(as_text=True)
    assert "Welches Album soll gezeigt werden?" in body
    assert '<html lang="de"' in body


def test_language_switch_persists_and_renders_russian(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker(), FakeThumbs()).test_client()
    resp = client.post("/language", data={"lang": "ru"})
    assert resp.status_code in (302, 303)
    assert get_language(cfg.state_file) == "ru"
    body = client.get("/").get_data(as_text=True)
    assert "Какой альбом показывать?" in body
    assert '<html lang="ru"' in body


def test_language_switch_to_english(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker(), FakeThumbs()).test_client()
    client.post("/language", data={"lang": "en"})
    body = client.get("/").get_data(as_text=True)
    assert "Which album should be shown?" in body


def test_unknown_language_is_ignored(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker(), FakeThumbs()).test_client()
    client.post("/language", data={"lang": "../etc/passwd"})
    assert get_language(cfg.state_file) == "de"
    assert "Welches Album soll gezeigt werden?" in client.get("/").get_data(as_text=True)


def test_switcher_offers_all_three_languages(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(), FakeThumbs())
    body = app.test_client().get("/").get_data(as_text=True)
    for label in ("Deutsch", "English", "Русский"):
        assert label in body


def test_language_choice_survives_picking_an_album(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker(), FakeThumbs()).test_client()
    client.post("/language", data={"lang": "ru"})
    client.post("/select", data={"album_id": "a9"})
    assert get_language(cfg.state_file) == "ru"
    assert get_selected_album(cfg.state_file) == "a9"


def test_index_survives_immich_being_unreachable(tmp_path):
    """The frame lives on a home network; the server it pulls from may be down,
    or the wifi may be broken. The picker must still answer, not 500."""
    app = create_app(FakeImmich(fail_list=True), _cfg(tmp_path), FakeWorker(), FakeThumbs())
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Fotos sind gerade nicht erreichbar" in body
    # no raw exception text leaks to a non-technical reader
    assert "immich unreachable" not in body
    assert "Traceback" not in body


def test_offline_message_is_translated(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(fail_list=True), cfg, FakeWorker(), FakeThumbs()).test_client()
    client.post("/language", data={"lang": "ru"})
    body = client.get("/").get_data(as_text=True)
    assert "Фотографии сейчас недоступны" in body


def test_thumb_returns_placeholder_when_the_cache_fails(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(), FakeThumbs(fail=True))
    resp = app.test_client().get("/thumb/t1")
    assert resp.status_code == 404  # must not be a 500


def test_index_is_never_cached(tmp_path):
    """The page carries live state (busy, selected album). A cached copy shows a
    stale 'loading' banner forever, because the reload serves the cache too."""
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(), FakeThumbs())
    resp = app.test_client().get("/")
    assert "no-store" in resp.headers.get("Cache-Control", "")


def test_status_is_never_cached(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(), FakeThumbs())
    resp = app.test_client().get("/status")
    assert "no-store" in resp.headers.get("Cache-Control", "")


def test_album_screen_lists_the_photos(tmp_path, image_assets):
    immich = FakeImmich(albums=[Album("a1", "Urlaub", "t1")], assets=image_assets)
    app = create_app(immich, _cfg(tmp_path), FakeWorker(), FakeThumbs())
    body = app.test_client().get("/album/a1").get_data(as_text=True)
    assert "/thumb/i1" in body and "/thumb/i2" in body
    assert 'loading="lazy"' in body
    assert "Urlaub" in body


def test_album_screen_offers_rotation(tmp_path, image_assets):
    immich = FakeImmich(albums=[Album("a1", "Urlaub", "t1")], assets=image_assets)
    app = create_app(immich, _cfg(tmp_path), FakeWorker(), FakeThumbs())
    body = app.test_client().get("/album/a1").get_data(as_text=True)
    assert "Bilder wechseln lassen" in body


def test_pin_sets_state_and_asks_for_a_render(tmp_path):
    cfg = _cfg(tmp_path)
    worker = FakeWorker()
    app = create_app(FakeImmich(), cfg, worker, FakeThumbs())
    resp = app.test_client().post("/pin", data={"album_id": "a1", "asset_id": "i2"})
    assert resp.status_code in (302, 303)
    assert get_pinned_asset(cfg.state_file) == "i2"
    assert get_selected_album(cfg.state_file) == "a1"
    assert worker.requests == 1


def test_selecting_an_album_releases_the_pin(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker(), FakeThumbs()).test_client()
    client.post("/pin", data={"album_id": "a1", "asset_id": "i2"})
    client.post("/select", data={"album_id": "a1"})
    assert get_pinned_asset(cfg.state_file) is None


def test_album_screen_marks_the_pinned_photo(tmp_path, image_assets):
    cfg = _cfg(tmp_path)
    immich = FakeImmich(albums=[Album("a1", "Urlaub", "t1")], assets=image_assets)
    client = create_app(immich, cfg, FakeWorker(), FakeThumbs()).test_client()
    client.post("/pin", data={"album_id": "a1", "asset_id": "i2"})
    body = client.get("/album/a1").get_data(as_text=True)
    assert body.count("card sel") == 1


def test_thumb_uses_the_cache(tmp_path):
    thumbs = FakeThumbs(data=b"CACHED")
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(), thumbs)
    resp = app.test_client().get("/thumb/i1")
    assert resp.data == b"CACHED"
    assert thumbs.gets == ["i1"]


def test_album_screen_survives_immich_being_unreachable(tmp_path):
    app = create_app(FakeImmich(fail_list=True), _cfg(tmp_path), FakeWorker(), FakeThumbs())
    resp = app.test_client().get("/album/a1")
    assert resp.status_code == 200
    assert "Fotos sind gerade nicht erreichbar" in resp.get_data(as_text=True)


def test_album_screen_is_translated(tmp_path, image_assets):
    cfg = _cfg(tmp_path)
    immich = FakeImmich(albums=[Album("a1", "Urlaub", "t1")], assets=image_assets)
    client = create_app(immich, cfg, FakeWorker(), FakeThumbs()).test_client()
    client.post("/language", data={"lang": "ru"})
    body = client.get("/album/a1").get_data(as_text=True)
    assert "Пусть фото меняются" in body
