#!/usr/bin/env python
"""
refresh_graph.py - rebuild the graphify knowledge graph(s) in one command.

v1 and v2 live in SEPARATE graphs (shared class/file names otherwise fabricate
phantom v1<->v2 edges that contradict the no-v1-imports rule):

  ACTIVE graph  -> graphify-out/        : v2/ + external state/handoff docs + root
                                          canon (CLAUDE.md, README.md). What agents use.
  v1 REFERENCE  -> v1/graphify-out/      : frozen v1 stack, on demand only.

Usage (exposed as `regraph` in PowerShell + bash):
  regraph              rebuild the ACTIVE graph
  regraph --v1         rebuild the v1 REFERENCE graph
  regraph --force      allow a >10% node drop (deliberate rescopes)
  regraph --no-agent   don't auto-invoke Claude; just print a worklist and stop

Code edits rebuild on their own. When a DOC changed/appeared, the prose must be read
by a model: the script hands the worklist to a headless Claude Code (`claude -p`), which
extracts each doc (with bridge edges into the existing concepts), then the script
finishes the rebuild. No model available -> it writes the worklist and stops loudly.
See graphify-out/REFRESH.md.
"""
from __future__ import annotations
import os, sys, json, re, hashlib, subprocess
from pathlib import Path

# ---- CONFIG ---------------------------------------------------------------
REPO_ROOT = Path(r"A:\exjobbet\repo")
OUT = REPO_ROOT / "graphify-out"
V2_ROOT = REPO_ROOT / "v2"
V1_ROOT = REPO_ROOT / "v1"
ROOT_DOCS = [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "README.md"]
EXTERNAL = [
    (Path(r"A:\Coding\skills\handoff\exjobbet-monorepo"), "handoff/exjobbet-monorepo/"),
    (Path(r"A:\Coding\skills\handoff\exjobbet"),          "handoff/exjobbet/"),
    (Path(r"A:\Coding\skills\state\exjobbet"),            "state/exjobbet/"),
]
EXTERNAL_PARENT = Path(r"A:\Coding\skills")   # --add-dir for the headless agent
# ---------------------------------------------------------------------------

os.environ["GRAPHIFY_OUT"] = str(OUT)
os.chdir(REPO_ROOT)

from graphify.detect import detect, save_manifest
from graphify.extract import collect_files, extract
from graphify.cache import check_semantic_cache, save_cached, save_semantic_cache
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json

SIDECAR = OUT / ".external_cache"
PICKUP = OUT / ".pickup"
INIT_MARKER = OUT / ".graph_refresh_init"
WORKLIST = OUT / ".refresh_worklist.json"
CONCEPT_INDEX = OUT / ".concept_index.txt"
FORCE = "--force" in sys.argv
NO_AGENT = "--no-agent" in sys.argv or os.environ.get("REGRAPH_NO_AGENT") == "1"
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


def find_claude():
    bases = [Path(os.environ["USERPROFILE"]) / e / "extensions"
             for e in (".cursor", ".vscode", ".vscode-insiders", ".windsurf")]
    cands = []
    for b in bases:
        if b.is_dir():
            cands += b.glob("anthropic.claude-code-*/resources/native-binary/claude.exe")
    return sorted(cands, key=lambda p: p.parent.parent.parent.name)[-1] if cands else None


def collect_code(file_lists: dict) -> list:
    out = []
    for f in file_lists.get("code", []):
        fp = Path(f)
        out.extend(collect_files(fp) if fp.is_dir() else [fp])
    return out


def words(paths) -> int:
    n = 0
    for p in paths:
        p = Path(p)
        if p.is_file():
            n += len(p.read_text(encoding="utf-8", errors="ignore").split())
    return n


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
            if fp.exists() and json.loads(fp.read_text(encoding="utf-8")).get("hash") == body_hash(p):
                frags.append(json.loads(fp.read_text(encoding="utf-8"))); continue
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


_AGENT_PROMPT = (
    "You are updating a graphify knowledge graph, non-interactively. Do exactly this:\n"
    "1. Read the worklist JSON at {worklist}.\n"
    "2. Read the concept index at its 'concept_index' path (TSV lines `node_id<TAB>label`) "
    "- these are concepts ALREADY in the graph.\n"
    "3. For EACH item in items[]: read the file at item.real. Extract its named "
    "concepts/decisions/mechanisms as nodes (file_type one of rationale|concept|document). "
    "CRUCIAL: add bridge edges FROM your new nodes TO existing concept ids the file "
    "discusses, copying the id VERBATIM from the concept index (relations: references|"
    "conceptually_related_to|semantically_similar_to|rationale_for). Node ids: lowercase "
    "[a-z0-9_] from filename+entity, unique, no suffixes. Every edge needs confidence_score "
    "(EXTRACTED=1.0; INFERRED one of 0.95/0.85/0.75/0.65/0.55).\n"
    "4. Write ONLY a JSON object {{\"nodes\":[...],\"edges\":[...]}} to item.pickup using the "
    "Write tool (one pickup per item).\n"
    "5. Do NOT run refresh_graph.py or rebuild anything. After writing every pickup, stop."
)


def resolve_docs(repo_uncached, ext_changed, scope):
    """Build the worklist, hand it to a headless Claude to extract, persist results.
    Exits(2) if no model is available or the agent didn't produce output."""
    PICKUP.mkdir(parents=True, exist_ok=True)
    items = []
    for d in repo_uncached:
        items.append({"kind": "repo", "real": d,
                      "source_file": Path(d).resolve().relative_to(REPO_ROOT).as_posix(),
                      "pickup": str(PICKUP / (hashlib.sha256(d.lower().encode()).hexdigest()[:16] + ".json"))})
    for d in ext_changed:
        items.append({"kind": "external", "real": d, "source_file": ext_label(Path(d)),
                      "pickup": str(PICKUP / (hashlib.sha256(d.lower().encode()).hexdigest()[:16] + ".json"))})
    WORKLIST.write_text(json.dumps(
        {"scope": scope, "concept_index": str(CONCEPT_INDEX), "items": items},
        indent=2, ensure_ascii=False), encoding="utf-8")

    claude = None if NO_AGENT else find_claude()
    if not claude:
        print(f"\n*** {len(items)} doc(s) need model extraction ***")
        for it in items:
            print("  ", it["kind"], ":", it["real"])
        why = "--no-agent set" if NO_AGENT else "no Claude CLI found"
        print(f"\nNot rebuilding ({why}). Process graphify-out/.refresh_worklist.json "
              f"then re-run. See graphify-out/REFRESH.md.")
        sys.exit(2)

    for it in items:
        Path(it["pickup"]).unlink(missing_ok=True)
    print(f"\nhanding {len(items)} doc(s) to Claude Code ({claude.parent.parent.parent.name}) for extraction...")
    env = dict(os.environ, REGRAPH_NO_AGENT="1")
    r = subprocess.run(
        [str(claude), "-p", _AGENT_PROMPT.format(worklist=str(WORKLIST)),
         "--permission-mode", "acceptEdits", "--add-dir", str(EXTERNAL_PARENT),
         "--allowedTools", "Read", "Write", "Glob", "Grep"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        sys.exit(f"claude extraction failed (exit {r.returncode}):\n{(r.stderr or r.stdout)[-800:]}")

    missing = []
    for it in items:
        pf = Path(it["pickup"])
        if not pf.exists():
            missing.append(it["real"]); continue
        frag = json.loads(pf.read_text(encoding="utf-8"))
        nodes = frag.get("nodes", []); edges = frag.get("edges", [])
        for x in nodes + edges:
            x["source_file"] = it["source_file"]   # stamp authoritative provenance
        if it["kind"] == "repo":
            save_semantic_cache(nodes, edges, [], root=REPO_ROOT)
        else:
            frag_path(Path(it["real"])).write_text(json.dumps(
                {"source_file": it["source_file"], "hash": body_hash(Path(it["real"])),
                 "nodes": nodes, "edges": edges}, ensure_ascii=False), encoding="utf-8")
        pf.unlink(missing_ok=True)
    if missing:
        sys.exit("agent did not produce extractions for:\n  " + "\n  ".join(missing))
    print(f"extracted {len(items)} doc(s) via Claude Code.")


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
    print("scanning v2 + root + external (active graph)...")
    det = detect(V2_ROOT)
    code = collect_code(det["files"])
    repo_docs = [f for k in ("document", "paper", "image") for f in det["files"].get(k, [])]
    repo_docs += [str(p) for p in ROOT_DOCS if p.is_file()]
    print(f"  v2 code: {len(code)} | docs (v2+root): {len(repo_docs)}")

    cn, ce, ch, uncached = check_semantic_cache(repo_docs, root=REPO_ROOT)
    if not INIT_MARKER.exists():
        seed_first_run(uncached)
        cn, ce, ch, uncached = check_semantic_cache(repo_docs, root=REPO_ROOT)
    ast = extract(code, cache_root=REPO_ROOT) if code else {"nodes": [], "edges": []}
    ext_frags, ext_changed, ext_current = scan_external()
    write_concept_index(ast["nodes"] + cn + [n for fr in ext_frags for n in fr["nodes"]])

    if uncached or ext_changed:
        resolve_docs(uncached, ext_changed, "active")
        cn, ce, ch, uncached = check_semantic_cache(repo_docs, root=REPO_ROOT)
        ext_frags, ext_changed, ext_current = scan_external()
        if uncached or ext_changed:
            sys.exit("still missing extractions after agent run; aborting.")

    nodes, edges = assemble(
        ast["nodes"] + cn + [x for fr in ext_frags for x in fr["nodes"]],
        ast["edges"] + ce + [x for fr in ext_frags for x in fr["edges"]])
    detection = {"total_files": len(code) + len(repo_docs) + len(ext_current),
                 "total_words": words(repo_docs) + words(ext_current)}
    save_manifest(det.get("all_files") or det["files"])
    rebuild(nodes, edges, ch, detection, OUT, REPO_ROOT, "ACTIVE graph (v2+ext+root)")


def main_v1():
    print("scanning v1 (reference graph)...")
    det = detect(V1_ROOT)
    code = collect_code(det["files"])
    v1_docs = [f for k in ("document", "paper", "image") for f in det["files"].get(k, [])]
    print(f"  v1 code: {len(code)} | docs: {len(v1_docs)}")
    cn, ce, ch, uncached = check_semantic_cache(v1_docs, root=REPO_ROOT)
    ast = extract(code, cache_root=REPO_ROOT) if code else {"nodes": [], "edges": []}
    write_concept_index(ast["nodes"] + cn)
    if uncached:
        resolve_docs(uncached, [], "v1")
        cn, ce, ch, uncached = check_semantic_cache(v1_docs, root=REPO_ROOT)
        if uncached:
            sys.exit("still missing extractions after agent run; aborting.")
    nodes, edges = assemble(ast["nodes"] + cn, ast["edges"] + ce)
    detection = {"total_files": det.get("total_files", 0), "total_words": det.get("total_words", 0)}
    rebuild(nodes, edges, ch, detection, V1_ROOT / "graphify-out", V1_ROOT, "v1 REFERENCE graph")


if __name__ == "__main__":
    (main_v1 if "--v1" in sys.argv else main_active)()
