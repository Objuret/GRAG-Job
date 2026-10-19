"""Integrity of a baseline run folder on the hundred, recomputed from its files.

    python integrity.py A.luc A.vec [B.luc B.vec]

Prints counts, lengths, hashes and numbers only. No question, answer, context or gold text.
The character rule checked is the harness's own (prod/harness/char_budget.py, read 2026-10-08):
whole units in rank order while they fit, then the first unit that does not fit cut so the
contexts total exactly the budget; `kept` counts the whole units, context_ids names only those.
"""
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from folders import ALL, REPO

sys.stdout.reconfigure(encoding="utf-8")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree_digest(root):
    """Same recipe as prod/harness/provenance.py tree_digest (read 2026-10-08)."""
    root = Path(root)
    files = sorted(p for p in root.glob("**/*.json") if p.is_file())
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(root).as_posix().encode("utf-8"))
        h.update(bytes([0]))
        h.update(sha(p).encode("utf-8"))
        h.update(bytes([10]))
    return h.hexdigest(), len(files)


def rows(p):
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def stamp(s):
    return datetime.fromisoformat(s)


def folder_stamp(name):
    raw = name.rsplit("__", 1)[-1]
    return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def mtime(p):
    return datetime.fromtimestamp(Path(p).stat().st_mtime, timezone.utc)


def q3(xs):
    xs = sorted(xs)
    return xs[0], statistics.median(xs), xs[-1]


def fmt(x, nd=3):
    return "None" if x is None else f"{x:.{nd}f}"


GOLD_IDS = REPO / "data" / "gold100.jsonl"
QUESTIONS = REPO / "data" / "questions.jsonl"
CORPUS = REPO / "data" / "corpus" / "Salesforce__HERB"
ORDER = ["context_precision_id", "context_recall_id", "context_precision_nonllm",
         "context_recall_nonllm", "semantic_similarity", "string_similarity", "bleu", "rouge",
         "chrf", "exact_match", "string_presence", "faithfulness", "answer_correctness",
         "context_recall_llm"]
JUDGED = ("faithfulness", "answer_correctness", "context_recall_llm")

_cache = {}


def question_file():
    if "q" not in _cache:
        q = {}
        with open(QUESTIONS, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    d = json.loads(line)
                    q[d["id"]] = d
        _cache["q"] = q
    return _cache["q"]


def corpus_digest():
    if "c" not in _cache:
        _cache["c"] = tree_digest(CORPUS)
    return _cache["c"]


def check_rows(name, folder, man, out):
    qfile = question_file()
    inp = man["inputs"]
    print("[inputs]")
    print(f"  manifest questions_file         : {man['questions_file']}   exists now: {Path(man['questions_file']).is_file()}")
    named = "ids_file" in man or any("ids_file" in (leg or {}) for leg in (man.get("legs") or []))
    print(f"  manifest names an id file path  : {named}")
    print(f"  ids_sha256 == sha256(data/gold100.jsonl)        : {inp['ids_sha256'] == sha(GOLD_IDS)}")
    print(f"  questions_sha256 == sha256(data/questions.jsonl): {inp['questions_sha256'] == sha(QUESTIONS)}")
    cd, cn = corpus_digest()
    print(f"  corpus sha256 == tree digest of data/corpus/Salesforce__HERB now: {inp['corpus']['sha256'] == cd}  (n_files manifest {inp['corpus']['n_files']}, now {cn})")

    ids = [r["id"] for r in out]
    gold = [json.loads(x)["id"] for x in GOLD_IDS.read_text(encoding="utf-8").splitlines() if x.strip()]
    n = len(out)
    print("[rows]")
    print(f"  rows                            : {n}   manifest n_questions {man['n_questions']} n_ran {man['n_ran']} n_failed {man['n_failed']} n_exhausted {man['n_exhausted']}")
    print(f"  ids unique                      : {len(set(ids)) == len(ids)}  ({len(set(ids))} distinct)")
    print(f"  ids == id file, same order      : {ids == gold}   same set: {set(ids) == set(gold)}   id file lines {len(gold)}")
    same_q = sum(1 for r in out if r["id"] in qfile and r["question"] == qfile[r["id"]]["question"])
    print(f"  row question == question file's : {same_q}/{n}")
    print(f"  failures.jsonl bytes            : {(folder / 'failures.jsonl').stat().st_size}")

    budget = man["char_budget"]
    tot_ok = meta_ok = kept_ok = nctx_ok = piece_ok = uniq_ok = bnd_out = full_gt = 0
    exhausted = no_boundary = over_k = piece_cited = 0
    kept, nctx, piece, piece_full = [], [], [], []
    for r in out:
        cb = r["meta"]["char_budget"]
        total = sum(len(c) for c in r["contexts"])
        tot_ok += total == budget
        meta_ok += cb["chars"] == total and cb["budget"] == budget
        kept_ok += cb["kept"] == len(r["context_ids"])
        b = cb["boundary"]
        nctx_ok += len(r["contexts"]) == cb["kept"] + (1 if b else 0)
        exhausted += bool(cb["exhausted"])
        if b:
            piece_ok += b["chars_kept"] == len(r["contexts"][-1])
            full_gt += b["chars_full"] > b["chars_kept"]
            bnd_out += b["id"] not in r["context_ids"]
            piece.append(b["chars_kept"])
            piece_full.append(b["chars_full"])
            piece_cited += b["id"] in set(qfile[r["id"]].get("citations") or [])
        else:
            no_boundary += 1
        uniq_ok += len(set(r["context_ids"])) == len(r["context_ids"])
        kept.append(cb["kept"])
        nctx.append(len(r["contexts"]))
        over_k += cb["kept"] > man["top_k"]
    nb = n - no_boundary
    print(f"[the cut]  manifest char_budget {budget}, top_k {man['top_k']}")
    print(f"  sum(len(contexts)) == {budget}                        : {tot_ok}/{n}")
    print(f"  meta.char_budget.chars == that sum and budget == {budget}: {meta_ok}/{n}")
    print(f"  meta.char_budget.kept == len(context_ids)              : {kept_ok}/{n}")
    print(f"  len(contexts) == kept + (1 if a cut piece)             : {nctx_ok}/{n}")
    print(f"  rows with a cut piece (boundary not null)              : {nb}/{n}   exhausted rows: {exhausted}")
    print(f"  cut piece: chars_kept == len(last context)             : {piece_ok}/{nb}")
    print(f"  cut piece: chars_full > chars_kept                     : {full_gt}/{nb}")
    print(f"  cut piece id absent from context_ids                   : {bnd_out}/{nb}")
    print(f"  context_ids unique within the row                      : {uniq_ok}/{n}")
    print(f"  whole units per row (kept)        min/median/max       : {q3(kept)}")
    print(f"  contexts per row (with the piece) min/median/max       : {q3(nctx)}")
    if piece:
        print(f"  cut piece chars kept              min/median/max       : {q3(piece)}")
        print(f"  cut piece full length             min/median/max       : {q3(piece_full)}")
    print(f"  rows with more whole units than the manifest top_k     : {over_k}/{n}")
    print(f"  rows whose cut piece id is one of the question citation ids: {piece_cited}/{nb}")
    return ids, qfile


def check_spend(name, folder, man, out):
    n = len(out)
    g = [r["generator"] for r in out]
    rt = [r["retrieval"] for r in out]
    print("[tokens and tries]")
    print(f"  generator.tokens_in > 0         : {sum(1 for x in g if x['tokens_in'] > 0)}/{n}     tokens_out > 0: {sum(1 for x in g if x['tokens_out'] > 0)}/{n}")
    print(f"  generator.calls values          : {dict(Counter(x['calls'] for x in g))}")
    print(f"  generator.attempts values       : {dict(sorted(Counter(x['attempts'] for x in g).items()))}   rows with attempts > 1: {sum(1 for x in g if x['attempts'] > 1)}")
    print(f"  generator.retry_s > 0 rows      : {sum(1 for x in g if x['retry_s'] > 0)}   wait_s > 0 rows: {sum(1 for x in g if x['wait_s'] > 0)}")
    print(f"  generator.cached_input_tokens>0 : {sum(1 for x in g if x['cached_input_tokens'] > 0)} rows, sum {sum(x['cached_input_tokens'] for x in g)}")
    print(f"  generator tokens_in  sum, (min, median, max): {sum(x['tokens_in'] for x in g)}, {q3([x['tokens_in'] for x in g])}")
    print(f"  generator tokens_out sum, (min, median, max): {sum(x['tokens_out'] for x in g)}, {q3([x['tokens_out'] for x in g])}")
    print(f"  retrieval.calls values          : {dict(Counter(x['calls'] for x in rt))}   retrieval tokens_in sum {sum(x['tokens_in'] for x in rt)}  time_s sum {fmt(sum(x['time_s'] for x in rt))}")
    print(f"  empty answers                   : {sum(1 for r in out if not r['answer'].strip())}/{n}")

    start = folder_stamp(folder.name)
    end = stamp(man["timestamp"])
    at = [stamp(r["answered_at"]) for r in out]
    wall = (end - start).total_seconds()
    gen_s = sum(x["time_s"] for x in g)
    req_s = sum(x["request_s"] for x in g)
    srch = sum(r["search_time_s"] for r in out)
    print("[stamps and seconds]")
    print(f"  folder stamp (start)            : {start.isoformat()}")
    print(f"  first / last answered_at        : {min(at).isoformat()} / {max(at).isoformat()}")
    print(f"  run_manifest timestamp (end)    : {end.isoformat()}")
    print(f"  arm_outputs.jsonl last written  : {mtime(folder / 'arm_outputs.jsonl').isoformat(timespec='seconds')}   run_manifest.json: {mtime(folder / 'run_manifest.json').isoformat(timespec='seconds')}")
    print(f"  answered_at inside [start, end] : {sum(1 for t in at if start <= t <= end)}/{n}")
    print(f"  answered_at non-decreasing in file order: {sum(1 for a, b in zip(at, at[1:]) if b >= a)}/{n - 1} steps")
    print(f"  wall window end - start         : {fmt(wall, 1)} s   first-to-last answered_at: {fmt((max(at) - min(at)).total_seconds(), 1)} s   start to first answer: {fmt((min(at) - start).total_seconds(), 1)} s")
    print(f"  sum generator.time_s            : {fmt(gen_s, 1)} s   sum generator.request_s: {fmt(req_s, 1)} s   sum search_time_s: {fmt(srch, 2)} s")
    print(f"  (sum generator.time_s + sum search_time_s) / wall window: {fmt((gen_s + srch) / wall, 2)}")
    print(f"  generator.time_s min/median/max : {tuple(round(x, 2) for x in q3([x['time_s'] for x in g]))}")
    print(f"  search_time_s    min/median/max : {tuple(round(x, 4) for x in q3([r['search_time_s'] for r in out]))}")
    bs = man["build_stats"]
    print(f"  manifest build_stats            : build_time_s {bs['build_time_s']}  calls {bs['model']['calls']}  tokens_in {bs['model']['tokens_in']}  time_s {bs['model']['time_s']}  models {bs['models']}")
    has = {k: (k in man) for k in ("workers", "legs", "lane", "index", "code_state", "generator", "env")}
    print(f"  manifest has key                : {has}")
    print(f"  code_version                    : {man['code_version']}   diff files in folder: {[p.name for p in folder.iterdir() if p.suffix == '.diff']}")


def check_eval(name, folder, ids, qfile):
    ev = rows(folder / "eval_results.jsonl")
    em = json.loads((folder / "eval_manifest.json").read_text(encoding="utf-8"))
    print("[eval rows]")
    print(f"  rows                            : {len(ev)}")
    pairs = Counter((r["question_id"], r["metric"]) for r in ev)
    per_q = Counter(r["question_id"] for r in ev)
    print(f"  distinct (question, score) pairs: {len(pairs)}   duplicated pairs: {sum(1 for v in pairs.values() if v > 1)}")
    print(f"  questions                       : {len(per_q)}   rows per question: {dict(Counter(per_q.values()))}   same id set as arm_outputs: {set(per_q) == set(ids)}")
    print(f"  arm field values                : {dict(Counter(r['arm'] for r in ev))}")
    print(f"  status values                   : {dict(Counter(r['status'] for r in ev))}")
    print(f"  components non-empty rows       : {sum(1 for r in ev if r['components'])}   human_label non-null: {sum(1 for r in ev if r['human_label'] is not None)}")
    print(f"  type field == question file type: {sum(1 for r in ev if qfile[r['question_id']]['type'] == r['type'])}/{len(ev)}")
    print(f"  question types (count of the {len(ids)}) : {dict(sorted(Counter(qfile[i]['type'] for i in ids).items()))}")
    by = defaultdict(list)
    for r in ev:
        by[r["metric"]].append(r)
    print(f"  {'score':<26}{'rows':>5}{'ok':>5}{'nan':>5}{'err':>5}{'None':>5}{'NaNval':>7}{'<0|>1':>6}{'mean of ok rows':>18}{'min':>9}{'max':>9}")
    for m in ORDER + sorted(set(by) - set(ORDER)):
        rs = by.get(m, [])
        st = Counter(r["status"] for r in rs)
        none = sum(1 for r in rs if r["value"] is None)
        nanv = sum(1 for r in rs if isinstance(r["value"], float) and r["value"] != r["value"])
        okv = [r["value"] for r in rs if r["status"] == "ok"]
        outside = sum(1 for v in okv if v < 0 or v > 1)
        mean = statistics.fmean(okv) if okv else float("nan")
        lo = min(okv) if okv else float("nan")
        hi = max(okv) if okv else float("nan")
        print(f"  {m:<26}{len(rs):>5}{st.get('ok', 0):>5}{st.get('nan', 0):>5}{st.get('error', 0):>5}{none:>5}{nanv:>7}{outside:>6}{mean:>18.6f}{lo:>9.4f}{hi:>9.4f}")

    print("[eval manifest]")
    ju = em["judge_usage"]
    legs = em.get("judge_legs") or []
    print(f"  judge_model {em['judge_model']}  backend {em['judge_backend']}  effort {em['judge_effort']}  timestamp {em['timestamp']}")
    for f in ("eval_manifest.json", "eval_results.jsonl", "eval_failures.jsonl", "failures.jsonl"):
        print(f"  {f:<22} last written {mtime(folder / f).isoformat(timespec='seconds')}   {(folder / f).stat().st_size} B")
    print(f"  judge_usage                     : {ju}")
    print(f"  judge_elapsed_s                 : {em['judge_elapsed_s']}")
    for i, leg in enumerate(legs, 1):
        u = leg["usage"]
        extra = sorted(k for k in leg if k not in ("usage", "timestamp", "judge_model", "judge_backend", "elapsed_s"))
        print(f"  leg {i}: timestamp {leg['timestamp']}  judge_model {leg['judge_model']}  calls {u['calls']}  attempts {u['attempts']}  tokens_in {u['tokens_in']}  cached {u['cached_input_tokens']}  tokens_out {u['tokens_out']}  time_s {fmt(u['time_s'], 1)}  request_s {fmt(u['request_s'], 1)}  elapsed_s {fmt(leg['elapsed_s'], 1)}  other keys {extra}")
    for key in ("calls", "tokens_in", "cached_input_tokens", "tokens_out", "attempts"):
        s = sum(leg["usage"][key] for leg in legs)
        print(f"  sum of legs {key:<20}: {s}   == judge_usage: {s == ju[key]}")
    for key in ("time_s", "request_s"):
        s = sum(leg["usage"][key] for leg in legs)
        print(f"  sum of legs {key:<20}: {fmt(s, 3)}   judge_usage: {fmt(ju[key], 3)}   equal within 1e-6: {math.isclose(s, ju[key], abs_tol=1e-6)}")
    s = sum(leg["elapsed_s"] for leg in legs)
    print(f"  sum of legs elapsed_s           : {fmt(s, 3)}   judge_elapsed_s: {fmt(em['judge_elapsed_s'], 3)}   equal within 1e-6: {math.isclose(s, em['judge_elapsed_s'], abs_tol=1e-6)}")
    judged = sum(1 for r in ev if r["metric"] in JUDGED)
    print(f"  judged cells (3 judged scores)  : {judged}   judge calls / judged cell: {fmt(ju['calls'] / judged, 3)}   judge calls / question: {fmt(ju['calls'] / len(per_q), 2)}")
    print(f"  tokens_in / call                : {fmt(ju['tokens_in'] / ju['calls'], 1)}   tokens_out / call: {fmt(ju['tokens_out'] / ju['calls'], 1)}   cached / tokens_in: {fmt(ju['cached_input_tokens'] / ju['tokens_in'], 4)}")
    print(f"  request_s / elapsed_s           : {fmt(ju['request_s'] / em['judge_elapsed_s'], 2)}")
    kept = "components.usage" if any(r["components"] for r in ev) else "none"
    print(f"  per-cell stamps, tokens or call records in this folder: {kept}; eval_calls.jsonl present: {(folder / 'eval_calls.jsonl').exists()}")
    print()


def check(name):
    folder = ALL[name]
    man = json.loads((folder / "run_manifest.json").read_text(encoding="utf-8"))
    out = rows(folder / "arm_outputs.jsonl")
    print("=" * 100)
    print(f"{name}   {folder.name}")
    print("=" * 100)
    ids, qfile = check_rows(name, folder, man, out)
    check_spend(name, folder, man, out)
    check_eval(name, folder, ids, qfile)


if __name__ == "__main__":
    for name in sys.argv[1:] or ["A.luc", "A.vec"]:
        check(name)
