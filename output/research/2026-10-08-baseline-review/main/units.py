"""The same record as each baseline writes it: lucene's unit text against vector's.

Reads the corpus only (data/corpus/Salesforce__HERB/products/*.json). No question, no gold,
no model, no embedder. Prints counts and character sums, never a text.

    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/main/units.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "prod"))

from arms import lucene, vector  # noqa: E402  (vector imports the embed module, loads no model)

CORPUS = REPO / "data" / "corpus" / "Salesforce__HERB"

ldocs = lucene.ingest_corpus(CORPUS)
vdocs = vector._read_corpus(CORPUS)

ltext = {d["id"]: f'{d["title"]}\n{d["contents"]}'.strip() for d in ldocs}
lkind = {d["id"]: d["kind"] for d in ldocs}
vtext = {d["id"]: d["text"] for d in vdocs}

print("units: lucene", len(ltext), "vector", len(vtext),
      "| same ids in the same order:", [d["id"] for d in ldocs] == [d["id"] for d in vdocs])
print("characters over all units: lucene", sum(map(len, ltext.values())),
      "vector", sum(map(len, vtext.values())))

by = defaultdict(lambda: {"n": 0, "same": 0, "lchars": 0, "vchars": 0, "lens_l": [], "lens_v": [],
                          "empty_l": 0, "empty_v": 0})
for i, lt in ltext.items():
    vt = vtext[i]
    b = by[lkind[i]]
    b["n"] += 1
    b["same"] += lt == vt
    b["lchars"] += len(lt)
    b["vchars"] += len(vt)
    b["lens_l"].append(len(lt))
    b["lens_v"].append(len(vt))
    b["empty_l"] += not lt.strip()
    b["empty_v"] += not vt.strip()

print("\nper kind of record: n | text identical in both arms | chars lucene | chars vector | "
      "median chars lucene / vector | longest lucene / vector | empty lucene / vector")
for kind in lucene.ARTIFACT_TYPES:
    b = by[kind]
    if not b["n"]:
        continue
    print(f"  {kind:<20} {b['n']:>6} | {b['same']:>6} | {b['lchars']:>9} | {b['vchars']:>9} | "
          f"{median(b['lens_l']):>7.0f} / {median(b['lens_v']):<7.0f} | "
          f"{max(b['lens_l']):>6} / {max(b['lens_v']):<6} | {b['empty_l']} / {b['empty_v']}")

# urls: lucene's text is title + newline + contents, where title = description (or link) and
# contents = description + space + link; count the records whose description stands twice
raw_urls = dup = 0
for pf in sorted((CORPUS / "products").glob("*.json")):
    data = json.loads(pf.read_text(encoding="utf-8"))
    for rec in data.get("urls", []) or []:
        raw_urls += 1
        desc = rec.get("description", "")
        if desc and ltext.get(rec.get("id"), "").count(desc) >= 2:
            dup += 1
print(f"\nurl records: {raw_urls}; of them with the description standing twice in lucene's text: {dup}")

# identical texts inside one arm: equal scores by construction
for name, texts in (("lucene", ltext), ("vector", vtext)):
    c = Counter(texts.values())
    groups = [n for n in c.values() if n > 1]
    print(f"{name}: distinct texts {len(c)} of {len(texts)}; units sharing their text with "
          f"another unit: {sum(groups)} in {len(groups)} groups (largest group {max(groups) if groups else 0})")

# size of a unit, both arms, all kinds
for name, texts in (("lucene", ltext), ("vector", vtext)):
    lens = sorted(map(len, texts.values()))
    n = len(lens)
    print(f"{name} unit length in characters: min {lens[0]}  median {lens[n // 2]}  "
          f"mean {sum(lens) / n:.0f}  90% {lens[int(n * 0.9)]}  99% {lens[int(n * 0.99)]}  max {lens[-1]}"
          f" | units longer than 72,000: {sum(1 for x in lens if x > 72000)}"
          f" | units longer than 7,200: {sum(1 for x in lens if x > 7200)}")
