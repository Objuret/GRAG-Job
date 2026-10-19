"""For his 2026-10-12 goal "solve this": the product's own conversations and own pull requests as
texts, one a row, to be embedded by the repo's own embedder on the desktop (no model call of
the lane; the corpus only, no question, no gold). A side measurement of what the order would be
if the unit were the conversation and not the batch.

  a conversation   the messages of one channel between its long gaps (`first_gold_rounds/ties.py`),
                   the records that are not the product's own work left out; its text is the
                   messages' own text, one a line, in the order written
  an own pull request   its record in the benchmark's own form (`harness.record_text`)

    .venv/Scripts/python.exe output/research/2026-10-11-missed-and-floated/own_units_for_embedding.py <out.jsonl>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test"), str(HERE / "first_gold_rounds")]
sys.stdout.reconfigure(encoding="utf-8")

import ties as TI  # noqa: E402
from harness.record_text import record_text  # noqa: E402


def units(product):
    P = TI.product(product)
    talks = defaultdict(list)
    for rid, t in P["talk_of"].items():
        if not TI.apart(rid, P):
            talks[t].append(rid)
    for (channel, run), rids in sorted(talks.items()):
        rids.sort(key=lambda r: P["raw"][r][1]["Message"]["User"]["timestamp"])
        yield {"id": f"talk|{product}|{channel}|{run}", "records": rids,
               "text": "\n".join(P["raw"][r][1]["Message"]["User"]["text"] for r in rids)}
    for rid, own in sorted(P["pr_own"].items()):
        if own:
            yield {"id": f"pr|{product}|{rid}", "records": [rid], "text": record_text("prs", P["raw"][rid][1])}


if __name__ == "__main__":
    out = Path(sys.argv[1])
    rows = [row for path in sorted(TI.RAW.glob("*.json")) for row in units(path.stem)]
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    chars = [len(row["text"]) for row in rows]
    kinds = defaultdict(int)
    for row in rows:
        kinds[row["id"].split("|")[0]] += 1
    print(f"{len(rows)} rows ({dict(kinds)}); characters a row: middle {sorted(chars)[len(chars) // 2]}, longest {max(chars)}; "
          f"all together {sum(chars):,}")
