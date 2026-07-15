#!/usr/bin/env python
"""
refresh_graph.py - rebuild the graphify navigation graph in one command.

The graph covers graphify-out/ : v3/ + the in-repo (gitignored) state/handoff
docs (docs/state, docs/handoff) + root canon (CLAUDE.md, README.md).

Usage (exposed as `regraph` in PowerShell + bash):
  regraph          rebuild the graph
  regraph --force  allow a >10% node drop (deliberate rescopes)

Code edits rebuild on their own. If a DOC changed/appeared, the prose has to be read
by a model first - the script can't do that itself, so it lists which docs need it and
stops. To finish: tell Claude "update the graph" and it'll read them, then re-run.
See graphify-out/REFRESH.md.
"""
from __future__ import annotations
import os, sys, json, re, hashlib, subprocess
from pathlib import Path

# ---- CONFIG ---------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent
OUT = REPO_ROOT / "graphify-out"
V3_ROOT = REPO_ROOT / "v3"
ROOT_DOCS = [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "README.md"]
EXTERNAL = [
    (REPO_ROOT / "docs" / "handoff", "handoff/"),
    (REPO_ROOT / "docs" / "state",   "state/"),
]
# ---------------------------------------------------------------------------

os.environ["GRAPHIFY_OUT"] = str(OUT)
os.chdir(REPO_ROOT)

from graphify.detect import detect, save_manifest
from graphify.extract import collect_files, extract
from graphify.cache import check_semantic_cache, save_cached
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json

SIDECAR = OUT / ".external_cache"
INIT_MARKER = OUT / ".graph_refresh_init"
WORKLIST = OUT / ".refresh_worklist.json"
CONCEPT_INDEX = OUT / ".concept_index.txt"
FORCE = "--force" in sys.argv
_FM = re.compile(r"^---[ \t]*\r?$", re.MULTILINE)


def body_hash(p: Path) -> str:
    raw = p.read_bytes()
    if p.suffix.lower() == ".md":
        text = raw.decode(errors="replace")
        m = _FM.match(text)
        if m:
            c = _FM.search(text, m.end())
            if c:
                raw = text[c.start() + 3:].encode()
    return hashlib.sha256(raw).hexdigest()


def real_path_for(source_file: str):
    for base, prefix in EXTERNAL:
        if source_file.startswith(prefix):
            return base / source_file[len(prefix):]
    return None


def ext_label(real: Path) -> str:
    for base, prefix in EXTERNAL:
        try:
            return prefix + real.relative_to(base).as_posix()
        except ValueError:
            continue
    return real.name


def frag_path(real: Path) -> Path:
    return SIDECAR / (hashlib.sha256(str(real).lower().encode()).hexdigest()[:16] + ".json")


def collect_code(file_lists: dict) -> list:
    out = []
    for f in file_lists.get("code", []):
        fp = Path(f)
        out.extend(collect_files(fp) if fp.is_dir() else [fp])
    return out


def words(paths) -> int:
    return sum(len(Path(p).read_text(encoding="utf-8", errors="ignore").split())
               for p in paths if Path(p).is_file())


def write_concept_index(nodes: list) -> None:
    types = {"document", "paper", "rationale", "concept"}
    lines = sorted("{}\t{}".format(n["id"], n.get("label", ""))
                   for n in nodes if n.get("file_type") in types)
    CONCEPT_INDEX.write_text("\n".join(lines), encoding="utf-8")


def scan_external():
    SIDECAR.mkdir(parents=True, exist_ok=True)
    current, changed, frags, seen = [], [], [], set()
    for base, prefix in EXTERNAL:
        if not base.is_dir():
            print(f"  ! external folder missing: {base}")
            continue
        for p in sorted(base.glob("*.md")):
            current.append(str(p)); seen.add(frag_path(p).name)
            fp = frag_path(p)
            if fp.exists():
                fr = json.loads(fp.read_text(encoding="utf-8"))
                if fr.get("hash") == body_hash(p):
                    frags.append(fr); continue
            changed.append(str(p))
    for fp in SIDECAR.glob("*.json"):
        if fp.name not in seen:
            fp.unlink(); print(f"  - dropped deleted external doc fragment: {fp.name}")
    return frags, changed, current


def seed_first_run(repo_uncached) -> None:
    SIDECAR.mkdir(parents=True, exist_ok=True)
    gp = OUT / "graph.json"
    if gp.exists():
        g = json.loads(gp.read_text(encoding="utf-8"))
        pref = tuple(p for _, p in EXTERNAL)
        by_src = {}
        for n in g["nodes"]:
            s = str(n.get("source_file", ""))
            if s.startswith(pref):
                by_src.setdefault(s, {"nodes": [], "edges": []})["nodes"].append(
                    {k: v for k, v in n.items() if k != "community"})
        for e in g.get("links", []):
            s = str(e.get("source_file", ""))
            if s.startswith(pref):
                by_src.setdefault(s, {"nodes": [], "edges": []})["edges"].append(e)
        for src, frag in by_src.items():
            real = real_path_for(src)
            if real and real.is_file():
                frag_path(real).write_text(json.dumps(
                    {"source_file": src, "hash": body_hash(real), **frag}, ensure_ascii=False),
                    encoding="utf-8")
    for d in repo_uncached:
        if Path(d).is_file():
            save_cached(Path(d), {"nodes": [], "edges": []}, root=REPO_ROOT, kind="semantic")
    INIT_MARKER.write_text("1", encoding="utf-8")
    print("first run: seeded external fragments + registered empty repo docs")


def need_docs_stop(repo_uncached, ext_changed, scope):
    """A doc changed/appeared and needs reading by a model. Record what, and stop -
    a script can't read prose. Finishing it = tell Claude 'update the graph'."""
    items = ([{"kind": "repo", "real": d, "source_file": Path(d).resolve().relative_to(REPO_ROOT).as_posix()}
              for d in repo_uncached]
             + [{"kind": "external", "real": d, "source_file": ext_label(Path(d))} for d in ext_changed])
    WORKLIST.write_text(json.dumps(
        {"scope": scope, "concept_index": str(CONCEPT_INDEX), "items": items},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(items)} doc(s) changed and need reading by a model:")
    for it in items:
        print("  -", it["real"])
    print("\nA script can't read prose. To finish: tell Claude \"update the graph\".")
    print("(It reads the docs, then re-runs this. Details: graphify-out/REFRESH.md.)")
    sys.exit(2)


def assemble(node_sources, edge_sources):
    nodes, seen = [], set()
    for n in node_sources:
        if n["id"] not in seen:
            seen.add(n["id"]); nodes.append(n)
    eseen, edges = set(), []
    for e in edge_sources:
        if e.get("source") in seen and e.get("target") in seen:
            key = (e["source"], e["target"], e.get("relation"))
            if key not in eseen:
                eseen.add(key); edges.append(e)
    return nodes, edges


def rebuild(nodes, edges, hyper, detection, out_dir: Path, export_cwd: Path, label: str):
    G = build_from_json({"nodes": nodes, "edges": edges, "hyperedges": hyper,
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
        label, G.number_of_nodes(), G.number_of_edges(), len(communities)))
    print("  html:", tail[-1] if tail else "(export skipped)")
    WORKLIST.unlink(missing_ok=True)


def main_active():
    print("scanning v3 + root + external (active graph)...")
    det = detect(V3_ROOT)
    # the nav graph is v3 CODE + DESIGN DOCS, never the benchmark dataset or run outputs
    _skip = [(V3_ROOT / "data").resolve(), (V3_ROOT / "output").resolve()]
    for _k in list(det["files"].keys()):
        det["files"][_k] = [f for f in det["files"][_k]
                            if not any(d == (rp := Path(f).resolve()) or d in rp.parents
                                       for d in _skip)]
    code = collect_code(det["files"])
    repo_docs = [f for k in ("document", "paper", "image") for f in det["files"].get(k, [])]
    repo_docs += [str(p) for p in ROOT_DOCS if p.is_file()]
    print(f"  v3 code: {len(code)} | docs (v3+root): {len(repo_docs)}")

    cn, ce, ch, uncached = check_semantic_cache(repo_docs, root=REPO_ROOT)
    if not INIT_MARKER.exists():
        seed_first_run(uncached)
        cn, ce, ch, uncached = check_semantic_cache(repo_docs, root=REPO_ROOT)
    ast = extract(code, cache_root=REPO_ROOT) if code else {"nodes": [], "edges": []}
    ext_frags, ext_changed, ext_current = scan_external()
    write_concept_index(ast["nodes"] + cn + [n for fr in ext_frags for n in fr["nodes"]])

    if uncached or ext_changed:
        need_docs_stop(uncached, ext_changed, "active")

    nodes, edges = assemble(
        ast["nodes"] + cn + [x for fr in ext_frags for x in fr["nodes"]],
        ast["edges"] + ce + [x for fr in ext_frags for x in fr["edges"]])
    detection = {"total_files": len(code) + len(repo_docs) + len(ext_current),
                 "total_words": words(repo_docs) + words(ext_current)}
    save_manifest(det.get("all_files") or det["files"])
    rebuild(nodes, edges, ch, detection, OUT, REPO_ROOT, "ACTIVE graph (v3+ext+root)")


if __name__ == "__main__":
    main_active()
