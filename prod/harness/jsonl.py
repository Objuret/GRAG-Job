from __future__ import annotations

import json
from pathlib import Path


def iter_records(path):
    """Yield records, ignoring blank lines and an invalid final nonblank line."""
    p = Path(path)
    if not p.is_file():
        return
    invalid_tail = None
    with p.open(encoding="utf-8") as fh:
        for physical_line in fh:
            # Match the existing splitlines behavior, including Unicode separators.
            for line in physical_line.splitlines():
                if not line.strip():
                    continue
                if invalid_tail is not None:
                    raise invalid_tail
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    # It is a tolerated torn tail only if no later record follows.
                    invalid_tail = error
                else:
                    yield record


def load(path) -> list:
    return list(iter_records(path))


def heal(path) -> int:
    p = Path(path)
    if not p.is_file():
        return 0
    data = p.read_bytes()
    if not data or data.endswith(b"\n"):
        return 0
    cut = data.rfind(b"\n") + 1
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

        p.write_bytes(b'{"id": 1}\n{"id": 2')
        assert load(p) == [{"id": 1}]
        assert heal(p) == 8
        assert p.read_bytes() == b'{"id": 1}\n'
        with p.open("a", encoding="utf-8") as fh:
            fh.write('{"id": 3}\n')
        assert load(p) == [{"id": 1}, {"id": 3}]

        p.write_bytes(b'{"id": 1}\r\n{"id": 2')
        assert heal(p) == 8
        assert p.read_bytes() == b'{"id": 1}\r\n'
        assert load(p) == [{"id": 1}]

        p.write_bytes(b'{"id": 1}\n{"id": 2}')
        assert heal(p) == 0
        assert p.read_bytes() == b'{"id": 1}\n{"id": 2}\n'

        p.write_bytes(b'{"id": ')
        assert heal(p) == 7
        assert p.read_bytes() == b""

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
