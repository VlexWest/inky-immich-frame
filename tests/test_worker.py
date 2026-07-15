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


def test_second_request_while_busy_is_rejected_but_coalesced_into_one_rerun():
    started = threading.Event()
    release = threading.Event()
    calls = []
    concurrent = 0
    max_concurrent = 0
    guard = threading.Lock()

    def render():
        nonlocal concurrent, max_concurrent
        with guard:
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
        calls.append(1)
        started.set()
        release.wait(timeout=5)
        with guard:
            concurrent -= 1

    w = RenderWorker(render)
    assert w.request() is True
    assert started.wait(timeout=2)
    assert w.status()["busy"] is True

    # a spammed second tap must not start a second render immediately,
    # and request() still returns False while busy...
    assert w.request() is False
    assert w.request() is False

    release.set()
    _wait_idle(w)
    # ...but it must not be silently dropped: exactly one more render runs
    # once the first finishes, and renders never overlap.
    assert calls == [1, 1]
    assert max_concurrent == 1


def test_a_single_request_while_busy_causes_exactly_one_more_render():
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

    assert w.request() is False

    release.set()
    _wait_idle(w)
    assert calls == [1, 1]  # not [1] (dropped) and not [1, 1, 1] (double-fired)


def test_repeated_requests_while_busy_collapse_into_a_single_rerun():
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

    # several taps while busy must collapse into a single extra render
    assert w.request() is False
    assert w.request() is False
    assert w.request() is False
    assert w.request() is False

    release.set()
    _wait_idle(w)
    assert calls == [1, 1]


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
