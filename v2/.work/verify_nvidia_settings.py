"""Confirm Settings reads NVIDIA_* from backend/.env. Key value never printed."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from shared.config import Settings  # noqa: E402

s = Settings()
k = s.nvidia_api_key
print("nvidia_base_url:", s.nvidia_base_url)
print("nvidia_model   :", s.nvidia_model)
print("nvidia_api_key :", (f"set (prefix {k[:5]}..., len {len(k)})" if k else "NOT SET"))

ok_url = s.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
ok_key = bool(k) and k.startswith("nvapi-")
print()
print("base_url correct (integrate. subdomain):", ok_url)
print("api_key present and nvapi- shaped      :", ok_key)
print("=> READY" if (ok_url and ok_key) else "=> NOT READY — fix the flagged item in backend/.env")
