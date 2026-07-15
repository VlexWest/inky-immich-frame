import threading

from inky_frame.worker import RenderWorker


def test_request_runs_the_render_and_reports_idle_when_done():
    done = threading.Event()

    def render():
        done.set()

    w = RenderWorker(render)
    assert w.request() is True
    assert done.wait(timeout=2)
    _wait_idle(w)
    assert w.status() == {"busy": False, "error": None}


def test_second_request_while_busy_is_rejected_so_one_render_at_a_time():
    started = threading.Event()
    release = threading.Event()
    calls = []

    def render():
        calls.append(1)
        started.set()
        release.wait(timeout=5)

    w = RenderWorker(render)
    assert w.request() is True
    assert started.wait(timeout=2)
    assert w.status()["busy"] is True

    # a spammed second tap must not queue or start another render
    assert w.request() is False
    assert w.request() is False

    release.set()
    _wait_idle(w)
    assert calls == [1]


def test_error_is_captured_and_does_not_wedge_the_worker():
    def boom():
        raise RuntimeError("immich down")

    w = RenderWorker(boom)
    w.request()
    _wait_idle(w)
    assert w.status() == {"busy": False, "error": "immich down"}

    # worker still usable afterwards, and a good run clears the error
    ok = threading.Event()
    w2 = RenderWorker(ok.set)
    w2.request()
    assert ok.wait(timeout=2)
    _wait_idle(w2)
    assert w2.status()["error"] is None


def _wait_idle(worker, timeout=5.0):
    deadline = threading.Event()
    t = threading.Timer(timeout, deadline.set)
    t.start()
    try:
        while worker.status()["busy"] and not deadline.is_set():
            pass
        assert not worker.status()["busy"], "worker never went idle"
    finally:
        t.cancel()
