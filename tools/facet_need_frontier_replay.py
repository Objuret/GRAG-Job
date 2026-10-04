"""Replay the frozen cosine-topic routes through four need/facet frontiers.

No model, database, training, or source-derived query changes. The original
envelope is reproduced exactly before its routes enter the new merge module.
"""
from pathlib import Path
import os

for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "4"

import ast
from collections import defaultdict
import json
import numpy as np
import facet_independent_envelope as original

ROOT, BASE, STATIC = original.ROOT, original.BASE, original.STATIC
NEEDS = BASE / "need_selection/needs.json"
OUT = BASE / "need_selection/replay"
MODES = ("joint", "facets", "needs", "need_facets")
read, write, sha = original.read, original.write, original.sha


def need_groups(question, tags):
    """Keep every captured tag, adding shared context to every named need."""
    assert len(tags) == len(set(tags)), "Duplicate captured tag"
    shared = question.get("shared_context_tags", [])
    assert isinstance(shared, list) and len(shared) == len(set(shared))
    assert set(shared) <= set(tags), "Invented shared-context tag"
    groups, members, covered = {}, {}, set()
    for need in question["needs"]:
        nid, member_tags = need["need_id"], need["member_tags"]
        assert isinstance(nid, str) and nid and nid not in groups
        assert isinstance(member_tags, list) and member_tags
        assert len(member_tags) == len(set(member_tags))
        assert set(member_tags) <= set(tags), "Invented need tag"
        retained = set(member_tags) | set(shared)
        groups[nid] = [i for i, tag in enumerate(tags) if tag in retained]
        members[nid] = [tags[i] for i in groups[nid]]
        covered.update(retained)
    assert groups and covered == set(tags), "Every original tag must be retained"
    return groups, members


def validate_frontier(result, chunk_ids, stream_ids, scores):
    rows = result["rows"]
    assert len(rows) == len(chunk_ids)
    assert {r["chunk_id"] for r in rows} == set(chunk_ids)
    assert len({r["chunk_id"] for r in rows}) == len(rows)
    assert scores.shape == (len(stream_ids), len(chunk_ids))
    assert np.isfinite(scores).all() and (scores >= 0).all()
    at = {cid: i for i, cid in enumerate(chunk_ids)}
    stream_at = {sid: i for i, sid in enumerate(stream_ids)}
    assert len(stream_at) == len(stream_ids)
    supported = np.any(scores > 0, axis=0)
    assert result["supported_count"] == int(supported.sum())
    assert set(result["unsupported_chunk_ids"]) == {
        cid for i, cid in enumerate(chunk_ids) if not supported[i]
    }
    depth_counts = defaultdict(int)
    for row in rows:
        ci = at[row["chunk_id"]]
        positive_streams = {sid for si, sid in enumerate(stream_ids) if scores[si, ci] > 0}
        assert set(row["stream_ranks"]) == positive_streams
        assert all(isinstance(rank, int) and rank > 0 for rank in row["stream_ranks"].values())
        assert all(scores[stream_at[sid], ci] > 0 for sid in row["winning_streams"])
        if not supported[ci]:
            assert row["depth"] is None
            assert row["first_position"] is None and row["last_position"] is None
            assert not row["stream_ranks"] and not row["winning_streams"]
        else:
            assert isinstance(row["depth"], int) and row["depth"] > 0
            assert row["depth"] == min(row["stream_ranks"].values())
            assert 1 <= row["first_position"] <= row["last_position"] <= int(supported.sum())
            depth_counts[row["depth"]] += 1
    cumulative = 0
    previous_depth = 0
    intervals = {}
    for frontier in result["frontier_sizes"]:
        assert frontier["depth"] > previous_depth
        assert frontier["size"] == depth_counts[frontier["depth"]]
        first = cumulative + 1
        cumulative += frontier["size"]
        assert cumulative == frontier["cumulative_size"]
        intervals[frontier["depth"]] = (first, cumulative)
        previous_depth = frontier["depth"]
    assert cumulative == result["supported_count"]
    for row in rows:
        if row["depth"] is not None:
            assert (row["first_position"], row["last_position"]) == intervals[row["depth"]]


def completion_interval(focal_rows, frontiers):
    """Bound unique candidates needed without imposing order inside a frontier."""
    if any(row["depth"] is None for row in focal_rows):
        return {"depth": None, "unique_count_interval": None,
                "unique_candidates_through_completion_depth": None,
                "reason": "At least one required source is unsupported."}
    depth = max(row["depth"] for row in focal_rows)
    frontier = next(f for f in frontiers if f["depth"] == depth)
    preceding = frontier["cumulative_size"] - frontier["size"]
    required_at_final_depth = sum(row["depth"] == depth for row in focal_rows)
    return {"depth": depth,
            "unique_count_interval": [preceding + required_at_final_depth,
                                      frontier["cumulative_size"]],
            "unique_candidates_through_completion_depth": frontier["cumulative_size"],
            "required_sources_at_final_depth": required_at_final_depth}


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError("Refusing to overwrite frontier replay evidence")
    module_path = ROOT / "test/artefact/facet_need_frontier.py"
    if not NEEDS.is_file() or not module_path.is_file():
        raise RuntimeError("Needs and frontier module must exist before execution")
    from artefact.facet_need_frontier import build_streams, merge_frontiers

    graph = read(STATIC / "graph.json")
    with np.load(STATIC / "arrays.npz") as archive:
        static = {key: archive[key] for key in archive.files}
    meta = read(BASE / "query_snapshot/queries.json")
    with np.load(BASE / "query_snapshot/arrays.npz") as archive:
        arrays = {key: archive[key] for key in archive.files}
    captures = read(BASE / "query_capture/query_captures.json")["captures"]
    manifest = read(BASE / "query_snapshot/manifest.json")
    needs = read(NEEDS)
    for path, expected in needs["input_sha256"].items():
        assert sha(BASE / path) == expected, "Need interpretation inputs changed"
    need_questions = {q["question_id"]: q for q in needs["questions"]}
    assert len(need_questions) == len(needs["questions"]) == 7
    queries = {q["id"]: q for q in meta["queries"]}
    assert len(queries) == len(captures) == 7
    assert set(need_questions) == {c["question_id"] for c in captures}
    assert sum(len(c["readings"]) for c in captures) == 14
    assert all(r["ok"] for c in captures for r in c["readings"])
    for name, expected in manifest["output_sha256"].items():
        assert sha(BASE / "query_snapshot" / name) == expected
    for key in ("graph_tags", "chunk_ids"):
        assert meta[key] == graph[key]
    assert tuple(graph["facets"]) == original.FACETS
    ids = graph["chunk_ids"]
    assert len(ids) == 4808 and [c["chunkId"] for c in graph["chunks"]] == ids
    for edge, tag_index, chunk_index in zip(graph["edge_ids"], static["edge_tag"], static["edge_chunk"]):
        assert edge == ids[chunk_index] + "::" + graph["graph_tags"][tag_index]
    assert len(static["edge_facets"]) == 57204
    reference = original.freeze_reference(static["edge_facets"])
    graph_groups = defaultdict(list)
    for ci, chunk in enumerate(graph["chunks"]):
        for product in chunk["scope"].get("product", []):
            for channel in chunk["scope"].get("channel", []):
                graph_groups[product["node_id"], channel["node_id"]].append(ci)
    relations = {"shared_product_channel": list(graph_groups.values())}
    arm_path = ROOT / "test/arms/artefact_v3.py"
    tree = ast.parse(arm_path.read_text(encoding="utf-8"))
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in {"_csr", "file_adjacency"}]
    assert len(funcs) == 2
    namespace = {"np": np, "json": json}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(arm_path), "exec"), namespace)
    adjacency = namespace["file_adjacency"](graph["chunks"])
    pairs = [(i, int(j)) for i in range(len(ids))
             for j in adjacency["members"][adjacency["ptr"][i]:adjacency["ptr"][i + 1]] if i < j]

    # Validate query/need membership without reading the focal target protocol.
    prepared = []
    for capture in captures:
        query = queries[capture["generation_id"]]
        tags, indices = query["tags"], query["query_tag_indices"]
        assert [meta["query_tags"][i] for i in indices] == tags == capture["clean_tags"]
        assert query["description"] == capture["description"]
        question_needs = need_questions[capture["question_id"]]
        assert question_needs["clean_tags"] == tags
        assert question_needs["description"] == query["description"]
        groups, members = need_groups(question_needs, tags)
        prepared.append((capture, query, groups, members))

    paths = [Path(__file__), Path(original.__file__), module_path, arm_path, NEEDS,
             ROOT / "test/tests/test_facet_need_frontier.py",
             BASE / "need_selection/PROTOCOL.md", BASE / "need_selection/NEEDS.md",
             BASE / "questions.json",
             STATIC / "graph.json", STATIC / "arrays.npz", BASE / "protocol.json",
             BASE / "EVALUATION.md", BASE / "query_capture/query_captures.json",
             BASE / "query_snapshot/queries.json", BASE / "query_snapshot/arrays.npz",
             BASE / "query_snapshot/manifest.json",
             ROOT / "test/artefact/facet_joint_candidate.py",
             ROOT / "test/artefact/facet_stream_envelope.py",
             BASE.parent / "source_first/FACET_STREAM_COMPARISON.md"]
    paths += [BASE / "facet_stream_envelope" / (r["id"] + "_intact.json")
              for c in captures for r in c["readings"]]
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "protocol.json", {
        "input_sha256": hashes, "modes": list(MODES), "readings": 14,
        "topic_input": "Original frozen cosine-topic column; no learned-topic intervention.",
        "unchanged": "Full original graph, routes, reference population, captures, weights, D/Q, coefficients and hop discount.",
        "stream_input": "Elementwise maximum of original direct_scores and graph_scores [facet,query,chunk], plus original nonnegative Q.",
        "need_groups": [{"question_id": c["question_id"], "query_tags": q["tags"],
                         "indices": groups, "tags": members} for c, q, groups, members in prepared],
        "reference_edges": len(static["edge_facets"]), "chunks": len(ids),
        "graph_groups": len(graph_groups), "adjacency_pairs": len(pairs),
        "model_calls": 0, "db_calls": 0,
        "focal_analysis": "Read old target protocol only after all rankings are persisted; report local depth directions, tie intervals, per-stream ranks and unique selected-pair completion counts.",
        "scope": "Exploratory recruitment comparison on previously inspected cases, not heldout validation.",
        "unsupported": "Zero-support chunks retain null depth/position and no finite stream rank."})

    records = []
    for capture, query, groups, members in prepared:
        indices, tags = query["query_tag_indices"], query["tags"]
        q = np.maximum(np.asarray(arrays["description_chunk_cos"][query["description_index"]], dtype=float), 0)
        for reading in capture["readings"]:
            rid = reading["id"]
            by_tag = {v["t"]: v["facets"] for v in reading["values"]}
            assert set(by_tag) == set(tags)
            weights = np.array([[by_tag[tag][facet] for facet in original.FACETS] for tag in tags])
            result = original.rank_facet_stream_envelope(
                chunk_ids=ids, query_tag_ids=tags, edge_ids=graph["edge_ids"],
                edge_tag_indices=static["edge_tag"], edge_chunk_indices=static["edge_chunk"],
                edge_facets=static["edge_facets"], query_facet_weights=weights,
                query_tag_cosines=arrays["query_tag_graph_cos"][indices],
                query_chunk_cosines=arrays["query_tag_chunk_cos"][indices],
                query_description_cosines=arrays["description_chunk_cos"][query["description_index"]],
                reference=reference, groups=relations, adjacency_pairs=pairs, facets_enabled=True)
            frozen_rows = read(BASE / "facet_stream_envelope" / (rid + "_intact.json"))["rows"]
            compact = [{key: row[key] for key in ("rank", "chunk_id", "score")} for row in result["rows"]]
            assert compact == frozen_rows, "Original envelope scores/ranks are not exactly reproduced"
            route_path = OUT / (rid + "_routes.npz")
            np.savez_compressed(route_path, direct_scores=result["direct_scores"],
                                graph_scores=result["graph_scores"], Q=q,
                                chunk_ids=np.asarray(ids), query_tag_ids=np.asarray(tags),
                                facet_ids=np.asarray(original.FACETS), query_facet_weights=weights)
            write(OUT / (rid + "_original_envelope.json"), {"rows": compact, "exact_match": True})
            route_scores = np.maximum(result["direct_scores"], result["graph_scores"])
            for mode in MODES:
                stream_ids, scores = build_streams(route_scores, q, groups, mode)
                stream_ids, scores = list(stream_ids), np.asarray(scores)
                if mode == "joint":
                    assert scores.shape == (1, len(ids))
                    assert np.array_equal(scores[0], result["scores"]), "Joint stream changed original scores"
                frontier = merge_frontiers(ids, stream_ids, scores)
                validate_frontier(frontier, ids, stream_ids, scores)
                score_path = OUT / (rid + "_" + mode + "_streams.npz")
                np.savez_compressed(score_path, stream_scores=scores,
                                    stream_ids=np.asarray(stream_ids), chunk_ids=np.asarray(ids))
                result_path = OUT / (rid + "_" + mode + ".json")
                record = {"reading_id": rid, "question_id": capture["question_id"],
                          "generation_id": capture["generation_id"], "mode": mode,
                          "stream_ids": stream_ids, "need_query_indices": groups,
                          "need_tags": members, "stream_scores_file": score_path.name,
                          "stream_scores_sha256": sha(score_path),
                          "route_file": route_path.name, "route_sha256": sha(route_path),
                          **frontier}
                write(result_path, record)
                records.append({"reading_id": rid, "question_id": capture["question_id"],
                                "mode": mode, "file": result_path.name,
                                "sha256": sha(result_path)})
            print(rid, "exact original match; four frontiers saved", flush=True)

    # Source preferences enter only after every ranking has been generated.
    assert len(records) == 56
    targets = {t["question_id"]: t for t in read(BASE / "protocol.json")["targets"]}
    summary = []
    for record in records:
        result = read(OUT / record["file"])
        target = targets[record["question_id"]]
        focal_ids = target.get("required_within_selected_pair") or [target["preferred"], target["comparison"]]
        rows = {r["chunk_id"]: r for r in result["rows"]}
        focal = {cid: rows[cid] for cid in focal_ids}
        direction = None
        if target.get("preferred"):
            preferred, comparison = (rows[target[key]]["depth"] for key in ("preferred", "comparison"))
            if preferred is None and comparison is None:
                direction = "both_unsupported"
            elif preferred is None:
                direction = "comparison_first"
            elif comparison is None or preferred < comparison:
                direction = "preferred_first"
            elif preferred == comparison:
                direction = "tie"
            else:
                direction = "comparison_first"
        summary.append({**record, "source_group": target["source_group"], "focal": focal,
                        "pair_depth_direction": direction,
                        "selected_pair_completion": completion_interval(list(focal.values()), result["frontier_sizes"]),
                        "supported_count": result["supported_count"],
                        "stream_ids": result["stream_ids"],
                        "interpretation": "Position intervals bound a unique-candidate prefix under arbitrary within-frontier ordering; no retrieval cutoff or complete-answer claim."})
    assert all(sha(ROOT / path) == value for path, value in hashes.items()), "Frozen inputs changed"
    write(OUT / "summary.json", summary)
    output_hashes = {p.name: sha(p) for p in OUT.iterdir() if p.is_file()}
    write(OUT / "verification.json", {"inputs_unchanged": True,
          "original_exact_score_and_rank_matches": 14, "frontier_rankings": len(records),
          "chunks_per_ranking": len(ids), "all_original_tags_retained": True,
          "shared_context_attached_to_every_need": True,
          "no_unsupported_chunk_has_finite_depth_or_position_or_stream_rank": True,
          "focal_targets_read_after_all_rankings": True, "output_sha256": output_hashes})
    print("Completed 14 exact envelope reproductions and 56 frontier rankings", flush=True)


if __name__ == "__main__":
    main()
