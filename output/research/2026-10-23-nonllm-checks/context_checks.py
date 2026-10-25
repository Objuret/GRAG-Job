"""The two non-LLM context scores on the three final runs, under four readings of the same
handed-over text, with every match traced back to the record it came from.

    R0 as evaluated   gold record = its string values joined by spaces; texts as handed over
                      (must give the stored scores again)
    R1 split          R0's gold records; each handed-over text cut into its records
    R2 same form      gold record and handed-over records both in record_text form; cut into records
    R3 content only   both sides only the record's content (message, document body and feedback,
                      transcript, chat, description, PR summary and review comments); cut into records

RAGAS's own NonLLMContextRecall and NonLLMContextPrecisionWithReference formulas, on Levenshtein
similarity (rapidfuzz, the measure RAGAS uses). Writes context_checks.json and prints a summary.
"""
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "prod")]
from harness.orchestrator import DEFAULT_CORPUS  # noqa: E402
from harness.record_text import ARTIFACT_TYPES, record_text  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402
from rapidfuzz.process import cdist  # noqa: E402
from ragas.metrics import NonLLMContextPrecisionWithReference, NonLLMContextRecall  # noqa: E402

RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261023T021439Z"}
READINGS = ("R0", "R1", "R2", "R3")
recall_m, prec_m = NonLLMContextRecall(), NonLLMContextPrecisionWithReference()
assert recall_m.threshold == 0.5 and prec_m.threshold == 0.5
SENTINEL = "\x00CONTENT\x00"


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def leaves(value):
    """The evaluation's gold record text: every string value, joined by spaces."""
    parts = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for w in v.values():
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)
    walk(value)
    return " ".join(parts).strip()


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
    """record_text up to where the record's content starts."""
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
full_text = {}


def rt(i):
    if i not in full_text:
        full_text[i] = record_text(kind_of[i], raw[i])
    return full_text[i]


def pieces_of(arm, row):
    """Each handed-over text cut into its records: [(text, record id, whole)]."""
    texts = row["contexts"]
    out = []
    if arm == "artefact":
        lists = row["meta"]["chunk_ids"]
        if len(lists) != len(texts):
            raise SystemExit(f"{arm} {row['id']}: {len(texts)} texts, {len(lists)} id lists")
        for text, ids in zip(texts, lists):
            ids = [str(i) for i in ids]
            if len(ids) == 1:
                out.append((text, ids[0], text == rt(ids[0])))
                continue
            whole = [rt(i) for i in ids]
            if not "\n\n".join(whole).startswith(text):
                raise SystemExit(f"{arm} {row['id']}: a text is not its records joined by a blank line")
            at = 0
            for i, piece in zip(ids, whole):
                if at >= len(text):
                    break
                part = text[at:at + len(piece)]
                out.append((part, i, part == piece))
                at += len(piece) + 2
        return out
    ids = [str(i) for i in row["context_ids"]]
    cut = (row["meta"].get("char_budget") or {}).get("boundary")
    text_ids = ids + ([str(cut["id"])] if cut else [])
    if len(text_ids) != len(texts):
        raise SystemExit(f"{arm} {row['id']}: {len(texts)} texts, {len(text_ids)} ids")
    for n, (t, i) in enumerate(zip(texts, text_ids)):
        whole = t == rt(i)
        if not whole and not (cut and n == len(texts) - 1):
            raise SystemExit(f"{arm} {row['id']}: text {n} is not the record its id names")
        out.append((t, i, whole))
    return out


def piece_content(piece, i, whole):
    k, rec = kind_of[i], raw[i]
    if whole:
        return content(k, rec)
    h = header(k, rec)
    if piece.startswith(h):
        return piece[len(h):]
    if h.startswith(piece):
        return ""
    raise SystemExit(f"a cut piece of {i} does not start with its record's header")


def sims(refs, texts):
    return 1 - cdist(refs, texts, scorer=Levenshtein.normalized_distance, workers=-1)


report = {}
for arm, folder in RUNS.items():
    d = ROOT / "output/k=chars" / folder
    stored = {(r["question_id"], r["metric"]): r for r in rows(d / "eval_results.jsonl")}
    means = defaultdict(list)
    recall_trace = {r: Counter() for r in READINGS[1:]}
    prec_trace = {r: Counter() for r in READINGS[1:]}
    other_pairs = {r: [] for r in ("R2", "R3")}
    reproduced = looked = 0
    pieces_total = empty_pieces = whole_pieces = 0
    for row in rows(d / "arm_outputs.jsonl"):
        q = row["id"]
        if stored[(q, "context_recall_nonllm")]["status"] != "ok":
            continue
        cited = [c for c in cites[q] if c in raw]
        given = {str(i) for i in row["context_ids"]}
        pieces = pieces_of(arm, row)
        pieces_total += len(pieces)
        whole_pieces += sum(w for _, _, w in pieces)
        pid = [i for _, i, _ in pieces]
        pwhole = [w for _, _, w in pieces]
        pc = [piece_content(t, i, w) for t, i, w in pieces]
        keep = [n for n, c in enumerate(pc) if c]
        empty_pieces += len(pieces) - len(keep)
        reading = {
            "R0": ([leaves(raw[c]) for c in cited], list(row["contexts"]), None, None),
            "R1": ([leaves(raw[c]) for c in cited], [t for t, _, _ in pieces], pid, pwhole),
            "R2": ([rt(c) for c in cited], [t for t, _, _ in pieces], pid, pwhole),
            "R3": ([content(kind_of[c], raw[c]) for c in cited], [pc[n] for n in keep],
                   [pid[n] for n in keep], [pwhole[n] for n in keep]),
        }
        for name, (refs, texts, ids, whole) in reading.items():
            m = sims(refs, texts)
            best_ref, best_text = m.max(axis=1), m.max(axis=0)
            rec = recall_m._compute_score(list(best_ref))
            prec = prec_m._calculate_average_precision([1 if s >= 0.5 else 0 for s in best_text])
            means[(name, "recall")].append(rec)
            means[(name, "precision")].append(prec)
            if name == "R0":
                looked += 2
                reproduced += abs(rec - stored[(q, "context_recall_nonllm")]["value"]) < 1e-9
                reproduced += abs(prec - stored[(q, "context_precision_nonllm")]["value"]) < 1e-9
                continue
            t = recall_trace[name]
            for j, c in enumerate(cited):
                hit = m[j] > 0.5
                mine = [n for n in range(len(texts)) if ids[n] == c]
                if not hit.any():
                    t["not found, " + ("passed whole" if any(whole[n] for n in mine)
                                       else "passed only in part" if mine else "not passed")] += 1
                    continue
                if any(hit[n] and whole[n] for n in mine):
                    t["found: itself, whole"] += 1
                elif any(hit[n] for n in mine):
                    t["found: itself, in part"] += 1
                else:
                    n = int(np.argmax(m[j]))
                    o = ids[n]
                    t["found: only through another record"] += 1
                    if name in other_pairs:
                        cs = 1 - Levenshtein.normalized_distance(content(kind_of[c], raw[c]),
                                                                 content(kind_of[o], raw[o]))
                        other_pairs[name].append({"question": q, "cited": c, "matched": o,
                                                  "kind_cited": kind_of[c], "kind_matched": kind_of[o],
                                                  "similarity": float(m[j, n]), "content_similarity": cs})
            pt = prec_trace[name]
            cset = set(cited)
            for n in range(len(texts)):
                by_text, by_id = best_text[n] >= 0.5, ids[n] in cset
                pt[("relevant by text" if by_text else "not by text") + ", "
                   + ("cited" if by_id else "not cited")] += 1
    id_means = {m: float(np.mean([r["value"] for (q, mm), r in stored.items() if mm == m and r["status"] == "ok"]))
                for m in ("context_recall_id", "context_precision_id")}
    report[arm] = {
        "reproduced": f"{reproduced} of {looked}",
        "pieces": {"total": pieces_total, "whole": whole_pieces, "empty_content_dropped_in_R3": empty_pieces},
        "id_means": id_means,
        "means": {f"{a} {b}": float(np.mean(v)) for (a, b), v in means.items()},
        "recall_trace": {k: dict(v) for k, v in recall_trace.items()},
        "precision_trace": {k: dict(v) for k, v in prec_trace.items()},
        "other_record_matches": other_pairs,
    }

(HERE / "context_checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
for arm, r in report.items():
    print(f"\n=== {arm}: stored scores given again by R0: {r['reproduced']}; pieces {r['pieces']}")
    print(f"  id: recall {r['id_means']['context_recall_id']:.3f}  precision {r['id_means']['context_precision_id']:.3f}")
    for name in READINGS:
        print(f"  {name}: recall {r['means'][name + ' recall']:.3f}  precision {r['means'][name + ' precision']:.3f}")
    for name in READINGS[1:]:
        print(f"  {name} recall trace: {r['recall_trace'][name]}")
        print(f"  {name} precision trace: {r['precision_trace'][name]}")
    for name in ("R2", "R3"):
        pairs = r["other_record_matches"][name]
        near = sum(p["content_similarity"] > 0.5 for p in pairs)
        kinds = Counter(f"{p['kind_cited']}->{p['kind_matched']}" for p in pairs)
        print(f"  {name} other-record matches: {len(pairs)}; content alone over 0.5: {near}; kinds {dict(kinds)}")
