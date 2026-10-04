"""The judge control: does Opus order a pair the way the graph's topic does.

Reads the control pairs, the topic key written beside them, and the answer files. The three
lines PROGRESS.md froze before any call are decided on the cross-tag/cross-chunk pairs; the
same three lines for the same-tag and same-chunk pairs are reported and decide nothing, and so
are the four non-topic facets.

Standard errors are a bootstrap over CHUNKS, not over pairs: a chunk is drawn with replacement
`n_chunks` times and a pair is kept with the weight its two chunks' draw counts multiply to, so
two pairs sharing a chunk move together, as they do on the corpus.

    python test/graph/facet_pairs_control.py --answers output/facet_pairs/answers
    python test/graph/facet_pairs_control.py --reference
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

PAIRS_DEFAULT = ROOT / "output" / "facet_pairs" / "pairs"
ANSWERS_DEFAULT = ROOT / "output" / "facet_pairs" / "answers"
OUT_DEFAULT = ROOT / "output" / "facet_pairs" / "control"

REFERENCE_VALUES = ROOT / "output" / "facet_views" / "pilot" / "check_final" / "values.jsonl"
REFERENCE_TOPIC = ROOT / "output" / "facet_views" / "pilot" / "topic_graph.jsonl"

FACETS = ("topic", "temporal", "why", "activity", "concreteness")
PAIR_TYPES = ("cross", "same_tag", "same_chunk")
BINS = ("near", "t1", "t2", "t3")

B = 10_000
SE_K = 3
BOOT_SEED = 20260918

NEAR_EQUAL = 0.03


# ------------------------------------------------------------------ reading

def read_jsonl(path) -> list:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def load(pairs_dir: Path, answers_dir: Path) -> list:
    """One record per control pair: its key, its presentations, its answers."""
    rows = read_jsonl(pairs_dir / "control.jsonl")
    keys = {k["pair_id"]: k for k in read_jsonl(pairs_dir / "topic_key.jsonl")}
    answers = {}
    src = Path(answers_dir) / "control"
    for path in sorted(src.glob("*.json")) if src.is_dir() else []:
        if path.name.startswith("manifest.") or path.name.endswith(".failed.json"):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(rec, dict) and rec.get("answers_canonical"):
            answers[rec["row_id"]] = rec

    by_pair: dict = {}
    for r in rows:
        p = by_pair.setdefault(r["pair_id"], {"pair_id": r["pair_id"],
                                              "pair_type": r["pair_type"],
                                              "presentations": {}})
        rec = answers.get(r["row_id"])
        p["presentations"][(r["order"], r["repeat"])] = (
            rec["answers_canonical"] if rec else None)
    out = []
    for pid, p in by_pair.items():
        key = keys.get(pid)
        if key is None:
            continue
        p.update({
            "gap": key["gap"], "gap_bin": key["gap_bin"],
            "higher": "first" if key["first"]["topic"] >= key["second"]["topic"] else "second",
            "chunks": (key["first"]["edge_id"].split("::", 1)[0],
                       key["second"]["edge_id"].split("::", 1)[0]),
        })
        out.append(p)
    return out


def answered(pairs: list) -> list:
    return [p for p in pairs if any(v is not None for v in p["presentations"].values())]


# ------------------------------------------------------------------ the statistics

def agreement_of(pair: dict, facet: str):
    """The pair's agreement with the known order: the mean over its answered presentations of
    1 for the higher-topic end, 0 for the other, 0.5 for equal. None when nothing came back."""
    scores = []
    for value in pair["presentations"].values():
        if value is None:
            continue
        choice = value.get(facet)
        if choice == "equal":
            scores.append(0.5)
        elif choice == pair["higher"]:
            scores.append(1.0)
        else:
            scores.append(0.0)
    return float(np.mean(scores)) if scores else None


def tie_share_of(pair: dict, facet: str):
    vals = [v[facet] for v in pair["presentations"].values() if v is not None]
    return float(np.mean([1.0 if v == "equal" else 0.0 for v in vals])) if vals else None


def order_flip_of(pair: dict, facet: str):
    """AB against BA, both at repeat 1, mapped back to the pair's own ends."""
    ab = pair["presentations"].get(("AB", 1))
    ba = pair["presentations"].get(("BA", 1))
    if ab is None or ba is None:
        return None
    return 1.0 if ab[facet] != ba[facet] else 0.0


def repeat_flip_of(pair: dict, facet: str):
    """AB against the identical AB asked again."""
    one = pair["presentations"].get(("AB", 1))
    two = pair["presentations"].get(("AB", 2))
    if one is None or two is None:
        return None
    return 1.0 if one[facet] != two[facet] else 0.0


class Boot:
    """One chunk-level resampling scheme, reused for every statistic of one pair set."""

    def __init__(self, pairs: list, seed: int = BOOT_SEED, b: int = B):
        self.pairs = pairs
        chunks = sorted({c for p in pairs for c in p["chunks"]})
        self.index = {c: i for i, c in enumerate(chunks)}
        self.n = len(chunks)
        self.b = b
        if self.n == 0:
            self.weights = np.zeros((b, 0))
            return
        rng = np.random.default_rng(seed)
        draws = rng.multinomial(self.n, np.full(self.n, 1.0 / self.n), size=b)
        ia = np.array([self.index[p["chunks"][0]] for p in pairs])
        ib = np.array([self.index[p["chunks"][1]] for p in pairs])
        self.weights = draws[:, ia] * draws[:, ib]

    def mean(self, values) -> tuple:
        """The weight-1 mean and the bootstrap SE of it, over the pairs whose value is not
        None."""
        values = np.asarray([np.nan if v is None else float(v) for v in values], dtype=float)
        ok = ~np.isnan(values)
        if not ok.any():
            return float("nan"), float("nan")
        point = float(values[ok].mean())
        w = self.weights[:, ok]
        tot = w.sum(axis=1)
        good = tot > 0
        if not good.any():
            return point, float("nan")
        boots = (w[good] @ values[ok]) / tot[good]
        return point, float(boots.std(ddof=1)) if boots.size > 1 else float("nan")

    def difference(self, values_a, values_b) -> tuple:
        """The difference of two weighted means under one and the same resampling."""
        a = np.asarray([np.nan if v is None else float(v) for v in values_a], dtype=float)
        b = np.asarray([np.nan if v is None else float(v) for v in values_b], dtype=float)
        oa, ob = ~np.isnan(a), ~np.isnan(b)
        if not oa.any() or not ob.any():
            return float("nan"), float("nan")
        point = float(a[oa].mean() - b[ob].mean())
        wa, wb = self.weights[:, oa], self.weights[:, ob]
        ta, tb = wa.sum(axis=1), wb.sum(axis=1)
        good = (ta > 0) & (tb > 0)
        if not good.any():
            return point, float("nan")
        boots = (wa[good] @ a[oa]) / ta[good] - (wb[good] @ b[ob]) / tb[good]
        return point, float(boots.std(ddof=1)) if boots.size > 1 else float("nan")


def fmt(x) -> str:
    return "  n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


# ------------------------------------------------------------------ the report

def facet_block(pairs: list, facet: str, lines: list, deciding: bool) -> dict:
    """The three frozen lines for one pair set and one facet."""
    boot = Boot(pairs)
    wide = [p for p in pairs if p["gap_bin"] != "near"]
    wide_boot = Boot(wide)
    agree, agree_se = wide_boot.mean([agreement_of(p, facet) for p in wide])

    per_bin = {}
    for b in BINS:
        sub = [p for p in pairs if p["gap_bin"] == b]
        sb = Boot(sub)
        point, se = sb.mean([agreement_of(p, facet) for p in sub])
        ties, _ = sb.mean([tie_share_of(p, facet) for p in sub])
        per_bin[b] = {"n": len(sub), "agreement": point, "se": se, "tie_share": ties}

    rise_pairs = [p for p in pairs if p["gap_bin"] in ("t1", "t3")]
    rb = Boot(rise_pairs)
    rise, rise_se = rb.difference(
        [agreement_of(p, facet) if p["gap_bin"] == "t3" else None for p in rise_pairs],
        [agreement_of(p, facet) if p["gap_bin"] == "t1" else None for p in rise_pairs])

    order_rate, order_se = boot.mean([order_flip_of(p, facet) for p in pairs])
    repeated = [p for p in pairs if repeat_flip_of(p, facet) is not None]
    pb = Boot(repeated)
    paired = pb.difference([order_flip_of(p, facet) for p in repeated],
                           [repeat_flip_of(p, facet) for p in repeated])
    repeat_rate, repeat_se = pb.mean([repeat_flip_of(p, facet) for p in repeated])
    paired_order, _ = pb.mean([order_flip_of(p, facet) for p in repeated])

    block = {
        "n_pairs": len(pairs), "n_wide": len(wide),
        "agreement": agree, "agreement_se": agree_se,
        "bins": per_bin,
        "rise_t1_to_t3": rise, "rise_se": rise_se,
        "order_flip_rate": order_rate, "order_flip_se": order_se,
        "repeat_flip_rate": repeat_rate, "repeat_flip_se": repeat_se,
        "n_repeated": len(repeated),
        "paired_order_flip_rate": paired_order,
        "flip_difference": paired[0], "flip_difference_se": paired[1],
    }
    if deciding:
        block["line1_pass"] = bool(agree - SE_K * agree_se > 0.50) if not np.isnan(
            agree_se) else False
        block["line2_pass"] = bool(rise > 0) if not np.isnan(rise) else False
        block["line3_pass"] = bool(paired[0] <= SE_K * paired[1]) if not np.isnan(
            paired[1]) else False
    return block


def render(blocks: dict, meta: dict) -> str:
    L = []
    L.append("# facet_pairs — the Topic judge control\n")
    L.append(f"Read {meta['answered']} of {meta['pairs']} control pairs "
             f"({meta['rows_done']} of {meta['rows']} presentations answered), "
             f"model {meta.get('model')}, effort {meta.get('effort')}, "
             f"prompt {str(meta.get('prompt_sha256'))[:12]}.\n")
    L.append(f"Standard errors: bootstrap B={B}, cluster = every chunk a pair touches. "
             f"Chunks are drawn with replacement n_chunks times and a pair is kept with "
             f"weight = the product of its two chunks' draw counts.\n")
    L.append(f"Gap bins on |topic_A − topic_B|: near < {NEAR_EQUAL}, then the terciles of the "
             f"remaining gaps inside each pair type's candidate population "
             f"(edges in `pairs/meta.json`).\n")

    L.append("\n## Topic, per pair type\n")
    L.append("| pair type | pairs | agreement (non-near) | SE | 3·SE line | "
             "rise t1→t3 | SE | order flips | repeat flips | difference | SE |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for t in PAIR_TYPES:
        b = blocks["topic"][t]
        L.append(f"| {t} | {b['n_pairs']} | {fmt(b['agreement'])} | {fmt(b['agreement_se'])} | "
                 f"{fmt(b['agreement'] - SE_K * b['agreement_se'])} | {fmt(b['rise_t1_to_t3'])} "
                 f"| {fmt(b['rise_se'])} | {fmt(b['order_flip_rate'])} | "
                 f"{fmt(b['repeat_flip_rate'])} | {fmt(b['flip_difference'])} | "
                 f"{fmt(b['flip_difference_se'])} |")

    L.append("\n## Topic, per gap bin\n")
    L.append("| pair type | bin | pairs | agreement | SE | tie share |")
    L.append("|---|---|---|---|---|---|")
    for t in PAIR_TYPES:
        for bn in BINS:
            c = blocks["topic"][t]["bins"][bn]
            L.append(f"| {t} | {bn} | {c['n']} | {fmt(c['agreement'])} | {fmt(c['se'])} | "
                     f"{fmt(c['tie_share'])} |")

    L.append("\n## The four other facets — reported, deciding nothing\n")
    L.append("| facet | pair type | first | second | equal | order flips | repeat flips |")
    L.append("|---|---|---|---|---|---|---|")
    for f in FACETS:
        if f == "topic":
            continue
        for t in PAIR_TYPES:
            d = blocks["distribution"][f][t]
            b = blocks[f][t]
            L.append(f"| {f} | {t} | {fmt(d['first'])} | {fmt(d['second'])} | "
                     f"{fmt(d['equal'])} | {fmt(b['order_flip_rate'])} | "
                     f"{fmt(b['repeat_flip_rate'])} |")

    cross = blocks["topic"]["cross"]
    L.append("\n## Verdict\n")
    checks = [
        ("1. agreement above 0.50 by three SE",
         cross.get("line1_pass"),
         f"{fmt(cross['agreement'])} − 3×{fmt(cross['agreement_se'])} = "
         f"{fmt(cross['agreement'] - SE_K * cross['agreement_se'])} vs 0.500"),
        ("2. agreement rises from the small-gap bin to the large-gap bin",
         cross.get("line2_pass"),
         f"t1 {fmt(cross['bins']['t1']['agreement'])} → t3 "
         f"{fmt(cross['bins']['t3']['agreement'])}, rise {fmt(cross['rise_t1_to_t3'])} "
         f"± {fmt(cross['rise_se'])}"),
        ("3. order flips no higher than repeat flips by three SE",
         cross.get("line3_pass"),
         f"on the {cross['n_repeated']} repeated pairs, order "
         f"{fmt(cross['paired_order_flip_rate'])} − repeat "
         f"{fmt(cross['repeat_flip_rate'])} = {fmt(cross['flip_difference'])}, "
         f"3×SE = {fmt(SE_K * cross['flip_difference_se'])}; order flips over all "
         f"{cross['n_pairs']} pairs {fmt(cross['order_flip_rate'])} "
         f"± {fmt(cross['order_flip_se'])}"),
    ]
    for name, ok, detail in checks:
        L.append(f"- {'PASS' if ok else 'FAIL'} — {name}: {detail}")
    failed = [name for name, ok, _ in checks if not ok]
    verdict = "PASS" if not failed else "FAIL"
    deciding = "every line holds" if not failed else failed[0]
    L.append(f"\n**{verdict}** — {deciding} (read on the cross pairs only).\n")
    return "\n".join(L), verdict, deciding


def distribution(pairs: list, facet: str) -> dict:
    vals = [v[facet] for p in pairs for v in p["presentations"].values() if v is not None]
    n = len(vals) or 1
    return {k: vals.count(k) / n for k in ("first", "second", "equal")}


# ------------------------------------------------------------------ the reference

def reference(out_dir: Path) -> str:
    """The no-call ceiling: how often the 2026-09-18 second topic instrument (Haiku's chunk
    description, `topic_local`) orders a pair as the graph's topic does."""
    if not REFERENCE_VALUES.is_file() or not REFERENCE_TOPIC.is_file():
        return (f"\n## Reference ceiling\n\nSkipped: {REFERENCE_VALUES} or "
                f"{REFERENCE_TOPIC} is not on disk.\n")
    local: dict = {}
    for line in REFERENCE_VALUES.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("variant") != "chunk" or r.get("write") != 1 or not r.get("original"):
            continue
        key = (r["chunk_id"], r["tag"])
        if key not in local and r.get("topic_local") is not None:
            local[key] = float(r["topic_local"])
    graph = {(r["chunk_id"], r["tag"]): float(r["topic_graph"])
             for r in read_jsonl(REFERENCE_TOPIC)}
    shared = sorted(set(local) & set(graph))
    if len(shared) < 3:
        return (f"\n## Reference ceiling\n\nSkipped: only {len(shared)} edges carry both "
                f"`topic_local` (variant chunk, write 1, original) and `topic_graph`.\n")

    lv = np.array([local[k] for k in shared])
    gv = np.array([graph[k] for k in shared])
    rows = []
    for i, j in itertools.combinations(range(len(shared)), 2):
        gap = abs(gv[i] - gv[j])
        same = (gv[i] - gv[j]) * (lv[i] - lv[j])
        rows.append((gap, 1.0 if same > 0 else (0.5 if same == 0 else 0.0)))
    gaps = np.array([r[0] for r in rows])
    agree = np.array([r[1] for r in rows])
    wide = np.sort(gaps[gaps >= NEAR_EQUAL])
    cuts = (wide[len(wide) // 3], wide[2 * len(wide) // 3]) if len(wide) >= 3 else (0.0, 0.0)
    names = np.where(gaps < NEAR_EQUAL, "near",
                     np.where(gaps < cuts[0], "t1", np.where(gaps < cuts[1], "t2", "t3")))
    L = ["\n## Reference ceiling — no calls\n",
         f"{len(shared)} edges of the 2026-09-18 pilot, all "
         f"{len(rows):,} pairs of them. `topic_local` is Haiku's chunk description read as "
         f"topic; `topic_graph` is the graph's cosine. Same gap bins "
         f"(near < {NEAR_EQUAL}, terciles {cuts[0]:.4f} / {cuts[1]:.4f}).\n",
         "| bin | pairs | topic_local orders as topic_graph |", "|---|---|---|"]
    for b in BINS:
        m = names == b
        L.append(f"| {b} | {int(m.sum()):,} | "
                 f"{agree[m].mean() if m.any() else float('nan'):.3f} |")
    m = gaps >= NEAR_EQUAL
    L.append(f"| all non-near | {int(m.sum()):,} | {agree[m].mean():.3f} |")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ cli

def main(argv: list | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    ap = argparse.ArgumentParser(description="the frozen Topic judge control")
    ap.add_argument("--pairs", default=str(PAIRS_DEFAULT))
    ap.add_argument("--answers", default=str(ANSWERS_DEFAULT))
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--reference", action="store_true",
                    help="append the no-call reference ceiling")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    print(f"facet_pairs_control starting | pairs {args.pairs} | answers {args.answers}",
          flush=True)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs = load(Path(args.pairs), Path(args.answers))
    have = answered(pairs)
    rows_total = sum(len(p["presentations"]) for p in pairs)
    rows_done = sum(1 for p in pairs for v in p["presentations"].values() if v is not None)
    print(f"  control pairs {len(pairs)} | answered {len(have)} | presentations "
          f"{rows_done}/{rows_total}", flush=True)

    ref = reference(out_dir) if args.reference else ""
    if not have:
        text = ("# facet_pairs — the Topic judge control\n\nNo control answer is on disk yet; "
                f"{rows_total} presentations are waiting.\n" + ref)
        (out_dir / "report.md").write_text(text, encoding="utf-8")
        (out_dir / "verdict.json").write_text(
            json.dumps({"verdict": "PENDING", "pairs": len(pairs), "answered": 0},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(text, flush=True)
        print(f"  written {out_dir / 'report.md'} | {time.perf_counter() - t0:.1f}s",
              flush=True)
        return 0

    sample = next((json.loads(p.read_text(encoding="utf-8"))
                   for p in sorted((Path(args.answers) / "control").glob("*.json"))
                   if not p.name.endswith(".failed.json")), {})
    meta = {"pairs": len(pairs), "answered": len(have), "rows": rows_total,
            "rows_done": rows_done, "model": sample.get("model"),
            "effort": sample.get("effort"), "prompt_sha256": sample.get("prompt_sha256")}

    blocks: dict = {"distribution": {}}
    for f in FACETS:
        blocks[f] = {t: facet_block([p for p in have if p["pair_type"] == t], f, [],
                                    deciding=(f == "topic" and t == "cross"))
                     for t in PAIR_TYPES}
        blocks["distribution"][f] = {t: distribution([p for p in have
                                                      if p["pair_type"] == t], f)
                                     for t in PAIR_TYPES}

    text, verdict, deciding = render(blocks, meta)
    text += ref
    (out_dir / "report.md").write_text(text, encoding="utf-8")
    (out_dir / "verdict.json").write_text(
        json.dumps({"verdict": verdict, "deciding": deciding, "meta": meta,
                    "topic": blocks["topic"], "bootstrap": {"B": B, "seed": BOOT_SEED,
                                                            "cluster": "chunk"}},
                   ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(text, flush=True)
    print(f"  written {out_dir / 'report.md'} and {out_dir / 'verdict.json'} "
          f"| {time.perf_counter() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
