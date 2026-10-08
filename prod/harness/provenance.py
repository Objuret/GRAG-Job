from __future__ import annotations

import hashlib
import os
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


_CODE_PATHS = ("prod", "test", "tools", "data", "pytest.ini", "refresh_graph.py")
# the run's own switches, and what the CLI of the model lane can read from its environment
_SETTING_PREFIXES = ("RAGAS_", "HERB_", "NEO4J_", "CLAUDE", "ANTHROPIC_", "MAX_THINKING",
                     "MAX_STRUCTURED", "DISABLE_", "OTEL_", "API_TIMEOUT")
_SECRET_WORDS = ("PASSWORD", "TOKEN", "KEY", "SECRET")


def code_state() -> dict:
    """What `dirty` hides: which code paths differ from the commit, and the diff itself.
    The run folders under output/ are left out, they are not code."""
    def git(*args, raw=False):
        try:
            out = subprocess.run(("git", *args), cwd=str(_REPO), capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        return out.stdout if raw else out.stdout.decode("utf-8", "replace")

    status = git("status", "--porcelain", "--", *_CODE_PATHS)
    # git's own bytes: read as text, the CR of a CR LF file is lost and the diff no longer applies
    diff = git("diff", "HEAD", "--", "prod", "test", "tools", "pytest.ini", "refresh_graph.py",
               raw=True)
    untracked = {}
    for line in (status or "").splitlines():
        if line.startswith("?? "):
            p = _REPO / line[3:].strip().strip('"')
            if p.is_file():
                untracked[line[3:].strip()] = file_digest(p)
    return {
        "status": None if status is None else status.splitlines(),
        "diff": diff,
        "diff_sha256": None if diff is None else hashlib.sha256(diff).hexdigest(),
        "untracked_sha256": untracked,
    }


def settings_env() -> dict:
    """The environment variables that change what a run does. A secret is named, never copied."""
    out = {}
    for name, value in sorted(os.environ.items()):
        if not name.startswith(_SETTING_PREFIXES):
            continue
        # a limit counted in tokens (MAX_THINKING_TOKENS) is a number, not a credential
        secret = any(w in name for w in _SECRET_WORDS) and not name.endswith("_TOKENS")
        out[name] = "<set>" if secret else value
    return out


def ram_bytes() -> int | None:
    try:
        if os.name == "nt":
            import ctypes

            class _Mem(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

            m = _Mem()
            m.dwLength = ctypes.sizeof(_Mem)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return int(m.ullTotalPhys)
            return None
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError, AttributeError):
        return None


def peak_memory_bytes() -> int | None:
    """The most memory this process has held so far."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class _Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]

            c = _Counters()
            c.cb = ctypes.sizeof(_Counters)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Counters),
                                                   wintypes.DWORD]
            if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return int(c.PeakWorkingSetSize)
            return None
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak if sys.platform == "darwin" else peak * 1024)
    except (OSError, ValueError, AttributeError, ImportError):
        return None


def embedder() -> dict:
    from harness.embed import EMBED_DEVICE, EMBED_DTYPE, EMBED_MODEL, EMBED_REVISION

    return {"model": EMBED_MODEL, "revision": EMBED_REVISION,
            "device": EMBED_DEVICE, "dtype": EMBED_DTYPE}


def installed_packages() -> list:
    """Every package of the Python that runs, as name==version, sorted."""
    from importlib.metadata import distributions

    seen = set()
    for dist in distributions():
        try:
            name = dist.metadata["Name"]
        except (KeyError, OSError, ValueError):
            name = None
        if name:
            seen.add(f"{name}=={dist.version}")
    return sorted(seen, key=str.lower)


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
        "python_executable": sys.executable,
        "cpu": platform.processor(),
        "cpu_count": os.cpu_count(),
        "ram_bytes": ram_bytes(),
        "packages": packages,
        "packages_all": installed_packages(),
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
