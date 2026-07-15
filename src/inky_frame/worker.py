import threading
from typing import Callable


class RenderWorker:
    """Runs a render off the request thread, one at a time.

    An e-ink refresh takes ~40s. Doing it inside a request would hang the
    browser long enough that it gives up, so requests only ever ask for a
    render and return immediately. While one is running further requests are
    rejected rather than queued: a repeated tap means "show me a picture",
    which the in-flight render already satisfies.
    """

    def __init__(self, render: Callable[[], object]) -> None:
        self._render = render
        self._lock = threading.Lock()
        self._busy = False
        self._error: str | None = None

    def request(self) -> bool:
        """Start a render. Returns False if one is already running."""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self._error = None
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def status(self) -> dict:
        with self._lock:
            return {"busy": self._busy, "error": self._error}

    def _run(self) -> None:
        error = None
        try:
            self._render()
        except Exception as exc:
            error = str(exc)
        finally:
            with self._lock:
                self._error = error
                self._busy = False
