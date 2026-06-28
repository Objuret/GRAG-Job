"""Stage 5: tag — one stateless structured call per chunk emits contextual
phrase tags (design §9.5).

The model emits phrases only: no numbers, no description, no facets (facets are
measured later over the finished tag corpus). Tags bind to the chunk's id — each
chunk's tags are its per-chunk Tag nodes, so `Source → File → Chunk → Tag` holds
and a tag traces down through its chunk's references to the exact source.

Structured output via NIM `response_format: json_schema`, mirroring the shared
generator. One temp-0 call per chunk, instance discarded — reproducible.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import httpx
from tqdm import tqdm

import abort
import nim
from artefact.chunk import Chunk, _get, chunk_dataset, load_key
from contract import BuildStats, ModelUsage

TAGGER_MODEL = "z-ai/glm-5.1"

_TAGS_SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
    "required": ["tags"],
}

SYSTEM = (
    "You read one chunk of source material and emit contextual phrase tags. "
    "Each tag is a short phrase naming a salient, distinct thing the chunk is "
    "about — a theme a reader would say it covers, not every sub-point or "
    "passing mention. Prefer a handful of strong tags over an exhaustive list, "
    "and collapse closely-related points into one. Never emit an id, a date, a "
    "number, or a bare name as a tag."
)


def tagger_view(chunk: Chunk, data_root: Path) -> str:
    """The model's view of the chunk: its content references resolved to text,
    in order. Read on demand from raw, never stored (references-not-copies)."""
    doc = json.loads((data_root / chunk.relpath).read_text(encoding="utf-8"))
    parts = []
    for r in chunk.refs:
        if r.scheme == "json_pointer":
            parts.append(_get(doc, r.address))
        else:
            ptr, start, end = r.address
            parts.append(_get(doc, ptr)[start:end])
    return "\n".join(parts)


def tag_chunk(view: str, model: str = TAGGER_MODEL) -> tuple[list[str], dict]:
    """One stateless temp-0 structured call → (tags, usage). Fail loud on a
    null or schema-breaking response — never a silent empty tag set."""
    t0 = time.perf_counter()
    resp = nim.post("/chat/completions", {
        "model": model,
        "temperature": 0,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": view},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "tags", "schema": _TAGS_SCHEMA},
        },
    })
    elapsed = time.perf_counter() - t0
    usage = resp.get("usage") or {}
    choices = resp.get("choices") or []
    if not choices:
        raise RuntimeError("tagger returned no choices")
    finish = choices[0].get("finish_reason")
    content = (choices[0].get("message") or {}).get("content")
    if content is None:
        raise RuntimeError(f"tagger returned null content (finish_reason={finish})")
    try:
        tags = json.loads(content)["tags"]
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise TypeError("tags is not list[str]")
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise RuntimeError(
            f"tagger broke the tags schema (finish_reason={finish}): {content!r}") from e
    return tags, {
        "tokens_in": int(usage.get("prompt_tokens", 0) or 0),       # left = NIM's API field; right = our name
        "tokens_out": int(usage.get("completion_tokens", 0) or 0),
        "tokens": int(usage.get("total_tokens", 0) or 0),
        "time": elapsed,
        "finish_reason": finish,
        "n_tags": len(tags),
    }


def _spread(bucket: list, take: int) -> list:
    """`take` items evenly spread across a bucket — variety, deterministic."""
    if take >= len(bucket):
        return bucket
    step = len(bucket) // take
    return [bucket[i * step] for i in range(take)]


def _sample(chunks: list[Chunk], n: int) -> list[Chunk]:
    """n chunks stratified across content-kinds (round-robin allocation)."""
    from collections import defaultdict
    by_kind: dict[str, list] = defaultdict(list)
    for c in chunks:
        by_kind[c.kind].append(c)
    kinds = sorted(by_kind)
    per, extra = divmod(n, len(kinds))
    out = []
    for j, k in enumerate(kinds):
        out += _spread(by_kind[k], per + (1 if j < extra else 0))
    return out


def smoke(n: int = 10, model: str = TAGGER_MODEL) -> None:
    """Tag n stratified chunks on `model` via NIM; print tags-by-chunk_id and the
    usage metrics, then project the full corpus run."""
    data_root = Path("data/corpus")
    key = load_key("artefact/keys/Salesforce__HERB.yaml")
    chunks = chunk_dataset(data_root / "Salesforce__HERB", data_root, key)
    sample = _sample(chunks, n)
    nim.require_key()

    print(f"== tagger smoke: {len(sample)} chunks on {model} ==\n")
    usages, failed = [], 0
    for c in sample:
        view = tagger_view(c, data_root)
        try:
            tags, usage = tag_chunk(view, model)
        except RuntimeError as e:  # surface the failure, keep the partial metrics
            failed += 1
            print(f"[{c.kind}] {c.chunk_id}  FAILED: {str(e)[:90]}\n")
            continue
        usages.append(usage)
        print(f"[{c.kind}] {c.chunk_id}  ({usage['n_tags']} tags, {usage['tokens']} tok)")
        print(f"    view: {view[:160]!r}{'…' if len(view) > 160 else ''}")
        for t in tags:
            print(f"      • {t}")
        print()

    n_done = len(usages)
    if not n_done:
        print(f"== all {failed} calls failed ==")
        return
    tot_tok = sum(u["tokens"] for u in usages)
    tot_in = sum(u["tokens_in"] for u in usages)
    tot_out = sum(u["tokens_out"] for u in usages)
    tot_time = sum(u["time"] for u in usages)
    tags_each = sorted(u["n_tags"] for u in usages)
    full = len(chunks)
    print("== metrics ==")
    print(f"  model           {model}")
    print(f"  chunks tagged   {n_done}  (failed {failed})")
    print(f"  tokens          in={tot_in} out={tot_out} total={tot_tok}  ({tot_tok // n_done}/chunk)")
    print(f"  tags/chunk      min={tags_each[0]} median={tags_each[n_done // 2]} max={tags_each[-1]}")
    print(f"  latency         {tot_time / n_done:.1f}s/chunk (wall {tot_time:.0f}s)")
    print(f"\n== full-run projection ({full} chunks) ==")
    print(f"  tokens          ~{tot_tok // n_done * full:,} ({tot_out // n_done * full:,} generated)")
    print(f"  time @ 40 RPM   ~{full / 40:.0f} min   (NIM: free)")


def _checkpoint_done(out: Path) -> set:
    """chunk_ids already tagged (by any model). Tolerates a torn final line from a
    hard crash — that one chunk re-tags on the next run."""
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["chunk_id"])
            except json.JSONDecodeError:
                break
    return done


ERROR_LIMIT = 5  # consecutive bad responses on a model before rotating to the next
DRY_BACKOFF = (30, 60, 120, 300, 600)  # escalating cooldown (s) when every model is walled; caps + repeats


def tag_corpus(models: list[str] | str, dataset: str = "Salesforce__HERB",
               limit: int | None = None) -> None:
    """Blast-until-wall across a model pool into ONE resumable checkpoint
    (output/tags/<dataset>.jsonl), deduped by chunk_id — any model's tag counts,
    nothing is re-tagged, each record stamped with the model that wrote it.

    Cycle the pool: tag with a model until NIM rate-limits it (the 429 wall), rotate
    to the next, and keep cycling — a model walled early in a pass can recover by the
    time we come back. Stop only when a whole pass tags nothing (every model walled)
    or the corpus is done. A crash or lockout loses nothing; rerun continues.
    """
    if isinstance(models, str):
        models = [models]
    data_root = Path("data/corpus")
    out = Path("output/tags") / f"{dataset}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    chunks = chunk_dataset(data_root / dataset, data_root, load_key(f"artefact/keys/{dataset}.yaml"))
    done = _checkpoint_done(out)
    pending = [c for c in chunks if c.chunk_id not in done]
    if limit is not None:
        pending = pending[:limit]

    nim.require_key()
    abort.watch()  # press q for a graceful stop — the checkpoint is already durable per chunk
    print(f"blast-tagging {len(pending)} chunks across {len(models)} models, concurrently "
          f"({len(done)} done / {len(chunks)} total) -> {out}")
    bar = tqdm(total=len(done) + len(pending), initial=len(done), unit="chunk")
    t0 = time.perf_counter()
    lock = threading.Lock()  # guards pending, the checkpoint file, and the bar

    cycle = dry = 0
    with out.open("a", encoding="utf-8") as f:

        def blast(model: str) -> int:
            """One worker: tag with `model`, pulling from the shared pending pool, until
            the model walls or errors out. Each model paces on its own NIM clock, so the
            workers run truly in parallel. The chunk it was on goes back to the pool on a
            wall/error, for another model or the next cycle. Returns the count it tagged."""
            short = model.split("/")[-1]
            tagged = errors = 0
            while not abort.aborted():
                with lock:
                    if not pending:
                        return tagged
                    c = pending.pop()
                try:
                    tags, u = tag_chunk(tagger_view(c, data_root), model)
                except abort.Aborted:
                    with lock: pending.append(c)
                    return tagged
                except httpx.HTTPStatusError as e:
                    with lock: pending.append(c)
                    bar.write(f"  {short} HTTP {e.response.status_code} — out this round")
                    return tagged
                except RuntimeError as e:
                    with lock: pending.append(c)
                    if "gave up after" in str(e):  # walled — drop out; other workers / next cycle cover it
                        bar.write(f"  {short} walled — out this round")
                        return tagged
                    errors += 1
                    bar.write(f"  ! {short} skip {c.chunk_id}: {str(e)[:45]}")
                    if errors >= ERROR_LIMIT:  # too many bad responses — give up on this model for now
                        bar.write(f"  {short} {errors} errors — out this round")
                        return tagged
                    continue
                with lock:
                    f.write(json.dumps({"chunk_id": c.chunk_id, "kind": c.kind, "model": model,
                                        "tags": tags, "tokens_in": u["tokens_in"],
                                        "tokens_out": u["tokens_out"]}, ensure_ascii=False) + "\n")
                    f.flush()
                    bar.update(1)
                tagged += 1
                errors = 0
            return tagged

        while pending and not abort.aborted():
            cycle += 1
            bar.set_description(f"cycle {cycle}")
            with ThreadPoolExecutor(max_workers=len(models)) as ex:
                futs = [ex.submit(blast, m) for m in models]   # submit ALL, then collect (parallel)
                cycle_tagged = sum(fut.result() for fut in futs)
            if not pending or abort.aborted():
                break
            if cycle_tagged == 0:  # every model walled this cycle — wait for quotas to recover, keep going
                wait = DRY_BACKOFF[min(dry, len(DRY_BACKOFF) - 1)]
                dry += 1
                bar.write(f"all {len(models)} models walled (cycle {cycle}) — cooling {wait}s, then continuing")
                slept = 0.0
                while slept < wait and not abort.aborted():
                    time.sleep(min(5.0, wait - slept)); slept += 5.0
            else:
                dry = 0
    bar.close()
    _write_build_stats(out, dataset, chunks, time.perf_counter() - t0)


def _write_build_stats(out: Path, dataset: str, chunks: list, el: float) -> None:
    """The artefact arm's build cost in the SAME contract vocabulary the lucene/vector
    arms record (contract.BuildStats + ModelUsage: calls/tokens/time). Cumulative from
    the checkpoint (the source of truth); wall-time accumulates across reruns."""
    from collections import Counter
    recs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    cum_in = sum(r["tokens_in"] for r in recs)
    cum_out = sum(r["tokens_out"] for r in recs)
    cum_tags = sum(len(r["tags"]) for r in recs)
    by_model = dict(Counter(r["model"] for r in recs))
    stats_path = out.with_suffix(".stats.json")
    prior = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {"runs": 0, "wall_seconds": 0.0}
    wall = round(prior["wall_seconds"] + el, 1)
    build = BuildStats(build_time_s=wall, models=sorted(by_model),
                       model=ModelUsage(calls=len(recs), tokens=cum_in + cum_out, time_s=wall))
    stats = {
        "dataset": dataset,
        "build_stats": asdict(build),
        "chunks_tagged": len(recs), "chunks_total": len(chunks),
        "tokens_in": cum_in, "tokens_out": cum_out,
        "tags_total": cum_tags, "tags_per_chunk": round(cum_tags / len(recs), 1) if recs else 0,
        "by_model": by_model,
        "runs": prior["runs"] + 1, "wall_seconds": wall,
    }
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"\n== build stats ==  -> {stats_path.name}")
    print(f"  progress      {len(recs)}/{len(chunks)} chunks tagged   (run #{stats['runs']})")
    print(f"  by model      {by_model}")
    print(f"  tokens        in={cum_in:,}  out={cum_out:,}  total={cum_in + cum_out:,}")
    print(f"  tags          {cum_tags:,} total  ({stats['tags_per_chunk']}/chunk)")
    print(f"  time (cum)    {wall:.0f}s over {stats['runs']} run(s)")
    if len(recs) < len(chunks):
        print(f"  remaining     {len(chunks) - len(recs)} — rerun to continue")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args == ["smoke"]:
        smoke()
    elif args:
        tag_corpus(models=args)  # the blast pool, in priority order, named on the command line
    else:
        print("usage: python -m artefact.tag <model_id> [<model_id> ...]   # blast pool, priority order")
        print("       python -m artefact.tag smoke")
