"""abort.py — press 'q' to stop a running gen/eval loop.

Ctrl+C can be swallowed mid network-call inside the thread pool (the main thread is
blocked in fut.result() and the workers aren't daemons), so it doesn't reliably stop
a long run. This gives a dependable graceful stop: a watcher thread sets a flag, the
gen and eval loops check it each item and bail — finished work is already flushed to
disk, so nothing is lost and the run resumes later.
"""
import threading
import time

_flag = threading.Event()


class Aborted(RuntimeError):
    """Raised from inside an in-flight call when q has been pressed, so a worker
    parked in a long NIM fan-out unwinds at once instead of running to the end."""


def aborted() -> bool:
    return _flag.is_set()


def watch() -> None:
    """Start a daemon thread that sets the abort flag when q/Q is pressed. No-op
    where msvcrt is unavailable (non-Windows) — there Ctrl+C stays the fallback."""
    try:
        import msvcrt
    except ImportError:
        return

    def _loop():
        while not _flag.is_set():
            if msvcrt.kbhit() and msvcrt.getch() in (b"q", b"Q"):
                _flag.set()
                print("\n[q] abort requested - finishing the current item, then stopping.")
                return
            time.sleep(0.1)

    threading.Thread(target=_loop, daemon=True).start()
