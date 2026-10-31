"""The round-1 facet layer for the metadata chunks of the artefact's pool: the HAS_TAG edges of
the chunks of employee.json and customers_data.json, encoded, scored and banded the way the
layer's 61,018 product edges were (his 2026-10-31 "go ahead and do this "for real"").

Three steps, each reading what the step before it wrote under OUT:

  inputs   the run's edges on the chunks whose `metadata_section` is 'employee' or
           'customers_data', and each chunk's text by `facet_stats.resolve_text`'s own rule:
           the string values of the records the chunk's locator points at, one per line
           (employee.json's records are its values in file order, which is the chunker's index;
           `resolve_text` itself returns no text for a metadata locator). Written as the two
           inputs of the full pass's extractor, `extract_standalone.py`: OUT/cache/edges.jsonl
           and OUT/cache/rows.jsonl. The extractor runs on the desktop's graphics card and writes
           OUT/cache/<model>.npz.
  refits   the round-1 baseline refit and the 24 bootstrap refits made again, with their stored
           seeds, through `bootstrap_scores.py`'s own `prepare`, `draw_rows` and `fit_one`
           steps; each draw's head and standardisation kept under OUT/refits/. The baseline is
           checked against round1/scores.jsonl and every draw against the stored
           round1/bootstrap/scores_b24.npz on the 61,018 edges (OUT/refits/check.json).
  extend   the encoded edges standardised and scored by each kept refit; OUT/bootstrap/
           scores_b24.npz holds the 61,018 edges' stored values, copied, and the new edges after
           them; then `bootstrap_scores.py --bands-only` reads the bands off it into
           OUT/bootstrap/BANDS.md and meta.json.

    python test/graph/facet_pairs/metadata_edges.py inputs|refits|extend

Nothing here calls a model or writes to the graph. `NEO4J_DATABASE` names the graph `inputs`
reads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
# the siblings first, then the repo's two roots, so `data`, `train` and `model` are this folder's
for _p in (str(ROOT / "prod"), str(ROOT / "test"), str(HERE)):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

import data as D  # noqa: E402

FACETS = D.FACETS
NON_TOPIC = ("temporal", "why", "activity", "concreteness")
SECTIONS = ("employee", "customers_data")
ROUND1 = ROOT / "output" / "facet_pairs" / "rounds" / "round1"
OUT = ROUND1 / "metadata_pool"
CACHE = ROOT / "output" / "facet_pairs" / "fullcache" / "Alibaba-NLP__gte-reranker-modernbert-base.npz"
ANSWERS = ROOT / "output" / "facet_pairs" / "answers"
STORED = ROUND1 / "bootstrap" / "scores_b24.npz"
MODEL_NAME = "Alibaba-NLP__gte-reranker-modernbert-base"

_EDGES_CYPHER = """
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $run AND c.metadata_section IN $sections
RETURN c.chunk_id AS chunk_id, t.name AS tag, c.metadata_section AS section, c.kind AS kind,
       c.locator_json AS locator, f.rel_path AS rel_path
ORDER BY chunk_id, tag
"""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def _rel(path: Path) -> str:
    return str(Path(path).relative_to(ROOT)).replace("\\", "/")


def _write_jsonl(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- inputs


def metadata_text(locator_json: str, rel_path: str, documents: dict) -> str:
    """`facet_stats.resolve_text`'s rule on a metadata locator: the records at the locator's
    indices, every string value of them one per line. A section that is a mapping
    (employee.json) is read as its values in file order."""
    from graph import facet_stats as FS
    loc = json.loads(locator_json)
    if rel_path not in documents:
        documents[rel_path] = json.loads(
            (ROOT / "data" / "corpus" / rel_path).read_text(encoding="utf-8"))
    section = FS._walk(documents[rel_path], loc["parent_ref"].split(".")[1:])
    records = list(section.values()) if isinstance(section, dict) else section
    if not isinstance(records, list):
        raise ValueError(f"{rel_path}: the locator {loc['chunk_ref']} reaches no record list")
    items = [records[i] for i in (loc.get("indices") or [loc["index"]])]
    text = "\n".join(FS._flat(items, []))
    if not text.strip():
        raise ValueError(f"{rel_path}: the locator {loc['chunk_ref']} gives no text")
    return text


def inputs() -> None:
    from graph.db import DATABASE, RUN_ID, _driver
    driver = _driver()
    try:
        with driver.session(database=DATABASE, default_access_mode="READ") as session:
            rows = session.run(_EDGES_CYPHER, run=RUN_ID, sections=list(SECTIONS)).data()
    finally:
        driver.close()
    documents, texts, edges = {}, {}, []
    for r in rows:
        if r["chunk_id"] not in texts:
            texts[r["chunk_id"]] = {"chunk_id": r["chunk_id"], "kind": r["kind"],
                                    "metadata_section": r["section"],
                                    "text": metadata_text(r["locator"], r["rel_path"], documents)}
        edges.append({"edge_id": D.edge_id(r["chunk_id"], r["tag"]), "chunk_id": r["chunk_id"],
                      "tag": r["tag"]})
    if len({e["edge_id"] for e in edges}) != len(edges):
        raise SystemExit("two edges join one chunk and one tag")
    per = {s: sum(1 for t in texts.values() if t["metadata_section"] == s) for s in SECTIONS}
    header = {"db": DATABASE, "run_id": RUN_ID, "sections": list(SECTIONS),
              "n_chunks": len(texts), "n_edges": len(edges), "chunks_per_section": per,
              "text": "facet_stats.resolve_text's rule on the metadata locator",
              "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    _write_jsonl(OUT / "cache" / "edges.jsonl", edges)
    _write_jsonl(OUT / "cache" / "rows.jsonl",
                 [{"header": header}] + [texts[c] for c in sorted(texts)])
    lengths = [len(t["text"]) for t in texts.values()]
    print(f"inputs: {DATABASE!r} run {RUN_ID!r}: {len(edges)} edges on {len(texts)} chunks "
          f"{per}; text {min(lengths)}..{max(lengths)} characters -> {OUT / 'cache'}",
          flush=True)


# ---------------------------------------------------------------- refits


def fit_kept(prep: dict, fit_obs: list) -> tuple:
    """`bootstrap_scores.fit_one`, step for step, with the head and the standardisation kept."""
    import torch
    import cache_probe as P
    idx = prep["idx"]
    enc_fit = P.encode_obs(fit_obs, idx)
    if enc_fit["n"] == 0:
        raise RuntimeError("a draw produced no cached fit observations")
    fit_rows = sorted({int(v) for v in enc_fit["a"].tolist() + enc_fit["b"].tolist()})
    Fz, mu, sd = P.standardise(prep["features"], fit_rows)
    X = torch.from_numpy(Fz)
    sub_rows, (sub_fit, sub_val) = P.subset([enc_fit, prep["enc_val"]])
    head, va = P.fit_head(X[sub_rows], sub_fit, sub_val, prep["val_obs_k"],
                          prep["head_kind"], prep["seed"], prep["max_epochs"],
                          prep["patience"], prep["lr"], prep["wd"], prep["hidden"])
    with torch.no_grad():
        scores = head(X).numpy()
    del Fz, X
    return head, float(va), mu, sd, scores


def refits() -> None:
    import torch
    import bootstrap_scores as BS
    started = time.perf_counter()
    if tuple(BS.NON_TOPIC) != NON_TOPIC or tuple(BS.FACETS) != tuple(FACETS):
        raise SystemExit("bootstrap_scores names other facets")
    config = json.loads((ROUND1 / "model" / "config.json").read_text(encoding="utf-8"))
    prep = BS.prepare(str(CACHE), str(ANSWERS), config)
    with np.load(STORED, allow_pickle=False) as z:
        stored = {k: z[k] for k in z.files}
    if [str(e) for e in stored["edge_ids"]] != prep["cache"].edge_ids:
        raise SystemExit("the stored refits and the cache list their edges in other orders")
    if [str(f) for f in stored["facets"]] != list(NON_TOPIC):
        raise SystemExit("the stored refits hold other facet columns")
    cols = [FACETS.index(f) for f in NON_TOPIC]
    out = OUT / "refits"
    out.mkdir(parents=True, exist_ok=True)

    tb = time.perf_counter()
    _, base_va, _, _, baseline = fit_kept(prep, prep["fit_obs"])
    rep = BS.reproduction_check(prep, baseline, str(ROUND1 / "scores.jsonl"))
    print(f"  baseline refit | val macro {base_va:.4f} | vs round1/scores.jsonl max |delta| "
          f"{rep['max_abs_delta']:.3e} | {time.perf_counter() - tb:.1f}s", flush=True)

    seeds = [int(s) for s in stored["seeds"]]
    B = len(seeds)
    n = len(prep["cache"].edge_ids)
    diff_max = np.zeros((len(NON_TOPIC), B))
    diff_sum = np.zeros(len(NON_TOPIC))
    equal = np.zeros(len(NON_TOPIC), dtype=np.int64)
    topic_max = np.zeros(B)
    vas = np.zeros(B)
    mus, sds = [], []
    for b, seed in enumerate(seeds):
        td = time.perf_counter()
        head, va, mu, sd, s = fit_kept(prep, BS.draw_rows(prep, seed))
        got = s[:, cols].astype(np.float32)
        held = stored["scores"][:, :, b]
        d = np.abs(got.astype(np.float64) - held.astype(np.float64))
        diff_max[:, b] = d.max(axis=0)
        diff_sum += d.sum(axis=0)
        equal += (got == held).sum(axis=0)
        topic_max[b] = float(np.abs(s[:, FACETS.index("topic")].astype(np.float64)
                                    - stored["head_topic"][:, b].astype(np.float64)).max())
        vas[b] = va
        torch.save(head.state_dict(), out / f"head_b{b:02d}_seed{seed}.pt")
        mus.append(mu)
        sds.append(sd)
        print(f"  draw {b + 1}/{B} seed {seed} | val macro {va:.4f} (stored "
              f"{float(stored['val_macro_agreement'][b]):.4f}) | max |delta| "
              f"{d.max():.3e} | {time.perf_counter() - td:.1f}s", flush=True)
    np.savez(out / "standardisation.npz", seeds=np.asarray(seeds, dtype=np.int64),
             mu=np.stack(mus), sd=np.stack(sds))
    per_facet = {f: {"max_abs_difference": float(diff_max[i].max()),
                     "mean_abs_difference": float(diff_sum[i] / (n * B)),
                     "values_bit_equal": int(equal[i]), "values": n * B}
                 for i, f in enumerate(NON_TOPIC)}
    check = {
        "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "what": ("the 24 refits made again with their stored seeds, their scores over the "
                 "cache's edges against the stored round1/bootstrap/scores_b24.npz"),
        "edges": n, "draws": B, "seeds": seeds,
        "per_facet": per_facet,
        "max_abs_difference_per_draw": {f: diff_max[i].tolist()
                                        for i, f in enumerate(NON_TOPIC)},
        "head_topic_max_abs_difference": float(topic_max.max()),
        "val_macro_agreement": vas.tolist(),
        "val_macro_agreement_stored": [float(v) for v in stored["val_macro_agreement"]],
        "val_macro_agreement_equal": bool(np.array_equal(
            vas, stored["val_macro_agreement"].astype(np.float64))),
        "baseline_reproduction_check": rep,
        "baseline_val_macro_agreement": base_va,
        "stored_sha256": _sha(STORED),
        "cache": {"path": _rel(CACHE)},
        "torch": torch.__version__, "numpy": np.__version__,
        "threads": torch.get_num_threads(),
        "code_sha256": {"metadata_edges.py": _sha(Path(__file__)),
                        "bootstrap_scores.py": _sha(HERE / "bootstrap_scores.py"),
                        "cache_probe.py": _sha(HERE / "cache_probe.py"),
                        "data.py": _sha(HERE / "data.py")},
        "wall_s": round(time.perf_counter() - started, 1),
    }
    (out / "check.json").write_text(json.dumps(check, indent=1), encoding="utf-8")
    print("refits: per facet " + json.dumps(per_facet), flush=True)
    print(f"  -> {out}", flush=True)


# ---------------------------------------------------------------- extend


def extend() -> None:
    import torch
    import bootstrap_scores as BS
    import cache_probe as P
    started = time.perf_counter()
    config = json.loads((ROUND1 / "model" / "config.json").read_text(encoding="utf-8"))
    check = json.loads((OUT / "refits" / "check.json").read_text(encoding="utf-8"))
    new_path = OUT / "cache" / f"{MODEL_NAME}.npz"
    new = P.Cache(str(new_path))
    meta = new.meta
    if (meta.get("model"), meta.get("revision")) != (config["cache_meta"]["model"],
                                                     config["cache_meta"]["revision"]):
        raise SystemExit("the new edges were encoded by another model or revision")
    wanted = [json.loads(line)["edge_id"] for line in
              (OUT / "cache" / "edges.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    if sorted(new.edge_ids) != sorted(wanted) or len(set(new.edge_ids)) != len(wanted):
        raise SystemExit("the encoded edges are not the edges of edges.jsonl")
    with np.load(STORED, allow_pickle=False) as z:
        stored = {k: z[k] for k in z.files}
    if set(new.edge_ids) & {str(e) for e in stored["edge_ids"]}:
        raise SystemExit("an encoded edge is already in the stored refits")
    cols = [FACETS.index(f) for f in NON_TOPIC]
    feats = new.features(config["variant"])
    with np.load(OUT / "refits" / "standardisation.npz", allow_pickle=False) as z:
        seeds = [int(s) for s in z["seeds"]]
        mus, sds = z["mu"], z["sd"]
    if seeds != [int(s) for s in stored["seeds"]]:
        raise SystemExit("the kept refits carry other seeds than the stored ones")
    B = len(seeds)
    # the stored edges go through the same arithmetic as the new ones, against their stored scores
    old_feats = P.Cache(str(CACHE)).features(config["variant"])
    if old_feats.shape[0] != stored["scores"].shape[0]:
        raise SystemExit("the cache and the stored refits hold different numbers of edges")
    old_max = np.zeros(len(NON_TOPIC))
    old_equal = np.zeros(len(NON_TOPIC), dtype=np.int64)
    scores = np.zeros((len(new.edge_ids), len(NON_TOPIC), B), dtype=np.float32)
    head_topic = np.zeros((len(new.edge_ids), B), dtype=np.float32)
    for b, seed in enumerate(seeds):
        head = P.Head(feats.shape[1], config["head"], int(config.get("hidden", P.HIDDEN)))
        head.load_state_dict(torch.load(OUT / "refits" / f"head_b{b:02d}_seed{seed}.pt",
                                        weights_only=True))
        head.eval()
        # `cache_probe.standardise`'s own arithmetic, with this draw's fit-row mean and sd
        X = torch.from_numpy(((feats - mus[b]) / sds[b]).astype(np.float32))
        X_old = torch.from_numpy(((old_feats - mus[b]) / sds[b]).astype(np.float32))
        with torch.no_grad():
            s = head(X).numpy()
            s_old = head(X_old).numpy()[:, cols]
        scores[:, :, b] = s[:, cols]
        head_topic[:, b] = s[:, FACETS.index("topic")]
        held = stored["scores"][:, :, b]
        old_max = np.maximum(old_max, np.abs(s_old.astype(np.float64)
                                             - held.astype(np.float64)).max(axis=0))
        old_equal += (s_old == held).sum(axis=0)
        del X_old, s_old
    del old_feats
    if not np.isfinite(scores).all():
        raise SystemExit("a new edge's refit score is not finite")
    edge_ids = [str(e) for e in stored["edge_ids"]] + list(new.edge_ids)
    boot = OUT / "bootstrap"
    boot.mkdir(parents=True, exist_ok=True)
    (OUT / "model").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROUND1 / "model" / "config.json", OUT / "model" / "config.json")
    npz = boot / f"scores_b{B}.npz"
    np.savez(npz,
             edge_ids=np.array(edge_ids, dtype=object).astype("U"),
             facets=np.array(list(NON_TOPIC)),
             scores=np.concatenate([stored["scores"], scores], axis=0),
             head_topic=np.concatenate([stored["head_topic"], head_topic], axis=0),
             seeds=stored["seeds"], val_macro_agreement=stored["val_macro_agreement"])
    # the bands are read off the extended matrix by bootstrap_scores itself (--bands-only),
    # which carries the reproduction check and the baseline agreement over from meta.json
    (boot / "meta.json").write_text(json.dumps({
        "reproduction_check": check["baseline_reproduction_check"],
        "baseline_val_macro_agreement": check["baseline_val_macro_agreement"]}, indent=1),
        encoding="utf-8")
    BS.run(str(CACHE), str(OUT), str(ANSWERS), draws=B, bands_only=True)
    record = {
        "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "edges_stored": int(stored["scores"].shape[0]), "edges_new": len(new.edge_ids),
        "edges": len(edge_ids),
        "stored": {"path": _rel(STORED), "sha256": _sha(STORED),
                   "rows": "copied unchanged, first in the file, in their stored order"},
        "new": {"cache": _rel(new_path), "cache_sha256": _sha(new_path), "cache_meta": meta,
                "rows": "after the stored rows, in the cache's order"},
        "refits": {"check": _rel(OUT / "refits" / "check.json"),
                   "standardisation_sha256": _sha(OUT / "refits" / "standardisation.npz")},
        "stored_edges_scored_the_new_way": {
            "what": ("the stored edges' cached vectors through each kept refit with this step's "
                     "arithmetic, against their stored scores"),
            "per_facet": {f: {"max_abs_difference": float(old_max[i]),
                              "values_bit_equal": int(old_equal[i]),
                              "values": int(stored["scores"].shape[0] * B)}
                          for i, f in enumerate(NON_TOPIC)}},
        "scores_sha256": _sha(npz),
        "torch": torch.__version__, "numpy": np.__version__,
        "code_sha256": {"metadata_edges.py": _sha(Path(__file__)),
                        "bootstrap_scores.py": _sha(HERE / "bootstrap_scores.py"),
                        "bootstrap_band.py": _sha(HERE / "bootstrap_band.py"),
                        "cache_probe.py": _sha(HERE / "cache_probe.py")},
        "wall_s": round(time.perf_counter() - started, 1),
    }
    (OUT / "EXTEND.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"extend: {len(edge_ids)} edges ({record['edges_stored']} stored + "
          f"{record['edges_new']} new) -> {npz}", flush=True)


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=("inputs", "refits", "extend"))
    a = ap.parse_args(argv)
    print(f"metadata_edges {a.step} …", flush=True)
    {"inputs": inputs, "refits": refits, "extend": extend}[a.step]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
