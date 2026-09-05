import threading
import time

_flag = threading.Event()


class Aborted(RuntimeError):
    pass


def aborted() -> bool:
    return _flag.is_set()


def watch() -> None:
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
