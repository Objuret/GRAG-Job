"""What the content-only (R3) matches between different records actually are, on the three final
runs: for recall, the cited records found only through another passed record; for precision, the
passed records that are not cited but count as relevant. Counts, length and similarity profiles,
and seeded samples of both texts side by side. Writes inspect_matches.json."""
import copy
import json
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "prod")]
from harness.orchestrator import DEFAULT_CORPUS  # noqa: E402
from harness.record_text import ARTIFACT_TYPES, record_text  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402
from rapidfuzz.process import cdist  # noqa: E402

RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261023T021439Z"}
SENTINEL = "\x00CONTENT\x00"
SHORT = 60


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def content(kind, rec):
    if kind == "slack":
        return rec["Message"]["User"]["text"]
    if kind == "documents":
        return rec["content"] + ("\n" + rec["feedback"] if rec.get("feedback") else "")
    if kind == "meeting_transcripts":
        return rec["transcript"]
    if kind == "meeting_chats":
        return rec["text"]
    if kind == "urls":
        return rec["description"]
    if kind == "prs":
        return "\n".join([rec["summary"]] + [r["comment"] for r in rec["reviews"]])
    raise KeyError(kind)


def header(kind, rec):
    marked = copy.deepcopy(rec)
    if kind == "slack":
        marked["Message"]["User"]["text"] = SENTINEL
    else:
        marked[{"documents": "content", "meeting_transcripts": "transcript", "meeting_chats": "text",
                "urls": "description", "prs": "summary"}[kind]] = SENTINEL
    return record_text(kind, marked).split(SENTINEL)[0]


raw, kind_of = {}, {}
for pf in sorted((Path(DEFAULT_CORPUS) / "products").glob("*.json")):
    data = json.loads(pf.read_text(encoding="utf-8"))
    for kind in ARTIFACT_TYPES:
        for rec in data.get(kind, []) or []:
            aid = rec.get("id")
            if aid is not None and str(aid) not in raw:
                raw[str(aid)], kind_of[str(aid)] = rec, kind
cites = {q["id"]: [str(c) for c in q["citations"]] for q in rows(ROOT / "data/questions.jsonl")}


def pieces_of(arm, row):
    texts = row["contexts"]
    if arm == "artefact":
        out = []
        for text, ids in zip(texts, row["meta"]["chunk_ids"]):
            ids = [str(i) for i in ids]
            if len(ids) == 1:
                out.append((text, ids[0], text == record_text(kind_of[ids[0]], raw[ids[0]])))
                continue
            at = 0
            for i in ids:
                piece = record_text(kind_of[i], raw[i])
                if at >= len(text):
                    break
                part = text[at:at + len(piece)]
                out.append((part, i, part == piece))
                at += len(piece) + 2
        return out
    ids = [str(i) for i in row["context_ids"]]
    cut = (row["meta"].get("char_budget") or {}).get("boundary")
    text_ids = ids + ([str(cut["id"])] if cut else [])
    return [(t, i, t == record_text(kind_of[i], raw[i])) for t, i in zip(texts, text_ids)]


def piece_content(piece, i, whole):
    k, rec = kind_of[i], raw[i]
    if whole:
        return content(k, rec)
    h = header(k, rec)
    return piece[len(h):] if piece.startswith(h) else ""


def norm(s):
    return " ".join(s.lower().split())


def profile(pairs):
    """pairs: (text a, text b, similarity, kind a, kind b)"""
    if not pairs:
        return {"n": 0}
    la = np.array([len(a) for a, *_ in pairs])
    lb = np.array([len(b) for _, b, *_ in pairs])
    s = np.array([p[2] for p in pairs])
    return {"n": len(pairs),
            "same text (case and spaces aside)": sum(norm(a) == norm(b) for a, b, *_ in pairs),
            f"both at most {SHORT} chars": int(((la <= SHORT) & (lb <= SHORT)).sum()),
            "median chars a / b": [float(np.median(la)), float(np.median(lb))],
            "similarity 1.0 / 0.8-1 / 0.65-0.8 / 0.5-0.65": [int((s >= 0.9999).sum()), int(((s >= 0.8) & (s < 0.9999)).sum()),
                                                             int(((s >= 0.65) & (s < 0.8)).sum()), int((s < 0.65).sum())],
            "kinds": dict(Counter(f"{p[3]}->{p[4]}" for p in pairs))}


checks = json.loads((HERE / "context_checks.json").read_text(encoding="utf-8"))
rng = random.Random(7)
out = {}
for arm, folder in RUNS.items():
    rec_pairs = [(content(kind_of[p["cited"]], raw[p["cited"]]), content(kind_of[p["matched"]], raw[p["matched"]]),
                  p["similarity"], p["kind_cited"], p["kind_matched"])
                 for p in checks[arm]["other_record_matches"]["R3"]]
    prec_pairs = []
    for row in rows(ROOT / "output/k=chars" / folder / "arm_outputs.jsonl"):
        cited = [c for c in cites[row["id"]] if c in raw]
        cset = set(cited)
        pieces = [(piece_content(t, i, w), i) for t, i, w in pieces_of(arm, row)]
        pieces = [(c, i) for c, i in pieces if c]
        refs = [content(kind_of[c], raw[c]) for c in cited]
        m = 1 - cdist(refs, [c for c, _ in pieces], scorer=Levenshtein.normalized_distance, workers=-1)
        for n, (pc, i) in enumerate(pieces):
            if i in cset or m[:, n].max() < 0.5:
                continue
            j = int(np.argmax(m[:, n]))
            prec_pairs.append((pc, refs[j], float(m[j, n]), kind_of[i], kind_of[cited[j]]))
    out[arm] = {"recall: cited found only through another record": profile(rec_pairs),
                "precision: passed, not cited, counted relevant": profile(prec_pairs)}
    print(f"\n=== {arm}")
    for name, pairs in (("recall: cited found only through another record", rec_pairs),
                        ("precision: passed, not cited, counted relevant", prec_pairs)):
        print(f"  {name}: {json.dumps(out[arm][name])}")
        for a, b, s, ka, kb in rng.sample(pairs, min(8, len(pairs))):
            print(f"    [{s:.2f} {ka}] {a[:110]!r}\n            vs {b[:110]!r}")
(HERE / "inspect_matches.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
