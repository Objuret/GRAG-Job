"""provenance.py — what a run folder needs to say about the conditions it ran under.

A manifest records what the run did. This records what it was: which code produced
it, on what machine with which library versions, and over exactly which bytes of
question set and corpus. Without those, two folders holding different numbers are
unexplainable — the difference could be the retrieval change under test or a
library upgrade, and nothing on disk distinguishes them.

Every lookup here is best-effort and returns a null field rather than failing a
run: provenance that costs a finished run is worse than provenance that admits a
gap. A field that could not be read is None, which reads as unknown, never as a
claim.
"""
from __future__ import annotations

import hashlib
import platform
import socket
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# The libraries whose version can move a number: retrieval engines, the numeric
# stack they rank in, the transport, and the eval framework.
TRACKED_PACKAGES = ("bm25s", "PyStemmer", "numpy", "httpx", "ragas", "neo4j")


def code_version() -> dict:
    """The commit the run's code came from, and whether the tree was dirty.
    `dirty` true means the commit does not describe what actually ran."""
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


def environment() -> dict:
    """The machine and the library versions the run executed against."""
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
    }


def file_digest(path) -> str | None:
    """sha256 of one file's bytes, None when it cannot be read."""
    p = Path(path) if path else None
    if not p or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree_digest(root, patterns=("**/*.json",)) -> dict | None:
    """A directory's content as one digest: sha256 over each matching file's
    repo-relative path and its own sha256, in sorted path order. Renaming a file,
    editing one byte, or adding or removing one all move the digest; file order on
    disk and mtimes do not. None when the directory is absent."""
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
    """The exact bytes this run read: the question bank, the id set that selected
    from it, and the corpus. Two runs agreeing on these three read identical
    inputs; two that disagree were never comparable."""
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

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "a.json").write_text('{"x": 1}', encoding="utf-8")
        (root / "sub").mkdir()
        (root / "sub" / "b.json").write_text('{"y": 2}', encoding="utf-8")
        first = tree_digest(root)
        assert first["n_files"] == 2

        # same bytes, same digest — recomputing is not a change
        assert tree_digest(root) == first
        # one byte moves it
        (root / "a.json").write_text('{"x": 2}', encoding="utf-8")
        assert tree_digest(root)["sha256"] != first["sha256"]
        # so does a rename that keeps every byte
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
