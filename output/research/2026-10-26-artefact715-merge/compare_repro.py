"""Read-only: the desktop half's rows against the same questions' retrieval made again on the laptop
(retrieval only, the first calls read from the desktop's store). Counts only, no question text."""
import json, sys, collections

desk, lap = sys.argv[1], sys.argv[2]


def rows(path):
    return {r["id"]: r for r in (json.loads(x) for x in open(path, encoding="utf-8") if x.strip())}


a, b = rows(desk + "/arm_outputs.jsonl"), rows(lap + "/arm_outputs.jsonl")
both = sorted(set(a) & set(b))
print(f"desktop rows {len(a)}, laptop rows {len(b)}, in both {len(both)}")


def device(r):
    devs = sorted({c.get("device") for c in r.get("calls") or [] if c.get("kind") == "embed"})
    return devs[0] if len(devs) == 1 else ("none" if not devs else "+".join(devs))


def groups(r):
    e = r["meta"]["interpreter"]["embeddings"]
    return {k: (v.get("embedding") if isinstance(v, dict) else None) for k, v in e.items()}


same = collections.Counter()
by_dev = collections.Counter()
diff_rows = []
for i in both:
    x, y = a[i], b[i]
    first = x["meta"]["interpreter"]["stages"] == y["meta"]["interpreter"]["stages"] or \
        [s.get("key") for s in x["meta"]["interpreter"]["stages"]] == [s.get("key") for s in y["meta"]["interpreter"]["stages"]]
    ids_same = x["context_ids"] == y["context_ids"]
    texts_same = x["contexts"] == y["contexts"]
    gx, gy = groups(x), groups(y)
    vec_same = gx == gy
    d = device(x)
    same["first call keys the same"] += first
    same["context_ids the same"] += ids_same
    same["contexts the same"] += texts_same
    same["query vectors the same (sha256)"] += vec_same
    by_dev[(d, ids_same, vec_same)] += 1
    if not ids_same:
        fx = {str(c) for t in x["context_ids"] for c in (t if isinstance(t, list) else [t])}
        fy = {str(c) for t in y["context_ids"] for c in (t if isinstance(t, list) else [t])}
        j = len(fx & fy) / max(1, len(fx | fy))
        diff_rows.append((round(j, 3), d, vec_same, len(fx), len(fy)))
for k, v in same.items():
    print(f"  {k}: {v} of {len(both)}")
print("  by the desktop row's embed device (device, ids same, vectors same): count")
for k, v in sorted(by_dev.items(), key=lambda kv: str(kv[0])):
    print(f"    {k}: {v}")
if diff_rows:
    diff_rows.sort()
    print("  rows whose ids differ: record-id overlap (Jaccard), desktop device, vectors same, ids desktop, ids laptop")
    for t in diff_rows[:25]:
        print("   ", t)
