
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
            continue
        if path.suffix != ".json":
            report.n_skipped += 1
            continue
        raw_bytes = path.read_bytes()
        root = json.loads(raw_bytes)
        present = [k for k in strip_keys if isinstance(root, dict) and k in root]
        corpus_out = corpus_root / rel
        corpus_out.parent.mkdir(parents=True, exist_ok=True)
        if not present:
            corpus_out.write_bytes(raw_bytes)
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
