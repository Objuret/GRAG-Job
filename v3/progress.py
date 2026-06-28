"""Stable CLI progress bars for the v3 harness."""
import sys

from tqdm import tqdm


def progress(*args, **kwargs):
    """tqdm tuned for Windows terminals and captured logs."""
    file = kwargs.setdefault("file", sys.stdout)
    kwargs.setdefault("ascii", True)
    kwargs.setdefault("dynamic_ncols", True)
    if "disable" not in kwargs:
        kwargs["disable"] = not getattr(file, "isatty", lambda: False)()
    return tqdm(*args, **kwargs)


def _selfcheck():
    import io

    captured = io.StringIO()
    bar = progress(total=1, desc="captured", unit="cell", file=captured)
    bar.update(1)
    bar.close()
    assert captured.getvalue() == ""

    tty = io.StringIO()
    tty.isatty = lambda: True
    bar = progress(total=1, desc="tty", unit="cell", file=tty)
    bar.update(1)
    bar.close()
    text = tty.getvalue()
    assert "#" in text and "\u2588" not in text
    print("progress self-check OK")


if __name__ == "__main__":
    _selfcheck()
