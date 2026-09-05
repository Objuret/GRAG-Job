from __future__ import annotations

import hashlib
import platform
import socket
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent

TRACKED_PACKAGES = ("bm25s", "PyStemmer", "numpy", "sentence-transformers", "torch",
                    "transformers", "httpx", "ragas", "neo4j")


def code_version() -> dict:
    def git(*args):
        try:
            out = subprocess.run(("git", *args), cwd=str(_REPO), capture_output=True,
                                 text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain")
    return {
        "commit": commit,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": None if status is None else bool(status.strip()),
    }


def embedder() -> dict:
    from harness.embed import EMBED_DEVICE, EMBED_DTYPE, EMBED_MODEL, EMBED_REVISION

    return {"model": EMBED_MODEL, "revision": EMBED_REVISION,
            "device": EMBED_DEVICE, "dtype": EMBED_DTYPE}


def environment() -> dict:
    from importlib.metadata import PackageNotFoundError, version

    packages = {}
    for name in TRACKED_PACKAGES:
        try:
            packages[name] = version(name)
        except (PackageNotFoundError, ValueError, OSError):
            packages[name] = None
    return {
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "packages": packages,
        "embedder": embedder(),
    }


def file_digest(path) -> str | None:
    p = Path(path) if path else None
    if not p or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree_digest(root, patterns=("**/*.json",)) -> dict | None:
    r = Path(root) if root else None
    if not r or not r.is_dir():
        return None
    files = sorted({p for pat in patterns for p in r.glob(pat) if p.is_file()})
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(r).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update((file_digest(p) or "").encode("utf-8"))
        h.update(b"\n")
    return {"sha256": h.hexdigest(), "n_files": len(files)}


def inputs(questions_file=None, ids_file=None, corpus_root=None) -> dict:
    return {
        "questions_sha256": file_digest(questions_file),
        "ids_sha256": file_digest(ids_file),
        "corpus": tree_digest(corpus_root),
    }


def _selfcheck():
    import tempfile

    cv = code_version()
    assert set(cv) == {"commit", "branch", "dirty"}
    env = environment()
    assert env["python"] and set(TRACKED_PACKAGES) <= set(env["packages"])
    assert set(env["embedder"]) == {"model", "revision", "device", "dtype"}
    assert all(env["embedder"].values())

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "a.json").write_text('{"x": 1}', encoding="utf-8")
        (root / "sub").mkdir()
        (root / "sub" / "b.json").write_text('{"y": 2}', encoding="utf-8")
        first = tree_digest(root)
        assert first["n_files"] == 2

        assert tree_digest(root) == first
        (root / "a.json").write_text('{"x": 2}', encoding="utf-8")
        assert tree_digest(root)["sha256"] != first["sha256"]
        (root / "a.json").write_text('{"x": 1}', encoding="utf-8")
        assert tree_digest(root) == first
        (root / "a.json").rename(root / "c.json")
        assert tree_digest(root)["sha256"] != first["sha256"]

        assert tree_digest(root / "nope") is None
        assert file_digest(root / "nope.json") is None
        assert file_digest(None) is None

        blank = inputs()
        assert blank == {"questions_sha256": None, "ids_sha256": None, "corpus": None}
    print("provenance self-check OK", flush=True)


if __name__ == "__main__":
    _selfcheck()
