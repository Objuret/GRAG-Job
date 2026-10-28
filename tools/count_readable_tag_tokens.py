"""The tokens of the 63 tags whose name holds an underscore, as the graph's tag pass embedded them (the
raw name) and as the graph holds them (the readable name, graph.db._readable): behind "query: ", counted
the way the harness counts embedding tokens (the embedder's own tokenizer, special tokens added, no
truncation). The embedder is loaded on the CPU for its tokenizer only; nothing is embedded.

    python tools/count_readable_tag_tokens.py [--write]

With --write it writes test/graph/build_cost_readable_names_tokens.json, which the export reads: the
raw names' vectors were replaced in the graph by the readable names' (MANIFEST.json readable_names), so
the raw names' share of the tag pass is not part of what built the index.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
TAGS = REPO / "output/embed_local/20261008_rev113abe4acafa_float32/tags_query.npz"
OUT = REPO / "test/graph/build_cost_readable_names_tokens.json"
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
os.environ.setdefault("HF_HUB_OFFLINE", "1")


def main():
    from graph.db import _readable
    from harness import embed
    ids = [str(i) for i in np.load(TAGS, allow_pickle=True)["ids"]]
    raw = [n for n in ids if _readable(n) != n]
    model = embed._embedder()
    prefix = embed.EMBED_PREFIX["query"]

    def count(texts):
        return sum(len(i) for i in model.tokenizer([prefix + t for t in texts], add_special_tokens=True,
                                                   truncation=False)["input_ids"])

    result = {"what": "tokens of the tags whose name holds an underscore, in the tag pass (raw name) and in the graph "
                      "(readable name)", "tags": len(ids), "tags_tokens": count(ids), "raw_names": len(raw),
              "raw_names_tokens": count(raw), "readable_names_tokens": count([_readable(t) for t in raw]),
              "script": "tools/count_readable_tag_tokens.py"}
    print(json.dumps(result, indent=1))
    if "--write" in sys.argv:
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"written: {OUT}")


if __name__ == "__main__":
    main()
