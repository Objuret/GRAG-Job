import sys

from tqdm import tqdm


def progress(*args, **kwargs):
    file = kwargs.setdefault("file", sys.stdout)
    kwargs.setdefault("ascii", True)
    kwargs.setdefault("dynamic_ncols", True)
    if "disable" not in kwargs:
        kwargs["disable"] = not getattr(file, "isatty", lambda: False)()
    return tqdm(*args, **kwargs)


def say(message: str) -> None:
    tqdm.write(message, file=sys.stdout)
    sys.stdout.flush()


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

    import contextlib

    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        say("a line")
    assert said.getvalue() == "a line\n"
    print("progress self-check OK")


if __name__ == "__main__":
    _selfcheck()
