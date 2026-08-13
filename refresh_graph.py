#!/usr/bin/env python
"""
refresh_graph.py - rebuild the graphify navigation graph in one command.

The graph covers the v3/ code: every source file under v3/, minus the benchmark
dataset (v3/data) and the run outputs (v3/output). Structure comes from the AST -
no model calls, a few seconds, one command.

Usage (exposed as `regraph` in PowerShell + bash):
  regraph          rebuild the graph
  regraph --force  allow a >10% node drop (deliberate rescopes)

This is the only rebuild path; it owns the scope. `graphify --update` rescopes to
the whole repo and is never used here. See graphify-out/REFRESH.md.
"""
from __future__ import annotations
import os, sys, json, re, subprocess, time
from pathlib import Path

print("refresh_graph: starting (loading graphify)...", flush=True)

# ---- CONFIG ---------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent
OUT = REPO_ROOT / "graphify-out"
V3_ROOT = REPO_ROOT / "v3"
SKIP = [V3_ROOT / "data", V3_ROOT / "output"]
# ---------------------------------------------------------------------------

os.environ["GRAPHIFY_OUT"] = str(OUT)
os.chdir(REPO_ROOT)

from graphify.detect import detect, save_manifest
from graphify.extract import collect_files, extract
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json

FORCE = "--force" in sys.argv


def collect_code(file_lists: dict) -> list:
    out = []
    for f in file_lists.get("code", []):
        fp = Path(f)
        out.extend(collect_files(fp) if fp.is_dir() else [fp])
    return out


def words(paths) -> int:
    return sum(len(Path(p).read_text(encoding="utf-8", errors="ignore").split())
               for p in paths if Path(p).is_file())


def rebuild(nodes, edges, detection, out_dir: Path, export_cwd: Path, label: str):
    G = build_from_json({"nodes": nodes, "edges": edges, "hyperedges": [],
                         "input_tokens": 0, "output_tokens": 0})
    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    deg = dict(G.degree())
    labels = {}
    for cid, ns in communities.items():
        top = max(ns, key=lambda x: deg.get(x, 0))
        t = re.sub(r"\s+", " ", str(G.nodes[top].get("label", top))).strip()
        labels[cid] = (t[:40].rstrip() + "...") if len(t) > 40 else t

    out_dir.mkdir(parents=True, exist_ok=True)
    gp = out_dir / "graph.json"
    if gp.exists() and not FORCE:
        prev = len(json.loads(gp.read_text(encoding="utf-8")).get("nodes", []))
        if G.number_of_nodes() < 0.9 * prev:
            sys.exit(f"refusing to write {label}: {G.number_of_nodes()} nodes vs {prev} "
                     f"(>10% drop). Re-run with --force if intentional.")
    questions = suggest_questions(G, communities, labels)
    report = generate(G, communities, cohesion, labels, gods, surprises, detection,
                      {"input": 0, "output": 0}, ".", suggested_questions=questions)
    (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    to_json(G, communities, str(gp), force=True)
    (out_dir / ".graphify_labels.json").write_text(
        json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, GRAPHIFY_OUT="graphify-out")
    r = subprocess.run([sys.executable, "-m", "graphify", "export", "html"],
                       cwd=str(export_cwd), env=env, capture_output=True, text=True)
    tail = (r.stdout or r.stderr or "").strip().splitlines()
    print("\n{}: {} nodes, {} edges, {} communities".format(
        label, G.number_of_nodes(), G.number_of_edges(), len(communities)), flush=True)
    print("  html:", tail[-1] if tail else "(export skipped)", flush=True)


def main():
    t0 = time.time()
    print("scanning v3 code...", flush=True)
    det = detect(V3_ROOT)
    skip = [d.resolve() for d in SKIP]
    for kind in list(det["files"].keys()):
        det["files"][kind] = [f for f in det["files"][kind]
                              if not any(d == (rp := Path(f).resolve()) or d in rp.parents
                                         for d in skip)]
    code = collect_code(det["files"])
    print(f"  v3 code: {len(code)} files", flush=True)

    ast = extract(code, cache_root=REPO_ROOT) if code else {"nodes": [], "edges": []}
    detection = {"total_files": len(code), "total_words": words(code)}
    save_manifest(det.get("all_files") or det["files"])
    rebuild(ast["nodes"], ast["edges"], detection, OUT, REPO_ROOT, "graph (v3 code)")
    print(f"  done in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
