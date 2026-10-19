"""For his 2026-10-12 goal "solve this": what the two baselines' delivered records on the hundred are
made of by the same ties (`first_gold_rounds/ties.py`). Read from the run folders' delivered
record ids; the question's product is read from the question's id. No gold, no model call.

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/the_ties_in_the_baselines_delivery.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")
import ties as TI  # noqa: E402

RUNS = ("lucene__gold100__cb72000__20260814T134547Z", "vector__gold100__cb72000__20260814T145615Z",
        "artefact_v4__gold100__cb72000__20261012T212549Z_combo")
holder = {}
for path in sorted(TI.RAW.glob("*.json")):
    for rid in TI.product(path.stem)["raw"]:
        holder.setdefault(rid, path.stem)
for run in RUNS:
    rows = [json.loads(line) for line in (REPO / "output" / "k=chars" / run / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    count, chars = Counter(), Counter()
    for row in rows:
        product = row["id"].split("::")[0]
        P = TI.product(product)
        for rid in dict.fromkeys(str(x) for x in row["context_ids"]):
            where = holder.get(rid)
            if where is None:
                key = "a record of no product file (the metadata files)"
            elif where != product:
                key = "a record of another product"
            else:
                key = "the product's own work" if not TI.apart(rid, P) else f"not its own work: {TI.tie(rid, P)}"
            count[key] += 1
            chars[key] += TI.product(where)["size"][rid] if where else 0
    total, total_chars = sum(count.values()), sum(chars.values())
    print(f"\n== {run}: {len(rows)} questions, {total / len(rows):.1f} records delivered a question ==")
    print("   records, a question | share of the delivered records | share of their characters")
    for key, n in count.most_common():
        print(f"  {n / len(rows):6.1f} | {n / total:5.1%} | {chars[key] / max(total_chars, 1):5.1%}  {key}")
