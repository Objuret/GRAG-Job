"""What the two artefact folders (D) keep per question: list lengths and counts only."""
import json
import statistics
import sys
from collections import Counter

from folders import ALL

sys.stdout.reconfigure(encoding="utf-8")


def rows(p):
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def q3(xs):
    xs = sorted(xs)
    return xs[0], statistics.median(xs), xs[-1]


for name in ("D.v4_100", "D.v4_10"):
    rs = rows(ALL[name] / "arm_outputs.jsonl")
    n = len(rs)
    print(f"{name}: rows {n}   top-level keys {sorted(rs[0])}")
    print(f"   sum(len(contexts)) == 72000: {sum(1 for r in rs if sum(len(c) for c in r['contexts']) == 72000)}/{n}   answers empty: {sum(1 for r in rs if not r['answer'])}/{n}")
    print(f"   len(contexts) min/median/max {q3([len(r['contexts']) for r in rs])}   len(context_ids) {q3([len(r['context_ids']) for r in rs])}   context_ids unique in row: {sum(1 for r in rs if len(set(r['context_ids'])) == len(r['context_ids']))}/{n}")
    rk = [r["meta"]["ranking"] for r in rs]
    for key in ("delivered_chunk_ids", "delivered_strength", "delivered_levels", "delivered_query_tags", "ordered_chunk_ids"):
        print(f"   meta.ranking.{key:<22} length min/median/max {q3([len(x[key]) for x in rk])}")
    print(f"   len(delivered_strength) == len(contexts): {sum(1 for r in rs if len(r['meta']['ranking']['delivered_strength']) == len(r['contexts']))}/{n}   len(delivered_chunk_ids) == len(contexts): {sum(1 for r in rs if len(r['meta']['ranking']['delivered_chunk_ids']) == len(r['contexts']))}/{n}")
    print(f"   meta.chunk_ids (one list per context) length == len(contexts): {sum(1 for r in rs if len(r['meta']['chunk_ids']) == len(r['contexts']))}/{n}   meta.returned min/median/max {q3([r['meta']['returned'] for r in rs])}")
    rt = [r["retrieval"] for r in rs]
    print(f"   retrieval.calls values {dict(sorted(Counter(x['calls'] for x in rt).items()))}   attempts {dict(sorted(Counter(x['attempts'] for x in rt).items()))}   tokens_in sum {sum(x['tokens_in'] for x in rt)}  tokens_out sum {sum(x['tokens_out'] for x in rt)}  cached sum {sum(x['cached_input_tokens'] for x in rt)}  time_s sum {sum(x['time_s'] for x in rt):.1f}")
    st = Counter()
    for r in rs:
        for s in r["meta"]["interpreter"]["stages"]:
            st[(s["stage"], s["cache_hit"], s.get("offline"), s["asks"])] += 1
    print(f"   meta.interpreter.stages (stage, cache_hit, offline, asks): {dict(st)}")
    if "calls" in rs[0]:
        print(f"   calls list lengths {dict(Counter(len(r['calls']) for r in rs))}   timing present {sum(1 for r in rs if 'timing' in r)}/{n}   timing.wall_s min/median/max {tuple(round(x, 2) for x in q3([r['timing']['wall_s'] for r in rs]))}   threads {len(set(r['timing']['thread'] for r in rs))}   leg values {dict(Counter(r['leg'] for r in rs))}")
        parts = [r["timing"]["wall_s"] - (r["search_time_s"] + r["retrieval"]["time_s"] + r["generator"]["time_s"]) for r in rs]
        print(f"   timing.wall_s - (search_time_s + retrieval.time_s + generator.time_s) min/median/max {tuple(round(x, 3) for x in q3(parts))}")
    ev = rows(ALL[name] / "eval_results.jsonl")
    print(f"   eval rows {len(ev)}   scores {len(set(r['metric'] for r in ev))}: {sorted(set(r['metric'] for r in ev))}   status {dict(Counter(r['status'] for r in ev))}   components non-empty {sum(1 for r in ev if r['components'])}")
