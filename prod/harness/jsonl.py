from __future__ import annotations

import json
from pathlib import Path


def load(path) -> list:
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
