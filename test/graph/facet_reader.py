"""Every facet ANSWER on disk turned into a value by a fixed reader.

Premise = the model's plain-prose answer for one (chunk, tag, facet), written by
test/graph/facet_answers.py. Hypothesis = one pole sentence per facet with the tag
inserted. Value = P(entailment) under MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli,
fp32; P(contradiction) and the margin P(entail) - P(contradict) are kept beside it.
The label order is read off the checkpoint's own config, never assumed.

No model call to claude-*, no graph read, no graph write.

    .venv/Scripts/python.exe test/graph/facet_reader.py --db herb-eval-volmax --overlay

Two machines: the laptop builds the pairs, the desktop's GPU scores them.

    # laptop
    python test/graph/facet_reader.py --db herb-eval-volmax --pairs-out pairs.jsonl
    # desktop (A:\\exjobbet\\repo\\.venv\\Scripts\\python.exe, facet_reader_gpu.py only)
    python facet_reader_gpu.py --pairs pairs.jsonl --out scores.jsonl
    # laptop
    python test/graph/facet_reader.py --db herb-eval-volmax --scores-in scores.jsonl --overlay

Writes output/facet_values/<db>/values.jsonl and meta.json, and with --overlay
output/facet_values/<db>.overlay.json in the shape of facet_stats' overlay (topic left
null: the arm reads it as the cosine).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

READER_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
READER_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
BATCH = 128
MAX_LEN = 256

FACETS = ("temporal", "why", "activity", "concreteness")
# the overlay carries five columns in facet_stats' order; topic stays null, the arm's cosine
OVERLAY_FACETS = ["topic", *FACETS]

# the pole sentence per facet, the tag inserted verbatim
HYPOTHESES = {
    "temporal": "What the text says about {tag} depends on when it happened, is happening or is due.",
    "why": "The text gives the reason for {tag}: why it is there or what it is for.",
    "activity": "{tag} is being done, changed, decided or carried out in the text.",
    "concreteness": "The text gives particulars about {tag}: figures, amounts, parts, cases or examples.",
}

RUN_ID = os.environ.get("HERB_TAG_RUN_ID", "pilot_full_herb")


def hypothesis(facet: str, tag: str) -> str:
    return HYPOTHESES[facet].replace("{tag}", tag)


def answer_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def answers_dir(db: str) -> Path:
    return ROOT / "output" / "facet_answers" / db


def values_dir(db: str) -> Path:
    return ROOT / "output" / "facet_values" / db


def overlay_path(db: str) -> Path:
    return ROOT / "output" / "facet_values" / f"{db}.overlay.json"


def is_complete(rec) -> bool:
    """the same completeness facet_answers writes: every given phrase answered."""
    if not isinstance(rec, dict) or not isinstance(rec.get("edges"), list):
        return False
    given, answered = rec.get("given"), rec.get("answered")
    if not isinstance(given, int) or not isinstance(answered, int):
        return False
    return answered == given and bool(rec.get("complete"))


def read_answers(directory: Path) -> tuple[list, dict]:
    """(chunk records, counts). Only complete files; .failed.json and manifests skipped."""
    counts = {"files": 0, "chunks": 0, "failed": 0, "unreadable": 0, "incomplete": 0,
              "edges": 0, "edges_skipped": 0}
    prompt_shas, recs = set(), []
    for p in sorted(Path(directory).glob("*.json")):
        if p.name.startswith("manifest."):
            continue
        if p.name.endswith(".failed.json"):
            counts["failed"] += 1
            continue
        counts["files"] += 1
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            counts["unreadable"] += 1
            continue
        if not is_complete(rec):
            counts["incomplete"] += 1
            continue
        counts["chunks"] += 1
        if rec.get("prompt_sha256"):
            prompt_shas.add(rec["prompt_sha256"])
        recs.append(rec)
    counts["prompt_sha256"] = sorted(prompt_shas)
    return recs, counts


def build_pairs(recs: list, counts: dict | None = None) -> list:
    """One pair per (chunk, tag, facet), sorted by premise+hypothesis length so a batch
    holds texts of one size. An edge missing any of the four answers is skipped."""
    pairs = []
    for rec in recs:
        chunk_id = rec.get("chunk_id")
        for edge in rec.get("edges", []):
            tag = edge.get("t")
            answers = {f: edge.get(f) for f in FACETS}
            if not chunk_id or not isinstance(tag, str) or not tag.strip() or not all(
                    isinstance(a, str) and a.strip() for a in answers.values()):
                if counts is not None:
                    counts["edges_skipped"] = counts.get("edges_skipped", 0) + 1
                continue
            if counts is not None:
                counts["edges"] = counts.get("edges", 0) + 1
            for facet in FACETS:
                premise = answers[facet]
                pairs.append({"chunk_id": chunk_id, "tag": tag, "facet": facet,
                              "answer_sha": answer_sha(premise),
                              "premise": premise, "hypothesis": hypothesis(facet, tag)})
    pairs.sort(key=lambda d: (len(d["premise"]) + len(d["hypothesis"]), d["chunk_id"],
                              d["tag"], d["facet"]))
    for i, d in enumerate(pairs):
        d["id"] = i
    return pairs


def value_key(row: dict) -> tuple:
    return (row["chunk_id"], row["tag"], row["facet"], row["answer_sha"])


def read_values(path: Path) -> dict:
    """what is already scored, keyed by (chunk, tag, facet, answer sha) — the resume."""
    done = {}
    if not path.is_file():
        return done
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if all(k in row for k in ("chunk_id", "tag", "facet", "answer_sha")):
                done[value_key(row)] = row
    return done


def pending(pairs: list, done: dict) -> list:
    return [p for p in pairs if value_key(p) not in done]


def write_jsonl(path: Path, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path


def row_from_score(pair: dict, probs: dict) -> dict:
    entail, contra = float(probs["entailment"]), float(probs["contradiction"])
    return {"chunk_id": pair["chunk_id"], "tag": pair["tag"], "facet": pair["facet"],
            "value": entail, "contradiction": contra, "margin": entail - contra,
            "answer_sha": pair["answer_sha"]}


def merge_scores(pairs: list, scores_path: Path) -> list:
    """scores.jsonl from the GPU box carries the identity fields back; a line that lost
    them is matched on its pair id."""
    by_id = {p["id"]: p for p in pairs}
    rows, unmatched = [], 0
    with Path(scores_path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            s = json.loads(line)
            if all(k in s for k in ("chunk_id", "tag", "facet", "answer_sha")):
                pair = s
            else:
                pair = by_id.get(s.get("id"))
                if pair is None:
                    unmatched += 1
                    continue
            rows.append(row_from_score(pair, {"entailment": s["entailment"],
                                              "contradiction": s["contradiction"]}))
    if unmatched:
        raise SystemExit(f"[facet_reader] {unmatched} score lines carry neither the identity "
                         f"fields nor a known pair id — rebuild the pairs from the same answers dir")
    return rows


def label_index(config) -> dict:
    """entailment / neutral / contradiction column, read off the checkpoint."""
    mapping = getattr(config, "label2id", None) or {}
    out = {}
    for name, idx in mapping.items():
        key = str(name).strip().lower()
        for want in ("entailment", "neutral", "contradiction"):
            if key == want or key.startswith(want[:6]):
                out[want] = int(idx)
    missing = [w for w in ("entailment", "neutral", "contradiction") if w not in out]
    if missing:
        raise SystemExit(f"[facet_reader] the checkpoint's label2id {mapping} does not name {missing}")
    return out


def score_pairs(pairs: list, batch: int = BATCH, max_len: int = MAX_LEN,
                model_name: str = READER_MODEL, revision: str = READER_REVISION) -> tuple[list, dict]:
    """Local scoring, fp32, CUDA when there is one. Imports torch only here."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[facet_reader] loading {model_name}@{revision[:8]} on {device}, fp32 ...", flush=True)
    tok = AutoTokenizer.from_pretrained(model_name, revision=revision)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, revision=revision, dtype=torch.float32).to(device).eval()
    cols = label_index(model.config)
    print(f"[facet_reader] labels {cols}; {len(pairs)} pairs, batch {batch}, max_len {max_len}",
          flush=True)
    rows, t0, last = [], time.time(), 0.0
    with torch.inference_mode():
        for i in range(0, len(pairs), batch):
            chunk = pairs[i:i + batch]
            enc = tok([p["premise"] for p in chunk], [p["hypothesis"] for p in chunk],
                      return_tensors="pt", truncation=True, padding=True, max_length=max_len)
            enc = {k: v.to(device) for k, v in enc.items()}
            probs = torch.softmax(model(**enc).logits.float(), dim=-1).cpu().numpy()
            for p, row in zip(chunk, probs):
                rows.append(row_from_score(p, {"entailment": row[cols["entailment"]],
                                               "contradiction": row[cols["contradiction"]]}))
            now = time.time()
            if now - last > 1.0 or i + batch >= len(pairs):
                last = now
                rate = len(rows) / max(now - t0, 1e-9)
                print(f"[facet_reader] {len(rows)}/{len(pairs)} pairs  {rate:.1f}/s  "
                      f"{now - t0:.0f}s", flush=True)
    wall = time.time() - t0
    return rows, {"where": f"{socket.gethostname()} {device} fp32", "device": device,
                  "wall_s": round(wall, 1),
                  "pairs_per_s": round(len(rows) / wall, 1) if wall > 0 else None}


def report(rows: list) -> None:
    print(f"\n{'facet':14}{'n':>7}{'min':>8}{'5%':>8}{'median':>8}{'95%':>8}{'max':>8}{'distinct':>10}")
    for facet in FACETS:
        v = sorted(r["value"] for r in rows if r["facet"] == facet)
        if not v:
            print(f"{facet:14}{0:7d}" + "       -" * 5 + "         -")
            continue
        def pct(q):
            return v[min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))]
        print(f"{facet:14}{len(v):7d}{v[0]:8.3f}{pct(0.05):8.3f}{statistics.median(v):8.3f}"
              f"{pct(0.95):8.3f}{v[-1]:8.3f}{len({round(x, 6) for x in v}):10d}")


def write_overlay(rows: list, db: str, source: Path, meta: dict, dest: Path | None = None) -> Path:
    """the arm's input, shaped like output/facet_stats/<db>.overlay.json: five weights per
    edge in OVERLAY_FACETS order, topic null (the arm reads topic as the cosine)."""
    by_edge = {}
    for r in rows:
        by_edge.setdefault((r["chunk_id"], r["tag"]), {})[r["facet"]] = r["value"]
    body = {"database": db, "run_id": RUN_ID, "facets": OVERLAY_FACETS,
            "method": ("temporal, why, activity, concreteness: P(entailment) of the facet's pole "
                       "sentence against the model's answer for that (chunk, tag, facet); "
                       "topic null, the arm's cosine(Tag.emb, Chunk.desc_emb)"),
            "tool": "test/graph/facet_reader.py",
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "reader_model": READER_MODEL, "reader_revision": READER_REVISION,
            "hypotheses": dict(HYPOTHESES),
            "answers_prompt_sha256": meta.get("answers_prompt_sha256"),
            "source": str(source), "edges": [
                {"tag": tag, "chunkId": chunk_id, "anchor": "answer",
                 "weights": [None] + [vals.get(f) for f in FACETS]}
                for (chunk_id, tag), vals in sorted(by_edge.items())]}
    p = Path(dest) if dest is not None else overlay_path(db)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("NEO4J_DATABASE", "herb-eval-volmax"),
                    help="names output/facet_answers/<db> and output/facet_values/<db>")
    ap.add_argument("--answers", default=None, help="an answers dir other than the db's")
    ap.add_argument("--out", default=None, help="a values dir other than the db's")
    ap.add_argument("--pairs-out", default=None, help="write the pairs and stop; no model loaded")
    ap.add_argument("--scores-in", default=None, help="merge scores from the GPU box; no model loaded")
    ap.add_argument("--overlay", action="store_true", help="also write <db>.overlay.json")
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--max-len", type=int, default=MAX_LEN)
    ap.add_argument("--limit", type=int, default=None, help="first N pairs, for a smoke")
    args = ap.parse_args(argv)

    t0 = time.time()
    src = Path(args.answers) if args.answers else answers_dir(args.db)
    out = Path(args.out) if args.out else values_dir(args.db)
    values_path = out / "values.jsonl"
    print(f"[facet_reader] answers {src}", flush=True)
    if not src.is_dir():
        raise SystemExit(f"[facet_reader] no answers dir at {src}")
    recs, counts = read_answers(src)
    print(f"[facet_reader] {counts['chunks']} complete chunks, {counts['failed']} failed, "
          f"{counts['incomplete']} incomplete, {counts['unreadable']} unreadable  "
          f"({time.time() - t0:.0f}s)", flush=True)
    pairs = build_pairs(recs, counts)
    if args.limit:
        pairs = pairs[:args.limit]
    done = read_values(values_path)
    todo = pending(pairs, done)
    print(f"[facet_reader] {counts['edges']} edges, {counts['edges_skipped']} edges skipped, "
          f"{len(pairs)} pairs, {len(pairs) - len(todo)} already scored, {len(todo)} to read",
          flush=True)

    if args.pairs_out:
        p = write_jsonl(Path(args.pairs_out), todo)
        print(f"[facet_reader] pairs -> {p}  ({len(todo)} lines, no model loaded)", flush=True)
        return

    if args.scores_in:
        new_rows = merge_scores(pairs, Path(args.scores_in))
        run = {"where": f"merged from {args.scores_in}", "device": None,
               "wall_s": None, "pairs_per_s": None}
    elif todo:
        new_rows, run = score_pairs(todo, args.batch, args.max_len)
    else:
        new_rows, run = [], {"where": "nothing to read", "device": None,
                             "wall_s": None, "pairs_per_s": None}

    merged = dict(done)
    for r in new_rows:
        merged[value_key(r)] = r
    rows = [merged[k] for k in sorted(merged)]
    write_jsonl(values_path, rows)
    meta = {"database": args.db, "answers_dir": str(src),
            "answers_prompt_sha256": counts["prompt_sha256"],
            "reader_model": READER_MODEL, "reader_revision": READER_REVISION,
            "dtype": "float32", "batch": args.batch, "max_len": args.max_len,
            "hypotheses": dict(HYPOTHESES), "facets": list(FACETS),
            "pairs": len(pairs), "pairs_read_this_run": len(new_rows),
            "values": len(rows), "chunks": counts["chunks"],
            "edges": counts["edges"], "edges_skipped": counts["edges_skipped"],
            "files": counts["files"], "failed": counts["failed"],
            "incomplete": counts["incomplete"], "unreadable": counts["unreadable"],
            "tool": "test/graph/facet_reader.py",
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "python": platform.python_version(), "host": socket.gethostname(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **run}
    (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[facet_reader] {len(rows)} values -> {values_path}", flush=True)
    report(rows)
    if args.overlay:
        dest = out.parent / f"{args.db}.overlay.json"
        print(f"\n[facet_reader] overlay -> {write_overlay(rows, args.db, values_path, meta, dest)}")


if __name__ == "__main__":
    sys.exit(main())
