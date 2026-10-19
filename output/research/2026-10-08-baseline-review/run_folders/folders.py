"""The run folders this review reads, by group. Read-only."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
KC = REPO / "output" / "k=chars"
PROOF = REPO / "output" / "research" / "2026-10-08-keep-everything-proof"

GROUPS = {
    "A": {
        "A.luc": KC / "lucene__gold100__cb72000__20261007T211014Z",
        "A.vec": KC / "vector__gold100__cb72000__20261007T211515Z",
    },
    "B": {
        "B.luc": KC / "lucene__gold100__cb72000__20260814T134547Z",
        "B.vec": KC / "vector__gold100__cb72000__20260814T145615Z",
    },
    "C": {
        "C.luc": PROOF / "lucene",
        "C.lucA": PROOF / "lucene__answer",
        "C.vec": PROOF / "vector",
        "C.vecAE": PROOF / "vector__answer__eval",
    },
    "D": {
        "D.v4_100": KC / "artefact_v4__gold100__cb72000__20261007T041909Z",
        "D.v4_10": KC / "artefact_v4__10smoke__cb72000__20261008T021732Z",
    },
}

ALL = {name: path for g in GROUPS.values() for name, path in g.items()}
GROUP_OF = {name: g for g, d in GROUPS.items() for name in d}

# eval_calls.jsonl holds the judge prompts (gold answers). It is opened in C only.
MAY_OPEN_EVAL_CALLS = {"C.luc", "C.lucA", "C.vec", "C.vecAE"}
