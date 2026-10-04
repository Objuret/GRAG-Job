"""Recompute the experimental prepared-query pipeline from frozen safe inputs.

No interpretation, embedding, database, network, raw-corpus, or saved-score replay.
Run --list for the available captured questions. See docs/facet-retrieval-demo.md.
"""
import argparse
import ast
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "output/research/2026-09-21-facet-validity/route_snapshot"
BASE = ROOT / "output/research/2026-09-22-joint-streams/independent_sources"
FACETS = ("topic", "temporal", "why", "activity", "concreteness")
CAPTURES = BASE / "query_capture/query_captures.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List frozen questions and reading indices; no retrieval.")
    parser.add_argument("--query-bundle", type=Path, default=BASE,
                        help="Bundle containing query_capture/ and query_snapshot/; defaults to original captures.")
    parser.add_argument("--question-id")
    parser.add_argument("--reading-index", type=int, default=0, help="Saved SCORE repeat index, default 0.")
    parser.add_argument("--coefficients", type=float, nargs=5, metavar="BETA", help="Required: topic temporal why activity concreteness.")
    parser.add_argument("--source-character-budget", type=int, help="Required nonnegative saved-source-character budget.")
    parser.add_argument("--output", type=Path, help="Required NEW output directory; never overwritten.")
    parser.add_argument("--verified-area", action="store_true", help="Opt in to this reading's archived verified area; unresolved readings stay global.")
    args = parser.parse_args(argv)
    args.query_bundle = args.query_bundle.resolve()
    if args.list:
        if args.question_id or args.coefficients is not None or args.source_character_budget is not None or args.output or args.verified_area:
            parser.error("--list cannot be combined with retrieval arguments")
        return parser, args
    for name in ("question_id", "coefficients", "source_character_budget", "output"):
        if getattr(args, name) is None:
            parser.error(f"--{name.replace('_', '-')} is required for retrieval")
    if (not all(math.isfinite(x) for x in args.coefficients)
            or args.coefficients[0] <= 0 or any(x < 0 for x in args.coefficients[1:])):
        parser.error("coefficients must be finite, with topic > 0 and auxiliaries >= 0")
    if args.source_character_budget < 0 or args.reading_index < 0:
        parser.error("budget and reading index must be nonnegative")
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error("output path already exists; choose a fresh directory")
    return parser, args


def verify_hash(path, expected):
    if sha(path) != expected:
        raise ValueError(f"Frozen input hash mismatch: {path}")


def source_adjacency(chunks, np):
    """Load only these two pure functions; never import the service-backed arm."""
    path = ROOT / "test/arms/artefact_v3.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in {"_csr", "file_adjacency"}]
    if len(functions) != 2:
        raise ValueError("Expected the two original adjacency functions")
    namespace = {"np": np, "json": json}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    adjacency = namespace["file_adjacency"](chunks)
    return [(i, int(j)) for i in range(len(chunks))
            for j in adjacency["members"][adjacency["ptr"][i]:adjacency["ptr"][i + 1]] if i < j]


def frozen_area(capture, reading):
    """Read only archived membership/provenance; never consume archived scores."""
    directory = BASE / "scope_recruitment/run"
    manifest_path, summary_path = directory / "manifest.json", directory / "summary.json"
    manifest = read(manifest_path)
    verify_hash(summary_path, manifest["output_sha256"][summary_path.name])
    matches = [row for row in read(summary_path) if row["reading_id"] == reading["id"]
               and row["question_id"] == capture["question_id"]]
    if len(matches) != 1:
        raise ValueError("Exactly one frozen scope record is required for this reading")
    record = matches[0]
    path = directory / record["file"]
    if path.parent != directory or path.name != reading["id"] + ".json.gz":
        raise ValueError("Unexpected frozen scope archive path")
    verify_hash(path, record["sha256"])
    verify_hash(path, manifest["output_sha256"][path.name])
    graph_path = STATIC / "graph.json"
    verify_hash(graph_path, manifest["input_sha256"][str(graph_path.relative_to(ROOT))])
    archived = json.loads(gzip.decompress(path.read_bytes()))
    if (archived["reading_id"] != reading["id"] or archived["question_id"] != capture["question_id"]
            or archived["area"]["question"] != capture["question"]):
        raise ValueError("Frozen scope query identity mismatch")
    ids, provenance = archived["area_chunk_ids"], archived["area"]
    if bool(ids) != bool(provenance["used_area"]) or record["area"] != provenance["used_area"]:
        raise ValueError("Frozen scope resolution and membership disagree")
    return (ids or None), provenance, [manifest_path, summary_path, path]


def run(args, capture, reading):
    # Import numeric/pipeline dependencies only after all CLI and capture checks.
    import numpy as np
    sys.path.insert(0, str(ROOT / "test"))
    from artefact.facet_joint_candidate import freeze_reference
    from artefact.facet_retrieval_pipeline import retrieve_prepared_query
    from artefact.facet_scope_recruitment import recruit_with_verified_area

    bundle = args.query_bundle
    captures_path = bundle / "query_capture/query_captures.json"
    sm = read(STATIC / "manifest.json")
    qm = read(bundle / "query_snapshot/manifest.json")
    for filename in ("graph.json", "arrays.npz"):
        verify_hash(STATIC / filename, sm["output_sha256"][filename])
    for filename in ("queries.json", "arrays.npz"):
        verify_hash(bundle / "query_snapshot" / filename, qm["output_sha256"][filename])
    verify_hash(captures_path, qm["completed_capture_sha256"])
    graph = read(STATIC / "graph.json")
    metadata = read(bundle / "query_snapshot/queries.json")
    query = next(q for q in metadata["queries"] if q["id"] == capture["generation_id"])
    if any(graph[key] != metadata[key] for key in ("chunk_ids", "graph_tags")):
        raise ValueError("Frozen graph/query vocabulary or chunk order mismatch")
    tags, indices = query["tags"], query["query_tag_indices"]
    if (tags != capture["clean_tags"] or tags != [metadata["query_tags"][i] for i in indices]
            or query["description"] != capture["description"] or tuple(graph["facets"]) != FACETS
            or [c["chunkId"] for c in graph["chunks"]] != graph["chunk_ids"]):
        raise ValueError("Frozen query fields, facet order or chunk alignment mismatch")
    by_tag = {v["t"]: v["facets"] for v in reading["values"]}
    if len(by_tag) != len(reading["values"]) or set(by_tag) != set(tags):
        raise ValueError("SCORE must retain exactly every captured query tag once")
    weights = np.array([[by_tag[t][f] for f in FACETS] for t in tags])
    groups = defaultdict(list)
    for i, chunk in enumerate(graph["chunks"]):
        for product in chunk["scope"].get("product", []):
            for channel in chunk["scope"].get("channel", []):
                groups[product["node_id"], channel["node_id"]].append(i)
    pairs = source_adjacency(graph["chunks"], np)
    input_paths = [Path(__file__), captures_path, STATIC / "manifest.json", STATIC / "graph.json",
                   STATIC / "arrays.npz", bundle / "query_snapshot/manifest.json",
                   bundle / "query_snapshot/queries.json", bundle / "query_snapshot/arrays.npz",
                   ROOT / "test/arms/artefact_v3.py"]
    input_paths += [ROOT / "test/artefact" / name for name in (
        "facet_retrieval_pipeline.py", "facet_joint_candidate.py", "facet_stream_envelope.py",
        "facet_recruitment_candidate.py", "facet_need_frontier.py")]
    area_ids, area_provenance = None, None
    if args.verified_area:
        area_ids, area_provenance, area_paths = frozen_area(capture, reading)
        input_paths += area_paths + [ROOT / "test/artefact/facet_scope_recruitment.py"]
        if area_ids is not None and not set(area_ids) <= set(graph["chunk_ids"]):
            raise ValueError("Frozen scope contains an ineligible chunk")
    input_hashes = {str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p): sha(p) for p in input_paths}
    print(f"Recomputing {args.question_id}, reading {args.reading_index}; {len(graph['chunk_ids'])} chunks.", flush=True)
    with np.load(STATIC / "arrays.npz", allow_pickle=False) as static, np.load(
            bundle / "query_snapshot/arrays.npz", allow_pickle=False) as arrays:
        for edge, ti, ci in zip(graph["edge_ids"], static["edge_tag"], static["edge_chunk"]):
            if edge != graph["chunk_ids"][ci] + "::" + graph["graph_tags"][ti]:
                raise ValueError("Frozen edge endpoint alignment mismatch")
        result = retrieve_prepared_query(
            chunk_rows=graph["chunks"], coefficients=args.coefficients,
            source_character_budget=args.source_character_budget, query_tag_ids=tags,
            edge_ids=graph["edge_ids"], edge_tag_indices=static["edge_tag"],
            edge_chunk_indices=static["edge_chunk"], edge_facets=static["edge_facets"],
            query_facet_weights=weights, query_tag_cosines=arrays["query_tag_graph_cos"][indices],
            query_chunk_cosines=arrays["query_tag_chunk_cos"][indices],
            query_description_cosines=arrays["description_chunk_cos"][query["description_index"]],
            reference=freeze_reference(static["edge_facets"]),
            groups={"shared_product_channel": list(groups.values())}, adjacency_pairs=pairs)
    area_result = None
    if args.verified_area:
        area_result = recruit_with_verified_area(
            chunk_rows=graph["chunks"], joint_scores=result["ranking"]["scores"],
            area_chunk_ids=area_ids, area_provenance=area_provenance,
            source_character_budget=args.source_character_budget)
        result["recruitment"] = area_result["recruitment"]
        by_id = {row["chunk_id"]: row for row in result["ranking"]["rows"]}
        chunks_by_id = {chunk["chunkId"]: chunk for chunk in graph["chunks"]}
        recovery = {row["chunk_id"]: row for row in result["recruitment"]["rows"]}
        result["contexts"] = [{
            "chunk_id": cid, "source_text": chunks_by_id[cid]["source_text"],
            "relpath": chunks_by_id[cid]["relpath"], "locator": chunks_by_id[cid]["locator"],
            "nomination_score": by_id[cid]["score"], "facet_provenance": by_id[cid]["provenance"],
            "recovery": recovery[cid],
        } for cid in result["recruitment"]["selected_chunk_ids"]]
    for path, expected in input_hashes.items():
        verify_hash(ROOT / path, expected)
    ranking = result["ranking"]
    contribution_error = max(abs(row["score"] - sum(w["contribution"] for w in row["provenance"].values() if w))
                             for row in ranking["rows"])
    if contribution_error > 1e-12:
        raise ValueError("Facet contributions do not reconstruct final scores")
    args.output.mkdir(parents=True, exist_ok=False)
    array_path = args.output / "ranking_arrays.npz"
    arrays_out = {key: ranking[key] for key in (
        "scores", "ranks", "per_facet_scores", "direct_scores", "graph_scores", "facet_percentiles")}
    if area_result is not None:
        arrays_out["recruitment_stream_scores"] = area_result["stream_scores"]
    np.savez_compressed(array_path, chunk_ids=graph["chunk_ids"], **arrays_out)
    scope_text = ("Frozen verified-area option: global plus archived area; unresolved area stays global. No new scope inference."
                  if args.verified_area else "Global nomination only; no inferred or named-area recruitment.")
    policy = {**result["policy"], "graph_relations": "Original shared Product+Channel groups and locator adjacency; no Product-only propagation.",
              "scope": scope_text,
              "status": "Experimental prepared-query demonstration, not production retrieval or a validated final weighting policy."}
    if area_result is not None:
        policy["area_recruitment"] = area_result["policy"]
    payload = {"created_utc": datetime.now(timezone.utc).isoformat(), "query_bundle": str(bundle), "question_id": args.question_id,
               "question": capture["question"], "description": capture["description"],
               "generation_id": capture["generation_id"], "reading_id": reading["id"],
               "reading_index": args.reading_index, "query_tags": tags,
               "query_facet_weights": weights.tolist(), "facets": list(FACETS), "policy": policy,
               "input_sha256": input_hashes, "ranking_arrays_sha256": sha(array_path),
               "graph_counts": {"chunks": len(graph["chunk_ids"]), "edges": len(graph["edge_ids"]),
                                "groups": len(groups), "adjacency_pairs": len(pairs)},
               "contribution_sum_max_abs_error": contribution_error,
               "verified_area": None if area_result is None else {
                   "area": area_result["area"], "stream_ids": area_result["stream_ids"],
                   "source": "Archived scope_recruitment/run membership and provenance; scores freshly computed."},
               "ranking": {k: ranking[k] for k in ("rows", "ranked_chunk_ids", "coefficients")},
               "recruitment": result["recruitment"], "contexts": result["contexts"]}
    (args.output / "retrieval.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    r = result["recruitment"]
    lines = ["# Prepared-query retrieval", "", capture["question"], "", f"Description: {capture['description']}", "",
             f"Reading: `{reading['id']}`. Coefficients ({', '.join(FACETS)}): `{args.coefficients}`.", "",
             f"Selected {len(result['contexts'])} chunks, {r['selected_source_characters']:,} / {args.source_character_budget:,} saved source characters.", "",
             "Recomputed through `retrieve_prepared_query`; no saved rankings consumed. Full source texts, original facet witnesses and recovery triggers are in `retrieval.json`. Complete numeric route tensors are in `ranking_arrays.npz`.", "",
             scope_text, "",
             "Original shared Product+Channel/file adjacency and exact-record recovery remain active. No new question interpretation or Product-only propagation occurs. Coefficients are explicit provisional policy. The budget admits complete frontiers, counts overlapping saved source characters and is not production serialized context.", "",
             "| Selected chunk | Recovered depth | Own score | Recovered earlier |", "| --- | ---: | ---: | --- |"]
    for context in result["contexts"]:
        rec = context["recovery"]
        lines.append(f"| `{context['chunk_id']}` | {rec['depth']} | {context['nomination_score']:.6g} | {rec['context_added']} |")
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {len(result['contexts'])} contexts to {args.output}")


def main(argv=None):
    parser, args = parse_args(argv)
    captures = read(args.query_bundle / "query_capture/query_captures.json")["captures"]
    if args.list:
        for capture in captures:
            readings = [r["repeat"] for r in capture["readings"] if r["ok"]]
            print(f"{capture['question_id']}\treadings={readings}\t{capture['question']}")
        return
    matches = [c for c in captures if c["question_id"] == args.question_id]
    if len(matches) != 1:
        parser.error("unknown or ambiguous question ID; use --list")
    readings = [r for r in matches[0]["readings"] if r["repeat"] == args.reading_index and r["ok"]]
    if len(readings) != 1:
        parser.error("reading index is unavailable or unsuccessful; use --list")
    try:
        run(args, matches[0], readings[0])
    except (ValueError, OSError, KeyError, StopIteration) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
