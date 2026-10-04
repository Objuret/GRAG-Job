"""Prospective function screen on sampled corpus relationships, no benchmark gold.

Select eight lowercase multiword tags by a fixed hash order, each shared by two
head-heldout chunks of 500--2400 characters. Select chunks by another fixed hash;
no chunk may occur in two subject groups. The lowercase restriction is a mechanical
way to sample semantic phrases rather than most proper names, not an entity detector.
No score or comparison answer affects selection. This is a restricted corpus stratum.

Four generic descriptions of sought content are instantiated from each tag before
any reader call. Existing graph relationships remain intact; there is no retagging.
Reuse the synthetic experiment's separated query, graph and preference reading
tasks, and its nonnegative comparison fit. Report all methods and ties.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test"), str(ROOT / "tools")]
from graph.facet_pairs import data as D
from facet_tradeoff_readings import jobs, run


def hashed(salt, value):
    return hashlib.sha256((salt+value).encode()).hexdigest()


def prepare(out, model):
    if (out / "manifest.json").exists():
        return json.loads((out / "manifest.json").read_text())
    rows_path = ROOT / "output/facet_neural/rows_export.jsonl"
    score_path = ROOT / "output/facet_pairs/rounds/round1/scores.jsonl"
    scored_edges = {json.loads(line)["edge_id"] for line in score_path.open(encoding="utf-8")}
    by_tag = defaultdict(list)
    for chunk in D.load_chunks(str(rows_path)):
        if not D.is_heldout(chunk["chunk_id"]) or not 500 <= len(chunk["text"]) <= 2400:
            continue
        for tag in set(chunk["tags"]):
            if tag == tag.lower() and 2 <= len(tag.split()) <= 8 and len(tag) < 80 and D.edge_id(chunk["chunk_id"], tag) in scored_edges:
                by_tag[tag].append(chunk)
    eligible = {t:cs for t,cs in by_tag.items() if len(cs) >= 2}
    used, domains = set(), []
    for tag in sorted(eligible, key=lambda t:hashed("corpus_tradeoff_20260922:",t)):
        candidates = sorted((c for c in eligible[tag] if c["chunk_id"] not in used),
            key=lambda c:hashed("corpus_tradeoff_chunk_20260922:", c["chunk_id"]))
        if len(candidates) < 2:
            continue
        chosen = candidates[:2]
        used.update(c["chunk_id"] for c in chosen)
        domains.append({"id": f"g{len(domains)}", "tag": tag,
            "descriptions": [
                f"Content about {tag} that explains its timing, sequence, dependencies or state of completion.",
                f"Content about {tag} that explains reasons, causes, purposes or the rationale for decisions.",
                f"Content about {tag} that records actions actually performed, changes made or decisions carried out, rather than only describing or proposing them.",
                f"Content about {tag} that supplies concrete particulars, such as specific quantities, named items, settings or documented details."],
            "texts": [c["text"] for c in chosen],
            "source_chunks": [c["chunk_id"] for c in chosen],
            "source_edges": [D.edge_id(c["chunk_id"],tag) for c in chosen],
            "source_kinds": [c.get("kind") for c in chosen]})
        if len(domains) == 8:
            break
    if len(domains) != 8 or len(used) != 16:
        raise RuntimeError("insufficient disjoint groups for stated protocol")
    cases = {"purpose": __doc__, "domains": domains}
    manifest = {"protocol": __doc__, "created_utc": datetime.now(timezone.utc).isoformat(),
        "model": model, "cases": cases, "jobs": jobs(cases), "eligible_tags": len(eligible),
        "source_sha256": {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [rows_path,score_path]},
        "collection_deviations": "None planned. Report missing readings without imputation or retries selected for content. Repeats share total mass per comparison.",
        "analysis_prespecified": {
            "split": "leave one of eight tag groups out; source chunks disjoint across groups and absent from the old head's fitting and validation",
            "methods": ["topic only", "query-independent nonnegative weighted facets", "equal query-times-edge products", "fitted nonnegative query-times-edge products", "query ordered lexicographic facets"],
            "numeric_fit": "nested leave-one-group-out three-way Davidson likelihood, nonnegative coefficients; select L2 from [0.001,0.01,0.1,1] by inner group-average log loss",
            "score_sources": ["separate direct readings", "original frozen graph head mapped to prior fixed references"],
            "repeats": "two preference readings with reversed A/B; mean of two separate numerical readings; equal total mass per distinct comparison",
            "limits": "eight groups in a restricted stratum, generic repeated query templates, one model across reading tasks; no population generalization or full retrieval claim"}}
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    manifest = prepare(args.out, args.model)
    if manifest["model"] != args.model:
        raise ValueError("existing manifest uses a different model")
    print("Sampled:", [d["tag"] for d in manifest["cases"]["domains"]], flush=True)
    print(f"Saved {len(manifest['jobs'])} call inputs before execution", flush=True)
    if args.run:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run,j,args.out,args.model) for j in manifest["jobs"]]
            for f in as_completed(futures):
                r = f.result()
                print(r["id"],len(r["answer"]),r.get("missing_cases",[]),flush=True)


if __name__ == "__main__":
    main()
