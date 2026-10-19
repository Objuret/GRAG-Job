"""Check the vectors of the new unit texts fetched from the desktop, hold the desktop's GPU against
the laptop's CPU on the 200-unit sample, and write the vector arm's cache file for these texts.

    .venv/Scripts/python.exe output/research/2026-10-09-baseline-unit-text/finalize_units.py

Nothing that exists is overwritten: the arm's cache file for these texts must not exist yet, and
the cache of the earlier texts is not touched. Numbers only.
"""
import hashlib
import io
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "prod"))

from arms import vector  # noqa: E402
from harness import embed  # noqa: E402
from harness.record_text import FORM, units_digest  # noqa: E402

OLD_CACHE = REPO / "output" / "embed_cache" / "llama-nemotron-embed-1b-v2_a43c8c706908de3a.npz"
OUT = REPO / "output" / "embed_local" / "20261009_units_rev113abe4acafa_float32"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rows(name):
    return [json.loads(x) for x in (HERE / name).open(encoding="utf-8") if x.strip()]


def spread(c):
    q = np.percentile(c, [0, 1, 50, 99, 100])
    return f"min {q[0]:.6f}  1% {q[1]:.6f}  median {q[2]:.6f}  99% {q[3]:.6f}  max {q[4]:.6f}"


def cos_rows(a, b):
    a, b = a.astype(np.float64), b.astype(np.float64)
    return (a * b).sum(axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))


def check(label, npz, manifest, inp):
    z = np.load(npz, allow_pickle=True)
    man = json.loads(manifest.read_text(encoding="utf-8"))
    m = z["matrix"]
    norms = np.linalg.norm(m.astype(np.float64), axis=1)
    checks = {
        "file hash equals the desktop's": sha(npz) == man["output_sha256"],
        "matrix hash equals the desktop's": hashlib.sha256(m.tobytes()).hexdigest() == man["matrix_sha256"],
        "input hash equals the laptop's file": sha(inp) == man["input_sha256"],
        "ids equal the input, same order": list(z["ids"]) == [r["id"] for r in rows(inp.name)],
        "one row per input row, 2048 wide": m.shape == (len(rows(inp.name)), 2048),
        "float32": str(m.dtype) == "float32",
        "no NaN or inf": bool(np.isfinite(m).all()),
        "unit length": bool(np.abs(norms - 1).max() < 1e-5),
        "passage mode, the repo's model and revision": (man["mode"], man["prefix"], man["model"], man["revision"])
        == ("passage", embed.EMBED_PREFIX["passage"], embed.EMBED_MODEL, embed.EMBED_REVISION),
    }
    print(f"== {label}: {m.shape} {m.dtype}, {man['tokens_in']} tokens, {man['seconds_this_call']} s, "
          f"device {man['device_name']}, longest input {man['max_seq_length']} tokens")
    for k, v in checks.items():
        print(f"   [{'ok' if v else 'FAIL'}] {k}")
    assert all(checks.values()), f"{label} failed a check"
    return z, man, checks


corpus_in = rows("corpus_units.jsonl")
ids = [r["id"] for r in corpus_in]
texts = [r["text"] for r in corpus_in]
cache = vector._cache_path(ids, texts)
assert not cache.exists(), f"{cache} exists, nothing is overwritten"
assert not OUT.exists(), f"{OUT} exists, nothing is overwritten"

zc, man_c, checks_c = check("corpus", HERE / "corpus_units_20261009_local.npz",
                            HERE / "corpus_units_20261009_local.manifest.json", HERE / "corpus_units.jsonl")
zs, man_s, checks_s = check("sample on the desktop", HERE / "sample_units_20261009_gpu.npz",
                            HERE / "sample_units_20261009_gpu.manifest.json", HERE / "sample.jsonl")

# the two machines on the same 200 texts: the question is embedded on the laptop when it is asked
lap = np.load(HERE / "sample_laptop.npz", allow_pickle=True)
assert list(lap["ids"]) == list(zs["ids"])
c = cos_rows(zs["matrix"], lap["matrix"])
d = np.abs(zs["matrix"].astype(np.float64) - lap["matrix"].astype(np.float64)).max()
print(f"\n== desktop GPU against laptop CPU, the 200-unit sample: cosine per row {spread(c)} | "
      f"largest difference in one number {d:.2e}")
idx = json.loads((HERE / "sample_idx.json").read_text(encoding="utf-8"))
same = np.abs(zc["matrix"][idx].astype(np.float64) - zs["matrix"].astype(np.float64)).max()
print(f"== the corpus rows of those 200 units against the sample made in its own call on the desktop: "
      f"largest difference in one number {same:.2e}")
gate = {"cosine_gpu_to_cpu": spread(c), "max_abs_diff_gpu_to_cpu": float(d),
        "max_abs_diff_corpus_rows_to_sample_call": float(same)}

old = np.load(OLD_CACHE, allow_pickle=True)
assert list(old["ids"]) == ids
moved = cos_rows(zc["matrix"], old["matrix"])
print(f"== each unit's new vector against its vector of 10-07 (the text changed): cosine {spread(moved)}")

# the job ran in two calls: the first was cut off with the laptop's sleep after 12 of 20 parts,
# the second made the rest. The second call's seconds are in its manifest; the first call's are
# read off the times its parts were written (one part's time before part 0 is when it began).
times = {}
for line in (HERE / "desktop_parts_times.print.txt").read_text(encoding="utf-8").splitlines():
    name, _, stamp = line.strip().partition(" ")
    if name.startswith("part"):
        times[int(name[4:8])] = datetime.fromisoformat(stamp.replace("Z", "+00:00")[:26] + "+00:00")
first_parts = [n for n in sorted(times) if times[n] < times[0].replace(day=times[0].day) + (times[11] - times[0]) * 2 and n <= 11]
step = (times[11] - times[0]).total_seconds() / 11
first_call_s = (times[11] - times[0]).total_seconds() + step
build_s = first_call_s + man_c["seconds_this_call"]
print(f"== build time: first call {first_call_s:,.1f} s (parts 0-11, {(len(first_parts)) * 2000} texts, from the parts' times), "
      f"second call {man_c['seconds_this_call']:,.1f} s ({man_c['texts_embedded_this_call']} texts, its manifest); together {build_s:,.1f} s")

matrix = zc["matrix"]
cache.parent.mkdir(parents=True, exist_ok=True)
tmp = cache.with_suffix(".tmp.npz")
np.savez(tmp, matrix=matrix, ids=np.array(ids, dtype=object), texts=np.array(texts, dtype=object),
         build_stats=np.array([build_s, man_c["n"], man_c["tokens_in"], 0, build_s], dtype=object))
tmp.replace(cache)
cost = {"model": man_c["model"], "revision": man_c["revision"], "mode": man_c["mode"],
        "prefix": man_c["prefix"], "calls": man_c["n"], "tokens_in": man_c["tokens_in"],
        "tokens_out": 0, "build_time_s": build_s,
        "build_time_note": f"two calls on the same machine: the first, cut off when the laptop that "
                           f"started it slept, made parts 0-11 in {first_call_s:.1f} s (read off "
                           f"the parts' write times); the second made the rest in "
                           f"{man_c['seconds_this_call']} s (its own manifest)",
        "batch": man_c["batch"],
        "device": man_c["device_name"], "dtype": man_c["dtype"], "host": man_c["host"],
        "python": man_c["python"], "torch": man_c["torch"],
        "sentence_transformers": man_c["sentence_transformers"],
        "transformers": man_c["transformers"], "made_utc": man_c["made_utc"],
        "max_seq_length": man_c["max_seq_length"], "units_over_max_seq_length": 0,
        "unit_text": FORM, "units_sha256": units_digest(ids, texts),
        "source": f"{OUT.relative_to(REPO).as_posix()}/MANIFEST.json",
        "earlier_texts_cache": OLD_CACHE.relative_to(REPO).as_posix()}
cache.with_suffix(".cost.json").write_text(json.dumps(cost, indent=2), encoding="utf-8")

OUT.mkdir(parents=True)
(OUT / "scripts").mkdir()
for f in ("prep_units.py", "sample_laptop.py", "finalize_units.py"):
    shutil.copy2(HERE / f, OUT / "scripts" / f)
for f in ("prep_units.print.txt", "sample_laptop.print.txt", "desktop_job.print.txt",
          "desktop_job_resumed.print.txt", "desktop_parts_times.print.txt"):
    if (HERE / f).is_file():
        shutil.copy2(HERE / f, OUT / f)
(OUT / "MANIFEST.json").write_text(json.dumps({
    "what": "the vector arm's corpus vectors for the unit texts of 2026-10-09, made by the local "
            "embedder on the desktop's GPU; the cache of the earlier texts is untouched",
    "unit_text": FORM, "units_sha256": units_digest(ids, texts), "n": len(ids),
    "input": {"file": "corpus_units.jsonl", "sha256": sha(HERE / "corpus_units.jsonl")},
    "desktop": {"corpus": man_c, "sample": man_s},
    "laptop_checks": {"corpus": checks_c, "sample": checks_s, "two_machines": gate},
    "cosine_to_the_vectors_of_the_earlier_text": spread(moved),
    "cache_file": {"path": cache.relative_to(REPO).as_posix(), "sha256": sha(cache),
                   "bytes": cache.stat().st_size},
    "embed_job": "the desktop's A:/exjobbet/embed_local_20261007/embed_job.py with harness/embed.py "
                 "as shipped 2026-10-07 (output/embed_local/20261007_rev113abe4acafa_float32/scripts)",
}, indent=2), encoding="utf-8")
print(f"\nthe arm's cache for these texts: {cache.relative_to(REPO)}  {cache.stat().st_size:,} bytes  "
      f"sha256 {sha(cache)[:16]}")
print(f"cost note beside it; record in {OUT.relative_to(REPO)}")
prepared = vector.build_dense_index(orchestrator_corpus := str(REPO / "data" / "corpus" / "Salesforce__HERB"))
print(f"the arm now reads it: cache_file {Path(prepared.cache_file).name} | units {len(prepared.ids)} | "
      f"matrix {prepared.matrix.shape} | build_stats {prepared.build_stats.build_time_s} s, "
      f"{prepared.build_stats.model.calls} calls, {prepared.build_stats.model.tokens_in} tokens")
