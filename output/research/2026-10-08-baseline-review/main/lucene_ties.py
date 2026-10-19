"""The lucene arm's full ranking for the MADE-UP question, written out with its scores.

Run it under each Python that has bm25s; the second script compares the two files.
No test question, no gold, no model. In memory, nothing written to a run folder.

    <python> output/research/2026-10-08-baseline-review/main/lucene_ties.py <out.json>
"""
import json
import sys
import time
from importlib.metadata import version
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "prod"))

from arms import lucene  # noqa: E402
from harness.char_budget import cut_at_budget  # noqa: E402

CORPUS = REPO / "data" / "corpus" / "Salesforce__HERB"
Q = json.loads((REPO / "output/research/2026-10-08-keep-everything-proof/madeup_question.jsonl")
               .read_text(encoding="utf-8").splitlines()[0])

t0 = time.perf_counter()
prepared = lucene.build_sparse_index(CORPUS)
build_s = time.perf_counter() - t0

times = []
for _ in range(7):
    t0 = time.perf_counter()
    units = lucene.retrieve_top_k_units((Q["id"], Q["question"]), prepared, len(prepared.ids))
    times.append(time.perf_counter() - t0)

ranked = [u for u in units if u["score"] > 0.0]
cut = cut_at_budget(((u["id"], u["text"]) for u in ranked), 72000)
out = {
    "python": sys.version.split()[0], "executable": sys.executable,
    "bm25s": version("bm25s"), "PyStemmer": version("PyStemmer"),
    "numpy": version("numpy"), "scipy": version("scipy"),
    "build_s": build_s, "search_s_single_thread": times,
    "n_units": len(prepared.ids), "n_ranked": len(ranked),
    "ids": [u["id"] for u in ranked], "scores": [u["score"] for u in ranked],
    "kept": cut.kept, "boundary": cut.boundary,
    "query_tokens": len(__import__("bm25s").tokenize(
        [Q["question"]], stopwords="en", stemmer=prepared.stemmer, show_progress=False).ids[0]),
}
Path(sys.argv[1]).write_text(json.dumps(out), encoding="utf-8")
print(f"bm25s {out['bm25s']} numpy {out['numpy']} scipy {out['scipy']} python {out['python']} | "
      f"build {build_s:.2f}s | search, one at a time: first {times[0]:.3f}s then "
      f"{', '.join(f'{t:.3f}' for t in times[1:])} | ranked {len(ranked)} of {len(prepared.ids)} | "
      f"whole units inside 72,000: {cut.kept} | query tokens {out['query_tokens']}")
