"""jsonl.py — the append-log reader every resumable stage shares.

A run's answers and its eval cells are appended one JSON object per line and
flushed as they land, so an interrupted write can leave a fragment at the end of
the file. That fragment is recoverable exactly once: the record it belonged to
was never finished, so dropping it costs nothing and the stage redoes it.

`load` drops a torn trailing line and raises on a parse error anywhere else,
where dropping would silently discard finished work. `heal` removes the fragment
from the file itself, which is what makes the next append safe — appending onto a
fragment welds two records into one unparseable line and turns a recoverable tail
into a permanent error the stage can never resume past.
"""
from __future__ import annotations

import json
from pathlib import Path


def load(path) -> list:
    """Records already in `path`, [] when it does not exist. A torn trailing line
    from a killed write is dropped; a parse error on any other line raises."""
    p = Path(path)
    if not p.is_file():
        return []
    lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    records = []
    for i, line in enumerate(lines):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                break
            raise
    return records


def heal(path) -> int:
    """Make `path` safe to append to, and report the bytes removed.

    A file whose last line parses but lacks its newline gets the newline. A file
    whose last line is a fragment is truncated back to the end of the last
    complete record. Anything already newline-terminated is untouched.
    """
    p = Path(path)
    if not p.is_file():
        return 0
    data = p.read_bytes()
    if not data or data.endswith(b"\n"):
        return 0
    cut = data.rfind(b"\n") + 1  # 0 when the file holds no newline at all
    tail = data[cut:]
    try:
        json.loads(tail.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        p.write_bytes(data[:cut])
        return len(tail)
    with p.open("ab") as fh:
        fh.write(b"\n")
    return 0


def _selfcheck():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.jsonl"

        p.write_bytes(b'{"id": 1}\n{"id": 2}\n')
        assert load(p) == [{"id": 1}, {"id": 2}]
        assert heal(p) == 0

        # torn tail: dropped by load, cut by heal, and the file stays appendable
        p.write_bytes(b'{"id": 1}\n{"id": 2')
        assert load(p) == [{"id": 1}]
        assert heal(p) == 8
        assert p.read_bytes() == b'{"id": 1}\n'
        with p.open("a", encoding="utf-8") as fh:
            fh.write('{"id": 3}\n')
        assert load(p) == [{"id": 1}, {"id": 3}]

        # CRLF is what the harness's own text-mode appends produce on Windows
        p.write_bytes(b'{"id": 1}\r\n{"id": 2')
        assert heal(p) == 8
        assert p.read_bytes() == b'{"id": 1}\r\n'
        assert load(p) == [{"id": 1}]

        # a complete last line missing only its newline keeps the record
        p.write_bytes(b'{"id": 1}\n{"id": 2}')
        assert heal(p) == 0
        assert p.read_bytes() == b'{"id": 1}\n{"id": 2}\n'

        # a fragment that is the only line leaves an empty, appendable file
        p.write_bytes(b'{"id": ')
        assert heal(p) == 7
        assert p.read_bytes() == b""

        # corruption that is NOT the tail is real damage and must raise
        p.write_bytes(b'{"id": 1\n{"id": 2}\n')
        try:
            load(p)
        except json.JSONDecodeError:
            pass
        else:
            raise AssertionError("mid-file corruption must raise")

        assert load(Path(d) / "missing.jsonl") == []
        assert heal(Path(d) / "missing.jsonl") == 0
    print("jsonl self-check OK", flush=True)


if __name__ == "__main__":
    _selfcheck()
