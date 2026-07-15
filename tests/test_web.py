import json

from inky_frame.config import Config, get_language, get_selected_album
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


def _cfg(tmp_path):
    return Config(immich_url="http://x", api_key="k",
                  state_file=str(tmp_path / "state.json"),
                  cache_dir=str(tmp_path / "cache"))


def test_index_lists_albums(tmp_path):
    immich = FakeImmich(albums=[Album("a1", "Urlaub", "t1")])
    app = create_app(immich, _cfg(tmp_path), FakeWorker())
    body = app.test_client().get("/").get_data(as_text=True)
    assert "Urlaub" in body
    assert "/thumb/t1" in body


def test_select_writes_state_and_asks_for_a_render(tmp_path):
    cfg = _cfg(tmp_path)
    worker = FakeWorker()
    app = create_app(FakeImmich(), cfg, worker)
    resp = app.test_client().post("/select", data={"album_id": "a9"})
    assert resp.status_code in (302, 303)
    assert get_selected_album(cfg.state_file) == "a9"
    assert worker.requests == 1


def test_refresh_asks_for_a_render(tmp_path):
    worker = FakeWorker()
    app = create_app(FakeImmich(), _cfg(tmp_path), worker)
    resp = app.test_client().post("/refresh")
    assert resp.status_code in (302, 303)
    assert worker.requests == 1


def test_select_still_persists_when_worker_is_busy(tmp_path):
    cfg = _cfg(tmp_path)
    worker = FakeWorker(busy=True, accept=False)
    app = create_app(FakeImmich(), cfg, worker)
    resp = app.test_client().post("/select", data={"album_id": "a9"})
    assert resp.status_code in (302, 303)
    assert get_selected_album(cfg.state_file) == "a9"


def test_status_reports_worker_state_as_json(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(busy=True))
    resp = app.test_client().get("/status")
    assert resp.status_code == 200
    assert json.loads(resp.get_data(as_text=True)) == {"busy": True, "error": None}


def test_index_marks_busy_so_the_page_can_lock_the_buttons(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(busy=True))
    body = app.test_client().get("/").get_data(as_text=True)
    assert 'data-busy="true"' in body


def test_index_shows_a_friendly_message_when_the_last_render_failed(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker(error="immich down"))
    body = app.test_client().get("/").get_data(as_text=True)
    assert "Bild konnte nicht geladen werden" in body
    # the raw technical error must not be shown to a non-technical reader
    assert "immich down" not in body


def test_thumb_proxies_immich_bytes(tmp_path):
    immich = FakeImmich(image_bytes=b"IMGBYTES")
    app = create_app(immich, _cfg(tmp_path), FakeWorker())
    resp = app.test_client().get("/thumb/t1")
    assert resp.status_code == 200
    assert resp.data == b"IMGBYTES"


def test_page_is_german_by_default(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker())
    body = app.test_client().get("/").get_data(as_text=True)
    assert "Welches Album soll gezeigt werden?" in body
    assert '<html lang="de"' in body


def test_language_switch_persists_and_renders_russian(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker()).test_client()
    resp = client.post("/language", data={"lang": "ru"})
    assert resp.status_code in (302, 303)
    assert get_language(cfg.state_file) == "ru"
    body = client.get("/").get_data(as_text=True)
    assert "Какой альбом показывать?" in body
    assert '<html lang="ru"' in body


def test_language_switch_to_english(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker()).test_client()
    client.post("/language", data={"lang": "en"})
    body = client.get("/").get_data(as_text=True)
    assert "Which album should be shown?" in body


def test_unknown_language_is_ignored(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker()).test_client()
    client.post("/language", data={"lang": "../etc/passwd"})
    assert get_language(cfg.state_file) == "de"
    assert "Welches Album soll gezeigt werden?" in client.get("/").get_data(as_text=True)


def test_switcher_offers_all_three_languages(tmp_path):
    app = create_app(FakeImmich(), _cfg(tmp_path), FakeWorker())
    body = app.test_client().get("/").get_data(as_text=True)
    for label in ("Deutsch", "English", "Русский"):
        assert label in body


def test_language_choice_survives_picking_an_album(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(), cfg, FakeWorker()).test_client()
    client.post("/language", data={"lang": "ru"})
    client.post("/select", data={"album_id": "a9"})
    assert get_language(cfg.state_file) == "ru"
    assert get_selected_album(cfg.state_file) == "a9"


def test_index_survives_immich_being_unreachable(tmp_path):
    """The frame lives on a home network; the server it pulls from may be down,
    or the wifi may be broken. The picker must still answer, not 500."""
    app = create_app(FakeImmich(fail_list=True), _cfg(tmp_path), FakeWorker())
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Fotos sind gerade nicht erreichbar" in body
    # no raw exception text leaks to a non-technical reader
    assert "immich unreachable" not in body
    assert "Traceback" not in body


def test_offline_message_is_translated(tmp_path):
    cfg = _cfg(tmp_path)
    client = create_app(FakeImmich(fail_list=True), cfg, FakeWorker()).test_client()
    client.post("/language", data={"lang": "ru"})
    body = client.get("/").get_data(as_text=True)
    assert "Фотографии сейчас недоступны" in body


def test_thumb_returns_placeholder_when_immich_is_down(tmp_path):
    app = create_app(FakeImmich(fail_download=True), _cfg(tmp_path), FakeWorker())
    resp = app.test_client().get("/thumb/t1")
    assert resp.status_code in (200, 404)  # must not be a 500
