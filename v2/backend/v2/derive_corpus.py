"""One-time prep: derive the corpus view a dataset's pipeline run scans.

The published HERB layout embeds RAG-unsafe surfaces inside the same
products/*.json as the corpus; ingesting them is exactly the contamination
that polluted the v1 `herb` DB. Two categories, both stripped:

  - the eval oracle: answerable_questions / unanswerable_questions
    (815 + 699 = 1,514 questions; arXiv:2506.23139).
  - the membership links: team / customers. Per the dataset card's RAG
    Evaluation Note these exist "for oracle/long-context evaluation
    settings only" — 390/815 answerable questions are people-/customer-
    search, and membership must be inferred from the artifacts or from
    metadata/* (which therefore STAYS in the corpus), never read off the
    product-level lists.

The quarantine is structural, not declarative:

    corpus/<dataset>/   what the pipeline scans — RAG-unsafe keys deleted.
                        The probe can never sense them; contamination is
                        impossible by construction. This is the canonical
                        raw the graph references.

Nothing stripped is copied anywhere (references-not-copies applies to eval
too): the eval harness reads the oracle in place from the working raw
(data_root/raw/<dataset>/), which stays byte-untouched. Files without
stripped keys (metadata/) are copied byte-verbatim so their hashes match;
stripped files are re-serialized deterministically (key order kept,
indent=2). Non-JSON files (README, .gitattributes, caches) are not corpus
and are not copied. Rerunnable; wipes a stale corpus view first.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ORACLE_KEYS = ("answerable_questions", "unanswerable_questions")
RAG_UNSAFE_KEYS = ("team", "customers")
STRIP_KEYS = ORACLE_KEYS + RAG_UNSAFE_KEYS


@dataclass
class DeriveReport:
    n_stripped: int = 0
    n_copied: int = 0
    n_skipped: int = 0
    stripped_counts: dict[str, int] = field(default_factory=dict)


def _dump(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def derive_corpus(
    dataset_dir: Path, strip_keys: tuple[str, ...] = STRIP_KEYS
) -> DeriveReport:
    dataset_dir = dataset_dir.resolve()
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"no such dataset dir: {dataset_dir}")
    if dataset_dir.parent.name != "raw":
        raise ValueError(
            f"dataset must live under a raw/ working root, got: {dataset_dir} — "
            "the corpus view is derived as a sibling corpus/ of raw/"
        )
    corpus_root = dataset_dir.parent.parent / "corpus" / dataset_dir.name
    if corpus_root.exists():
        print(f"wiping stale corpus view: {corpus_root}")
        shutil.rmtree(corpus_root)

    report = DeriveReport(stripped_counts={k: 0 for k in strip_keys})
    for path in sorted(dataset_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dataset_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue  # .cache and friends — never corpus, never counted
        if path.suffix != ".json":
            report.n_skipped += 1
            continue
        raw_bytes = path.read_bytes()
        root = json.loads(raw_bytes)
        present = [k for k in strip_keys if isinstance(root, dict) and k in root]
        corpus_out = corpus_root / rel
        corpus_out.parent.mkdir(parents=True, exist_ok=True)
        if not present:
            corpus_out.write_bytes(raw_bytes)  # verbatim: hash matches the raw
            report.n_copied += 1
            continue
        if set(present) != set(strip_keys):
            raise ValueError(
                f"{path}: has {present} but not all of {list(strip_keys)} — "
                "unexpected shape, refusing to guess"
            )
        for k in strip_keys:
            report.stripped_counts[k] += len(root.pop(k))
        if any(k in root for k in strip_keys):
            raise AssertionError(f"{path}: stripped key survived the strip")
        corpus_out.write_text(_dump(root), encoding="utf-8")
        report.n_stripped += 1

    if report.n_stripped == 0:
        raise RuntimeError(
            f"{dataset_dir}: no file carried the strip keys {list(strip_keys)} — "
            "nothing to strip; is this the right dataset?"
        )
    return report
