"""How the artefact's two nonllm scores and two id scores move under three readings of the same
handed-over text. RAGAS's own formulas, checked first against every stored score. Counts and
scores only; no question, answer, gold or text is printed.

nonllm  as run       the texts as the answer model got them (must give the stored scores)
        split        each artefact chunk split into its records, one retrieved text per record
        split+form   the same, each whole record written in the baselines' form (record_text)
id      as stored    whole records handed over (the 2026-10-21 correction included)
        no slices    a document counted only when the slices handed over hold its whole text
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Coding\exjobbet\GRAG-Job")
sys.path[:0] = [str(ROOT / "prod"), str(ROOT / "test")]
from harness.record_text import ARTIFACT_TYPES, record_text  # noqa: E402
from ragas.metrics import NonLLMContextPrecisionWithReference, NonLLMContextRecall  # noqa: E402
from ragas.metrics._string import DistanceMeasure, NonLLMStringSimilarity  # noqa: E402

RUNS = {"lucene": "lucene__gold100__cb72000__20261008T234209Z",
        "vector": "vector__gold100__cb72000__20261017T061242Z",
        "artefact": "artefact_v4__gold100__cb72000__20261020T041923Z"}
HERB = ROOT / "data/raw/Salesforce__HERB"


def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def leaves(value):
    """prod/eval/ragas.py _string_leaves: the record's string values joined by spaces."""
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


gold_text, kind_of, main_text = {}, {}, {}
for pf in sorted((HERB / "products").glob("*.json")):
    data = json.loads(pf.read_text(encoding="utf-8"))
    for kind in ARTIFACT_TYPES:
        for rec in data.get(kind, []) or []:
            aid = rec.get("id")
            if aid is None or aid in gold_text:
                continue
            gold_text[aid] = leaves(rec)
            kind_of[str(aid)] = kind
            main_text[str(aid)] = rec.get("content") or rec.get("transcript") or rec.get("text") or ""
gold_text = {str(k): v for k, v in gold_text.items()}
gold_ids = {r["id"] for r in rows(ROOT / "data/gold100.jsonl")}
cites = {q["id"]: [str(c) for c in q["citations"]] for q in rows(ROOT / "data/questions.jsonl")
         if q["id"] in gold_ids}

lev = NonLLMStringSimilarity(distance_measure=DistanceMeasure.LEVENSHTEIN).distance_measure_map[
    DistanceMeasure.LEVENSHTEIN]
recall_m, prec_m = NonLLMContextRecall(), NonLLMContextPrecisionWithReference()
assert recall_m.threshold == 0.5 and prec_m.threshold == 0.5


def sim(a, b):
    return 1 - lev.normalized_distance(a, b)


def nonllm(retrieved, refs):
    m = np.array([[sim(rc, ref) for rc in retrieved] for ref in refs])
    rec = recall_m._compute_score(list(m.max(axis=1)))
    prec = prec_m._calculate_average_precision([1 if s >= prec_m.threshold else 0 for s in m.max(axis=0)])
    return rec, prec


def stored(arm):
    out = {}
    for r in rows(ROOT / "output/k=chars" / RUNS[arm] / "eval_results.jsonl"):
        out[(r["question_id"], r["metric"])] = r["value"]
    return out


def compare(name, pairs):
    up = [b - a for a, b in pairs if b > a + 1e-12]
    down = [a - b for a, b in pairs if b < a - 1e-12]
    print(f"    {name}: up on {len(up)} (by {min(up, default=0):.3f} to {max(up, default=0):.3f}), "
          f"down on {len(down)} (by {min(down, default=0):.3f} to {max(down, default=0):.3f}), "
          f"the same on {len(pairs) - len(up) - len(down)}; "
          f"mean {np.mean([a for a, _ in pairs]):.3f} -> {np.mean([b for _, b in pairs]):.3f}")


# the baselines: the stored nonllm scores given again by these formulas
for arm in ("lucene", "vector"):
    st = stored(arm)
    same = 0
    for r in rows(ROOT / "output/k=chars" / RUNS[arm] / "arm_outputs.jsonl"):
        refs = [gold_text[c] for c in cites[r["id"]] if c in gold_text]
        rec, prec = nonllm(r["contexts"], refs)
        same += abs(rec - st[(r["id"], "context_recall_nonllm")]) < 1e-9
        same += abs(prec - st[(r["id"], "context_precision_nonllm")]) < 1e-9
    print(f"{arm}: stored nonllm scores given again: {same} of 200")

# the artefact
st = stored("artefact")
res = {"run": [], "split": [], "form": []}
idp = {"stored": [], "noslice": []}
same_n = same_id = 0
dropped_cited = dropped_q = 0
for r in rows(ROOT / "output/k=chars" / RUNS["artefact"] / "arm_outputs.jsonl"):
    q = r["id"]
    refs = [gold_text[c] for c in cites[q] if c in gold_text]
    texts, id_lists = r["contexts"], r["meta"]["chunk_ids"]
    cut = r["meta"]["char_budget"].get("boundary")
    split, form = [], []
    whole_ids, slice_chars, json_whole = [], {}, set()
    for n, (text, ids) in enumerate(zip(texts, id_lists)):
        whole_text = not (cut and n == len(texts) - 1)
        if not text.startswith("{"):
            split.append(text)
            form.append(text)
            if whole_text:
                whole_ids += [str(i) for i in ids]
                for i in ids:
                    slice_chars[str(i)] = slice_chars.get(str(i), 0) + len(text)
            continue
        lines = text.split("\n")
        for k, line in enumerate(lines):
            split.append(line)
            complete = whole_text or k < len(lines) - 1
            if complete:
                rec = json.loads(line)
                form.append(record_text(kind_of[str(rec["id"])], rec))
                whole_ids.append(str(rec["id"]))
                json_whole.add(str(rec["id"]))
            else:
                form.append(line)
    a = nonllm(texts, refs)
    same_n += abs(a[0] - st[(q, "context_recall_nonllm")]) < 1e-9
    same_n += abs(a[1] - st[(q, "context_precision_nonllm")]) < 1e-9
    res["run"].append(a)
    res["split"].append(nonllm(split, refs))
    res["form"].append(nonllm(form, refs))
    # id scores, RAGAS's set formulas
    ref, got = set(cites[q]), set(whole_ids)
    s_rec, s_prec = len(ref & got) / len(ref), len(got & ref) / len(got)
    same_id += abs(s_rec - st[(q, "context_recall_id")]) < 1e-9
    same_id += abs(s_prec - st[(q, "context_precision_id")]) < 1e-9
    in_json = json_whole
    drop = {rid for rid, chars in slice_chars.items()
            if rid not in in_json and chars / max(1, len(main_text[rid])) < 0.99}
    kept = got - drop
    n_rec, n_prec = len(ref & kept) / len(ref), len(kept & ref) / len(kept)
    idp["stored"].append((s_rec, s_prec))
    idp["noslice"].append((n_rec, n_prec))
    dropped_cited += len(drop & ref)
    dropped_q += bool(drop & ref)
print(f"artefact: stored nonllm scores given again: {same_n} of 200; stored id scores given again: {same_id} of 200")
print("  context_recall_nonllm, from as run:")
compare("split into records", [(a[0], b[0]) for a, b in zip(res["run"], res["split"])])
compare("split, baselines' form", [(a[0], b[0]) for a, b in zip(res["run"], res["form"])])
print("  context_precision_nonllm, from as run:")
compare("split into records", [(a[1], b[1]) for a, b in zip(res["run"], res["split"])])
compare("split, baselines' form", [(a[1], b[1]) for a, b in zip(res["run"], res["form"])])
print(f"  id scores, documents handed over only as slices holding less than their whole text not counted: "
      f"{dropped_cited} cited records in {dropped_q} questions")
compare("context_recall_id", [(a[0], b[0]) for a, b in zip(idp["stored"], idp["noslice"])])
compare("context_precision_id", [(a[1], b[1]) for a, b in zip(idp["stored"], idp["noslice"])])
json.dump({"nonllm": res, "id_stored": idp["stored"]},
          open(Path(__file__).with_name("granularity_checks.json"), "w"), default=list)
