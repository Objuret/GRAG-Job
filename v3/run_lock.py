"""Single-writer guard for run output folders."""
from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path


class RunLock:
    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)
        self.path = self.out_dir / ".run.lock"
        self.fd = None

    def __enter__(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._stale():
                    self.path.unlink(missing_ok=True)
                    continue
                detail = self.path.read_text(encoding="utf-8", errors="replace")
                raise RuntimeError(
                    f"output folder is already in use: {self.out_dir}\n"
                    f"lock: {self.path}\n{detail}"
                )
            else:
                payload = {
                    "pid": os.getpid(),
                    "host": socket.gethostname(),
                    "started": datetime.now(timezone.utc).isoformat(),
                    "argv": sys.argv,
                }
                os.write(self.fd, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
                os.fsync(self.fd)
                return self
        raise RuntimeError(f"could not acquire output lock: {self.path}")

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.path.unlink(missing_ok=True)

    def _stale(self) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            pid = int(payload["pid"])
        except Exception:
            return False
        return not _pid_alive(pid)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            still_active = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
            if not handle:
                return False
            code = wintypes.DWORD()
            try:
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _selfcheck():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        with RunLock(d):
            try:
                with RunLock(d):
                    raise AssertionError("second lock should fail")
            except RuntimeError as e:
                assert "already in use" in str(e)
        assert not (Path(d) / ".run.lock").exists()
    print("run_lock self-check OK")


if __name__ == "__main__":
    _selfcheck()
