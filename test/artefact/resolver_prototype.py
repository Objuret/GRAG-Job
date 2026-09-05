
from __future__ import annotations

import hashlib
import json
from pathlib import Path

H = Path("data/raw/Salesforce__HERB/products/PitchForce.json")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def json_pointer(doc, pointer: str):
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise ValueError(f"invalid json-pointer (must start with '/'): {pointer!r}")
    cur = doc
    for raw in pointer.split("/")[1:]:
        token = unescape(raw)
        if isinstance(cur, list):
            if not token.lstrip("-").isdigit():
                raise KeyError(f"pointer {pointer!r}: '{token}' is not a list index")
            idx = int(token)
            if not (0 <= idx < len(cur)):
                raise KeyError(f"pointer {pointer!r}: index {idx} out of range (len {len(cur)})")
            cur = cur[idx]
        elif isinstance(cur, dict):
            if token not in cur:
                raise KeyError(f"pointer {pointer!r}: key {token!r} not present")
            cur = cur[token]
        else:
            raise KeyError(f"pointer {pointer!r}: cannot descend into scalar at {token!r}")
    return cur


def resolve(ref: dict, *, data_root: Path) -> object:
    path = data_root / ref["file_path"]
    actual = sha256_of(path)
    if actual != ref["sha256"]:
        raise RuntimeError(
            f"HASH MISMATCH for {ref['file_path']}: graph built against "
            f"{ref['sha256'][:12]}…, on-disk is {actual[:12]}…. Refusing to serve drifted content."
        )
    doc = json.loads(path.read_text(encoding="utf-8"))
    scheme = ref["scheme"]
    if scheme == "json_pointer":
        return json_pointer(doc, ref["address"])
    if scheme == "char_span":
        ptr, start, end = ref["address"]
        val = json_pointer(doc, ptr)
        if not isinstance(val, str):
            raise TypeError(f"char_span target is not a string: {ptr}")
        return val[start:end]
    raise ValueError(f"unknown scheme: {scheme}")


def main() -> None:
    root = Path(".")
    sha = sha256_of(H)
    fid = sha[:24]
    print(f"file: {H.name}  file_id={fid}\n")

    refs = [
        {"label": "slack[0] msg text (json_pointer)",
         "file_path": str(H), "sha256": sha, "scheme": "json_pointer",
         "address": "/slack/0/Message/User/text"},
        {"label": "prs[0] summary (json_pointer)",
         "file_path": str(H), "sha256": sha, "scheme": "json_pointer",
         "address": "/prs/0/summary"},
        {"label": "documents[0] content, first 60 chars (char_span)",
         "file_path": str(H), "sha256": sha, "scheme": "char_span",
         "address": ["/documents/0/content", 0, 60]},
        {"label": "slack[0] userId (scalar attribute via pointer)",
         "file_path": str(H), "sha256": sha, "scheme": "json_pointer",
         "address": "/slack/0/Message/User/userId"},
    ]

    print("--- resolving valid references ---")
    for r in refs:
        val = resolve(r, data_root=root)
        s = val if isinstance(val, str) else json.dumps(val)
        print(f"  {r['label']}\n    -> {s[:120]!r}")
    print()

    print("--- hash-verify gate (tampered sha) ---")
    bad = dict(refs[0]); bad["sha256"] = "0" * 64
    try:
        resolve(bad, data_root=root)
        print("  FAIL: served content despite hash mismatch")
    except RuntimeError as e:
        print(f"  OK fail-loud: {e}")
    print()

    print("--- bad pointer (no silent None) ---")
    miss = dict(refs[0]); miss["address"] = "/slack/0/Message/User/nonexistent"
    try:
        resolve(miss, data_root=root)
        print("  FAIL: returned a value for a missing key")
    except KeyError as e:
        print(f"  OK fail-loud: {e}")


if __name__ == "__main__":
    main()
