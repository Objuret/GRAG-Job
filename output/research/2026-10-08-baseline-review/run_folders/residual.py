"""Residual counts for the review: ids in the directory namespace, and D's source hashes."""
import hashlib
import json
import subprocess
import sys

from folders import ALL, REPO

sys.stdout.reconfigure(encoding="utf-8")


def rows(p):
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


for name in ("A.luc", "A.vec", "B.luc", "B.vec"):
    rs = rows(ALL[name] / "arm_outputs.jsonl")
    meta_ids = sum(1 for r in rs for c in r["context_ids"] if str(c).startswith("metadata::"))
    all_ids = sum(len(r["context_ids"]) for r in rs)
    distinct = len(set(c for r in rs for c in r["context_ids"]))
    print(f"{name}: context ids delivered {all_ids} (distinct {distinct}); ids starting with 'metadata::' {meta_ids}")

# the artefact row's own record of source files (hash only), against the files as they stand
r = rows(ALL["D.v4_100"] / "arm_outputs.jsonl")[0]
src = r["meta"]["provenance"]["source_sha256"]
print()
print("D.v4_100 meta.provenance.source_sha256 (made 2026-10-07T04:19Z) against the files now and at HEAD:")
for path, h in src.items():
    p = REPO / path.replace(chr(92), "/")
    now = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    got = subprocess.run(["git", "show", "HEAD:" + path.replace(chr(92), "/")], cwd=str(REPO), capture_output=True)
    head_lf = hashlib.sha256(got.stdout).hexdigest() if got.returncode == 0 else None
    head_crlf = hashlib.sha256(got.stdout.replace(bytes([13, 10]), bytes([10])).replace(bytes([10]), bytes([13, 10]))).hexdigest() if got.returncode == 0 else None
    print(f"   {path.replace(chr(92), '/'):<44} == file now: {h == now}   == HEAD blob: {h == head_lf or h == head_crlf}   (in git at HEAD: {got.returncode == 0})")
