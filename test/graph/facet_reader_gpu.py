"""Score facet answer/pole pairs on a GPU box. Copied to the desktop and run there:

    scp test/graph/facet_reader_gpu.py pairs.jsonl djuret@192.168.50.253:/a/exjobbet/
    A:\\exjobbet\\repo\\.venv\\Scripts\\python.exe facet_reader_gpu.py --pairs pairs.jsonl --out scores.jsonl

No repo import: torch and transformers only. Reads pairs.jsonl (one JSON object a line with
id, premise, hypothesis and the identity fields), writes scores.jsonl with entailment /
neutral / contradiction and the identity fields passed back, so the merge on the laptop
needs nothing else. fp32; the label order is read off the checkpoint's own config.
Resumable: ids already in the out file are not scored again.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
PASSTHROUGH = ("id", "chunk_id", "tag", "facet", "answer_sha")


def label_index(config):
    mapping = getattr(config, "label2id", None) or {}
    out = {}
    for name, idx in mapping.items():
        key = str(name).strip().lower()
        for want in ("entailment", "neutral", "contradiction"):
            if key == want or key.startswith(want[:6]):
                out[want] = int(idx)
    missing = [w for w in ("entailment", "neutral", "contradiction") if w not in out]
    if missing:
        raise SystemExit(f"[gpu] the checkpoint's label2id {mapping} does not name {missing}")
    return out


def read_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--revision", default=REVISION)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--device", default=None, help="cuda | cpu; default cuda when there is one")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    t0 = time.time()
    pairs = read_jsonl(Path(args.pairs))
    out_path = Path(args.out)
    already = set()
    if out_path.is_file():
        already = {r.get("id") for r in read_jsonl(out_path)}
    todo = [p for p in pairs if p.get("id") not in already]
    print(f"[gpu] {len(pairs)} pairs, {len(already)} already scored, {len(todo)} to read",
          flush=True)
    if not todo:
        return
    todo.sort(key=lambda d: len(d.get("premise", "")) + len(d.get("hypothesis", "")))

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    name = torch.cuda.get_device_name(0) if device == "cuda" else "cpu"
    print(f"[gpu] loading {args.model}@{args.revision[:8]} on {device} ({name}), fp32 ...",
          flush=True)
    tok = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, revision=args.revision, dtype=torch.float32).to(device).eval()
    cols = label_index(model.config)
    print(f"[gpu] labels {cols}; batch {args.batch}, max_len {args.max_len}  "
          f"({time.time() - t0:.0f}s)", flush=True)

    n, last, t1 = 0, 0.0, time.time()
    with out_path.open("a", encoding="utf-8") as fh, torch.inference_mode():
        for i in range(0, len(todo), args.batch):
            chunk = todo[i:i + args.batch]
            enc = tok([p["premise"] for p in chunk], [p["hypothesis"] for p in chunk],
                      return_tensors="pt", truncation=True, padding=True,
                      max_length=args.max_len)
            enc = {k: v.to(device) for k, v in enc.items()}
            probs = torch.softmax(model(**enc).logits.float(), dim=-1).cpu().numpy()
            for p, row in zip(chunk, probs):
                rec = {k: p[k] for k in PASSTHROUGH if k in p}
                rec["entailment"] = float(row[cols["entailment"]])
                rec["neutral"] = float(row[cols["neutral"]])
                rec["contradiction"] = float(row[cols["contradiction"]])
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
            fh.flush()
            os.fsync(fh.fileno())
            now = time.time()
            if now - last > 1.0 or i + args.batch >= len(todo):
                last = now
                print(f"[gpu] {n}/{len(todo)} pairs  {n / max(now - t1, 1e-9):.1f}/s  "
                      f"{now - t1:.0f}s", flush=True)
    wall = time.time() - t1
    print(f"[gpu] wrote {n} scores -> {out_path}  {n / max(wall, 1e-9):.1f} pairs/s  {wall:.1f}s",
          flush=True)


if __name__ == "__main__":
    main()
