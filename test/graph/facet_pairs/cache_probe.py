"""Train cheap heads on ONE frozen backbone cache and read the diagnostic table off it.

The cache comes from the Colab extractor (`colab/facet_pairs_bakeoff/extract_standalone.py`):
one `.npz` per backbone holding, per edge, the first-token vector and the attention-masked mean
of the last four layers, plus `n_tokens`, `truncated` and — for the rerankers — the model's own
relevance logit. Nothing here runs a backbone; the representations are frozen input.

What is identical for every candidate, as PROGRESS.md fixed before any result existed: the
chunk split, the 1,720 judged rows, the known topic labels, the head designs, the Davidson
pairwise loss, the pooling variants. For each candidate the (head, variant) pair is chosen on
the TRAINING-chunk validation carve-out only; the held-out chunks are read once, with that one
combination.

Variants, nine: the eight saved vectors (`cls_L-1..-4`, `mean_L-1..-4`) and
`concat(cls_L-1, mean_L-1)` — the last being the pooling the 09-17/09-18 ranker used.

Heads, three:
  linear   — one scalar per facet straight off the pooled vector;
  mlp      — one hidden layer (width 128, a stated default of this file) shared by the five,
             then five scalars;
  separate — an independent one-hidden-layer MLP per facet, sharing no trainable parameter.

The topic control is the ONLY place the known topic values are opened. Its heads are fitted on
pairs built from the known topic ORDER of training-chunk topic-sample edges (a gap under 0.03 —
the project's measured write-to-write noise of topic, 2026-09-18 — is a tie) and read as a
Spearman on held-out-chunk topic-sample edges. The Opus-trained heads never see a topic number.

Stated defaults of this file, none of them his: hidden width 128; Adam lr 1e-3, weight decay
1e-4; at most 300 epochs, full-batch, early stopping with patience 30 on validation macro
agreement; features z-scored with the fit set's own mean and sd; 5,000 topic-control pairs;
bootstrap B = 10,000 over held-out chunks; seed 20260919.

    python test/graph/facet_pairs/cache_probe.py \\
        --cache output/facet_pairs/bakeoff/cache/tasksource__deberta-small-long-nli.npz
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from . import data as D
    from .train import OUTCOME_ID, davidson_nll
except ImportError:  # run as a script
    import data as D  # noqa: E402
    from train import OUTCOME_ID, davidson_nll  # noqa: E402

FACETS = D.FACETS
N_FACETS = len(FACETS)

VARIANTS = (["cls_L-%d" % i for i in range(1, 5)]
            + ["mean_L-%d" % i for i in range(1, 5)]
            + ["concat_L-1"])
HEADS = ("linear", "mlp", "separate")

HIDDEN = 128
LR = 3e-3
WEIGHT_DECAY = 1e-4
MAX_EPOCHS = 400
PATIENCE = 60
SEED = 20260919
BOOT = 10000
TOPIC_PAIRS = 5000
TOPIC_TIE = 0.03          # the measured write-to-write noise of topic, 2026-09-18
FULL_GRAPH_EDGES = 61018  # what F's cache-size figure is quoted for


# ---------------------------------------------------------------- the cache

class Cache:
    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.path = str(path)
        self.edge_ids = [str(x) for x in z["edge_id"]]
        self.index = {e: i for i, e in enumerate(self.edge_ids)}
        # Kept in the dtype the extractor stored (float16). float16 -> float32 is exact, so
        # casting one variant at a time in `features()` gives the same numbers as holding
        # eight float32 copies and, at 61,018 edges, is the difference between fitting in
        # memory and paging.
        self.vectors = {k: np.asarray(z[k])
                        for k in z.files if k.startswith("cls_") or k.startswith("mean_")}
        self.n_tokens = np.asarray(z["n_tokens"], dtype=np.int64)
        self.truncated = np.asarray(z["truncated"], dtype=bool)
        self.native_logit = (np.asarray(z["native_logit"], dtype=np.float32)
                             if "native_logit" in z.files else None)
        meta_path = Path(path).with_suffix("").as_posix() + ".meta.json"
        self.meta = (json.loads(Path(meta_path).read_text(encoding="utf-8"))
                     if Path(meta_path).is_file() else {})
        self.name = self.meta.get("model") or Path(path).stem.replace("__", "/")
        self.hidden = int(self.meta.get("hidden_size")
                          or next(iter(self.vectors.values())).shape[1])

    def features(self, variant: str) -> np.ndarray:
        if variant == "concat_L-1":
            return np.concatenate([self.vectors["cls_L-1"], self.vectors["mean_L-1"]],
                                  axis=1).astype(np.float32)
        return self.vectors[variant].astype(np.float32)

    def variants(self) -> list:
        return [v for v in VARIANTS
                if v == "concat_L-1" and "cls_L-1" in self.vectors and "mean_L-1" in self.vectors
                or v in self.vectors]

    def cache_bytes(self, n_edges: int = FULL_GRAPH_EDGES) -> int:
        """F: what the full graph would cost in this backbone's cache — 8 vectors, float16."""
        return int(n_edges) * 8 * int(self.hidden) * 2


# ---------------------------------------------------------------- the heads

class Head(nn.Module):
    def __init__(self, dim: int, kind: str, hidden: int = HIDDEN):
        super().__init__()
        if kind not in HEADS:
            raise ValueError(f"head must be one of {HEADS}, got {kind!r}")
        self.kind = kind
        if kind == "linear":
            self.net = nn.Linear(dim, N_FACETS)
        elif kind == "mlp":
            self.net = nn.Sequential(nn.Linear(dim, hidden), nn.GELU(),
                                     nn.Linear(hidden, N_FACETS))
        else:
            self.net = nn.ModuleList([
                nn.Sequential(nn.Linear(dim, hidden), nn.GELU(), nn.Linear(hidden, 1))
                for _ in range(N_FACETS)])
        self.tie_log = nn.Parameter(torch.zeros(N_FACETS))

    def forward(self, x):
        if self.kind == "separate":
            return torch.cat([m(x) for m in self.net], dim=-1)
        return self.net(x)

    def nu(self, facet_ids):
        return self.tie_log[facet_ids].exp()


# ---------------------------------------------------------------- observations -> tensors

def encode_obs(obs: list, index: dict) -> dict:
    """Observation lists to index tensors. Observations whose edges are not cached are dropped."""
    ia, ib, fi, oi, keep = [], [], [], [], []
    for k, o in enumerate(obs):
        a, b = index.get(o["a_edge_id"]), index.get(o["b_edge_id"])
        if a is None or b is None:
            continue
        ia.append(a)
        ib.append(b)
        fi.append(FACETS.index(o["facet"]))
        oi.append(OUTCOME_ID[o["outcome"]])
        keep.append(k)
    return {"a": torch.tensor(ia, dtype=torch.long), "b": torch.tensor(ib, dtype=torch.long),
            "facet": torch.tensor(fi, dtype=torch.long),
            "outcome": torch.tensor(oi, dtype=torch.long),
            "keep": keep, "n": len(keep)}


def subset(encs: list) -> tuple:
    """Remap a group of encodings onto only the cache rows they touch.

    A training step never needs the rows nothing points at, and the caches are ten times the
    size of the judged edge set, so the fit runs on the small matrix and the final scoring on
    the full one.
    """
    rows = sorted({int(v) for e in encs for v in e["a"].tolist() + e["b"].tolist()})
    remap = {r: i for i, r in enumerate(rows)}
    out = []
    for e in encs:
        out.append({**e,
                    "a": torch.tensor([remap[int(v)] for v in e["a"].tolist()],
                                      dtype=torch.long),
                    "b": torch.tensor([remap[int(v)] for v in e["b"].tolist()],
                                      dtype=torch.long)})
    return rows, out


def agreement_macro(scores: np.ndarray, enc: dict, obs: list) -> float:
    """Macro over the five facets of the share of DECIDED observations ordered as the judge."""
    per = []
    for f in range(N_FACETS):
        sel = [i for i in range(enc["n"])
               if int(enc["facet"][i]) == f and int(enc["outcome"][i]) in (0, 1)]
        if not sel:
            continue
        ok = 0
        for i in sel:
            g = scores[int(enc["a"][i]), f] - scores[int(enc["b"][i]), f]
            ok += int((g > 0 and int(enc["outcome"][i]) == 0)
                      or (g < 0 and int(enc["outcome"][i]) == 1))
        per.append(ok / len(sel))
    return float(np.mean(per)) if per else float("nan")


def fit_head(X: torch.Tensor, fit: dict, val: dict, val_obs: list, kind: str,
             seed: int, max_epochs: int = MAX_EPOCHS, patience: int = PATIENCE,
             lr: float = LR, wd: float = WEIGHT_DECAY, hidden: int = HIDDEN) -> tuple:
    """Fit one head on `fit`, select the epoch on `val`. Returns (head, best val agreement)."""
    if fit["n"] == 0:
        raise RuntimeError("no fit observations reach this cache: the judged pairs' edges are "
                           "not in it")
    torch.manual_seed(seed)
    head = Head(X.shape[1], kind, hidden)
    opt = torch.optim.Adam(head.parameters(), lr=lr, weight_decay=wd)
    best, best_state, bad = -1.0, None, 0
    for _ in range(max_epochs):
        head.train()
        opt.zero_grad()
        s = head(X)
        sa = s[fit["a"]].gather(-1, fit["facet"].unsqueeze(-1)).squeeze(-1)
        sb = s[fit["b"]].gather(-1, fit["facet"].unsqueeze(-1)).squeeze(-1)
        loss = davidson_nll(sa, sb, head.nu(fit["facet"]), fit["outcome"])
        loss.backward()
        opt.step()
        head.eval()
        with torch.no_grad():
            sc = head(X).numpy()
        a = agreement_macro(sc, val, val_obs) if val["n"] else float(-loss.detach())
        if a > best:
            best, bad = a, 0
            best_state = {k: v.detach().clone() for k, v in head.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        head.load_state_dict(best_state)
    head.eval()
    return head, best


def standardise(F: np.ndarray, rows: list) -> tuple:
    mu = F[rows].mean(axis=0) if rows else F.mean(axis=0)
    sd = F[rows].std(axis=0) if rows else F.std(axis=0)
    sd = np.where(sd < 1e-6, 1.0, sd)
    return ((F - mu) / sd).astype(np.float32), mu, sd


# ---------------------------------------------------------------- the topic control

def load_topic(stats_path: str, wanted: set) -> dict:
    """edge_id -> known topic. THE ONLY reader of the known values in this module."""
    out = {}
    with open(stats_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("topic") is None:
                continue
            e = D.edge_id(r["chunk_id"], r["tag"])
            if e in wanted:
                out[e] = float(r["topic"])
    return out


def topic_pairs(edges: list, topic: dict, n: int, seed: int) -> list:
    """Observations in the judged rows' shape, labelled by the KNOWN topic order."""
    if len(edges) < 2:
        return []
    rng = random.Random(seed)
    out, seen = [], set()
    tries = 0
    while len(out) < n and tries < n * 50:
        tries += 1
        a, b = rng.choice(edges), rng.choice(edges)
        if a == b:
            continue
        lo, hi = sorted((a, b))
        if (lo, hi) in seen:
            continue
        seen.add((lo, hi))
        gap = topic[lo] - topic[hi]
        outcome = "equal" if abs(gap) < TOPIC_TIE else ("first" if gap > 0 else "second")
        ca, _ = D.split_edge_id(lo)
        cb, _ = D.split_edge_id(hi)
        out.append({"facet": "topic", "a_edge_id": lo, "b_edge_id": hi,
                    "a_chunk_id": ca, "b_chunk_id": cb, "outcome": outcome,
                    "pair_type": "topic_control", "pair_id": None, "row_id": None})
    return out


def spearman(x: list, y: list):
    if len(x) < 3:
        return None
    return _pearson(_ranks(x), _ranks(y))


def _ranks(v: list) -> list:
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def _pearson(a: list, b: list):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if va == 0 or vb == 0:
        return None
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb)


# ---------------------------------------------------------------- C, the teacher side

def teacher_same_side(rows: list) -> dict:
    """Opus's own raw answers, facet against facet: among held-out rows where BOTH facets name
    a side, the share where they name the same side. Ten unordered facet pairs."""
    out = {}
    for i in range(N_FACETS):
        for j in range(i + 1, N_FACETS):
            fi, fj = FACETS[i], FACETS[j]
            items = []
            for r in rows:
                ans = r.get("answers_canonical") or {}
                a, b = ans.get(fi), ans.get(fj)
                if a in ("first", "second") and b in ("first", "second"):
                    items.append({"row_id": r.get("row_id"), "same": a == b,
                                  "chunk": _row_chunk(r)})
            out[f"{fi}~{fj}"] = items
    return out


def _row_chunk(r: dict) -> str:
    ea, ca, _ = D._edge_of(r["a"])
    eb, cb, _ = D._edge_of(r["b"])
    return min(ca, cb)


# ---------------------------------------------------------------- D, per-edge variation

def within_chunk_share(values: np.ndarray, chunks: list) -> list:
    """Per facet, the share of the output's variance that lies BETWEEN TAGS INSIDE one chunk.

    The usual variance decomposition: total = between-chunk + within-chunk, and D is
    within / total, computed over the chunks that carry two or more cached edges.
    """
    by = {}
    for i, c in enumerate(chunks):
        by.setdefault(c, []).append(i)
    if values.shape[0] < 2:
        return [None] * values.shape[1]
    within = np.zeros(values.shape[1])
    for g in by.values():
        if len(g) > 1:
            v = values[g]
            within += ((v - v.mean(axis=0)) ** 2).sum(axis=0)
    total = ((values - values.mean(axis=0)) ** 2).sum(axis=0)
    return [float(within[f] / total[f]) if total[f] > 0 else None
            for f in range(values.shape[1])]


# ---------------------------------------------------------------- the run

def run(cache_path: str, answers: str, rows_path: str, stats: str, edges_path: str,
        seed: int = SEED, boot: int = BOOT, topic_n: int = TOPIC_PAIRS,
        heads=HEADS, variants=None, max_epochs: int = MAX_EPOCHS,
        patience: int = PATIENCE, hidden: int = HIDDEN, quiet: bool = False,
        artifacts: dict | None = None) -> dict:
    """`artifacts`, when a dict is passed, is filled with the fitted head, the scores matrix
    over every cached edge and the encodings, so a caller can score and retrain without
    running the selection a second time. It changes nothing this function computes."""
    t0 = time.perf_counter()
    cache = Cache(cache_path)
    texts = D.load_texts(rows_path) if Path(rows_path).is_file() else {}
    answer_rows = D.load_answer_rows(answers)
    obs_all = D.observations(answer_rows)
    part = D.partition_observations(obs_all)

    # held-out observations: one per (pair, facet, presentation order), smallest repeat
    try:
        from .evaluate import first_presentations
    except ImportError:
        from evaluate import first_presentations  # noqa: E402
    held_obs = first_presentations(part["heldout"])
    tv = D.training_val_split(part["train"])
    fit_obs, val_obs = tv["fit"], tv["val"]
    D.assert_no_heldout(part["train"])

    if not quiet:
        print(f"cache_probe | {cache.name}", flush=True)
        print(f"  cached edges {len(cache.edge_ids)} | hidden {cache.hidden} | "
              f"native_logit {cache.native_logit is not None}", flush=True)
    idx = cache.index
    enc_fit = encode_obs(fit_obs, idx)
    enc_val = encode_obs(val_obs, idx)
    enc_held = encode_obs(held_obs, idx)
    if not quiet:
        print(f"  observations fit {len(fit_obs)} ({enc_fit['n']} cached) | "
              f"validation {len(val_obs)} ({enc_val['n']}) | "
              f"held-out {len(held_obs)} ({enc_held['n']})", flush=True)
    val_obs_k = [val_obs[k] for k in enc_val["keep"]]
    held_obs_k = [held_obs[k] for k in enc_held["keep"]]

    fit_rows = sorted({int(v) for v in enc_fit["a"].tolist() + enc_fit["b"].tolist()})
    var_list = list(variants) if variants is not None else cache.variants()

    # ---- selection on the validation carve-out ONLY
    selection = []
    best = None
    sub_rows, (sub_fit, sub_val) = subset([enc_fit, enc_val])
    for variant in var_list:
        Fz, _, _ = standardise(cache.features(variant), fit_rows)
        X = torch.from_numpy(Fz)
        Xs = X[sub_rows]
        for kind in heads:
            head, va = fit_head(Xs, sub_fit, sub_val, val_obs_k, kind, seed,
                                max_epochs, patience, hidden=hidden)
            selection.append({"variant": variant, "head": kind, "val_agreement": va})
            if best is None or va > best["val_agreement"]:
                best = {"variant": variant, "head": kind, "val_agreement": va,
                        "model": head, "X": X}
            if not quiet:
                print(f"    {variant:<12} {kind:<9} val {va:.4f}", flush=True)
    if best is None:
        raise RuntimeError("no (head, variant) combination could be fitted")
    if not quiet:
        print(f"  selected {best['head']} on {best['variant']} "
              f"(validation {best['val_agreement']:.4f})", flush=True)

    with torch.no_grad():
        scores = best["model"](best["X"]).numpy()

    if artifacts is not None:
        artifacts.update({
            "cache": cache, "head": best["model"], "head_kind": best["head"],
            "variant": best["variant"], "scores": scores, "fit_rows": fit_rows,
            "enc_fit": enc_fit, "enc_val": enc_val, "enc_held": enc_held,
            "fit_obs": fit_obs, "val_obs": val_obs_k, "held_obs": held_obs_k,
            "index": idx, "hidden": hidden, "seed": seed,
            "max_epochs": max_epochs, "patience": patience})

    # ---- A: held-out agreement, and the per-item records the bootstrap reads
    A_items, per_facet, per_type = [], {}, {}
    for i in range(enc_held["n"]):
        o = held_obs_k[i]
        if int(enc_held["outcome"][i]) not in (0, 1):
            continue
        f = int(enc_held["facet"][i])
        g = float(scores[int(enc_held["a"][i]), f] - scores[int(enc_held["b"][i]), f])
        correct = ((g > 0 and int(enc_held["outcome"][i]) == 0)
                   or (g < 0 and int(enc_held["outcome"][i]) == 1))
        A_items.append({"cluster": min(o["a_chunk_id"], o["b_chunk_id"]),
                        "facet": FACETS[f], "pair_type": o.get("pair_type"),
                        "correct": bool(correct), "gap": abs(g),
                        "row_id": o.get("row_id")})
    for f in FACETS:
        sub = [it for it in A_items if it["facet"] == f]
        per_facet[f] = {"n": len(sub),
                        "agreement": (sum(it["correct"] for it in sub) / len(sub))
                        if sub else None}
        for t in sorted({str(it["pair_type"]) for it in sub}):
            s2 = [it for it in sub if str(it["pair_type"]) == t]
            per_type.setdefault(f, {})[t] = {
                "n": len(s2), "agreement": sum(it["correct"] for it in s2) / len(s2)}
    _a = [v["agreement"] for v in per_facet.values() if v["agreement"] is not None]
    A = float(np.mean(_a)) if _a else None

    # ---- E: the score gap on decided pairs against pairs Opus called equal
    E = {}
    for f in FACETS:
        dec = [it["gap"] for it in A_items if it["facet"] == f]
        tie = []
        for i in range(enc_held["n"]):
            if int(enc_held["outcome"][i]) != 2 or FACETS[int(enc_held["facet"][i])] != f:
                continue
            fi = int(enc_held["facet"][i])
            tie.append(abs(float(scores[int(enc_held["a"][i]), fi]
                                 - scores[int(enc_held["b"][i]), fi])))
        E[f] = {"mean_gap_decided": float(np.mean(dec)) if dec else None,
                "mean_gap_tied": float(np.mean(tie)) if tie else None,
                "difference": (float(np.mean(dec)) - float(np.mean(tie)))
                if dec and tie else None,
                "n_decided": len(dec), "n_tied": len(tie)}

    # ---- C: collapse excess against Opus's own raw answers, same held-out rows
    held_rows = [r for r in answer_rows if str(r.get("set")) == D.HELDOUT_SET]
    teacher = teacher_same_side(held_rows)
    row_by_id = {r.get("row_id"): r for r in held_rows}
    C_items, C_pairs = [], {}
    for key, items in teacher.items():
        fi, fj = key.split("~")
        a_i, b_i = FACETS.index(fi), FACETS.index(fj)
        stu, tea = [], []
        for it in items:
            r = row_by_id.get(it["row_id"])
            if r is None:
                continue
            ea, _, _ = D._edge_of(r["a"])
            eb, _, _ = D._edge_of(r["b"])
            ia, ib = idx.get(ea), idx.get(eb)
            if ia is None or ib is None:
                continue
            gi = scores[ia, a_i] - scores[ib, a_i]
            gj = scores[ia, b_i] - scores[ib, b_i]
            if gi == 0 or gj == 0:
                continue
            same_student = (gi > 0) == (gj > 0)
            C_items.append({"cluster": it["chunk"], "facet_pair": key,
                            "student_same": bool(same_student),
                            "teacher_same": bool(it["same"])})
            stu.append(bool(same_student))
            tea.append(bool(it["same"]))
        C_pairs[key] = {"n": len(stu),
                        "student": float(np.mean(stu)) if stu else None,
                        "teacher": float(np.mean(tea)) if tea else None,
                        "excess": (float(np.mean(stu)) - float(np.mean(tea)))
                        if stu else None}
    _c = [v["excess"] for v in C_pairs.values() if v["excess"] is not None]
    C = float(np.mean(_c)) if _c else None

    # ---- B: the topic control, the only reading of the known topic values
    bake = [json.loads(l) for l in Path(edges_path).read_text(encoding="utf-8").splitlines()
            if l.strip()]
    ts = [r for r in bake if r.get("topic_sample")]
    ts_train = [r["edge_id"] for r in ts if r["split"] == "train" and r["edge_id"] in idx]
    ts_held = [r["edge_id"] for r in ts if r["split"] == "heldout" and r["edge_id"] in idx]
    known = load_topic(stats, set(ts_train) | set(ts_held))
    ts_train = [e for e in ts_train if e in known]
    ts_held = [e for e in ts_held if e in known]

    tp = topic_pairs(ts_train, known, topic_n, seed)
    tp_fit = [o for o in tp if not (D.is_train_val(o["a_chunk_id"])
                                    or D.is_train_val(o["b_chunk_id"]))]
    tp_val = [o for o in tp if o not in tp_fit]
    enc_tfit, enc_tval = encode_obs(tp_fit, idx), encode_obs(tp_val, idx)
    tval_k = [tp_val[k] for k in enc_tval["keep"]]
    tfit_rows = sorted({int(v) for v in enc_tfit["a"].tolist() + enc_tfit["b"].tolist()})

    b_best = None
    b_selection = []
    t_rows, (t_fit, t_val) = (subset([enc_tfit, enc_tval]) if enc_tfit["n"]
                              else ([], (None, None)))
    for variant in (var_list if enc_tfit["n"] else []):
        Fz, _, _ = standardise(cache.features(variant), tfit_rows)
        Xt = torch.from_numpy(Fz)
        Xts = Xt[t_rows]
        for kind in heads:
            h, va = fit_head(Xts, t_fit, t_val, tval_k, kind, seed,
                             max_epochs, patience, hidden=hidden)
            b_selection.append({"variant": variant, "head": kind, "val_agreement": va})
            if b_best is None or va > b_best["val_agreement"]:
                with torch.no_grad():
                    b_best = {"variant": variant, "head": kind, "val_agreement": va,
                              "scores": h(Xt).numpy()}
    B_items = ([{"cluster": D.split_edge_id(e)[0],
                 "pred": float(b_best["scores"][idx[e], 0]), "known": known[e]}
                for e in ts_held] if b_best else [])
    B = spearman([it["pred"] for it in B_items], [it["known"] for it in B_items])

    # ---- D: per-edge variation on the held-out-split cached edges
    held_edges = [r["edge_id"] for r in bake
                  if r["split"] == "heldout" and r["edge_id"] in idx]
    hv = np.array([scores[idx[e]] for e in held_edges], dtype=np.float64)
    hc = [D.split_edge_id(e)[0] for e in held_edges]
    Dvals = within_chunk_share(hv, hc)
    D_items = [{"cluster": hc[i], "values": hv[i].tolist()} for i in range(len(held_edges))]

    # ---- F
    F = {"truncation_rate": (float(cache.truncated.mean())
                             if len(cache.truncated) else None),
         "n_truncated": int(cache.truncated.sum()),
         "seconds_per_1000_edges": cache.meta.get("seconds_per_1000_edges"),
         "device": cache.meta.get("device"),
         "cache_bytes_full_graph": cache.cache_bytes(),
         "cache_mb_full_graph": round(cache.cache_bytes() / 1e6, 1),
         "hidden_size": cache.hidden,
         "max_length": cache.meta.get("max_length"),
         "n_tokens_median": int(np.median(cache.n_tokens)) if len(cache.n_tokens) else None}

    # ---- G: the rerankers' own logit alone
    G = None
    if cache.native_logit is not None:
        g_items = []
        for i in range(enc_held["n"]):
            if int(enc_held["outcome"][i]) not in (0, 1):
                continue
            o = held_obs_k[i]
            g = float(cache.native_logit[int(enc_held["a"][i])]
                      - cache.native_logit[int(enc_held["b"][i])])
            g_items.append({"cluster": min(o["a_chunk_id"], o["b_chunk_id"]),
                            "facet": FACETS[int(enc_held["facet"][i])],
                            "correct": bool((g > 0 and int(enc_held["outcome"][i]) == 0)
                                            or (g < 0 and int(enc_held["outcome"][i]) == 1))})
        gA = {f: (lambda s: (sum(it["correct"] for it in s) / len(s)) if s else None)(
            [it for it in g_items if it["facet"] == f]) for f in FACETS}
        gB = spearman([float(cache.native_logit[idx[e]]) for e in ts_held],
                      [known[e] for e in ts_held])
        G = {"A_macro": float(np.mean([v for v in gA.values() if v is not None])),
             "A_per_facet": gA, "B_spearman": gB, "items": g_items}

    result = {
        "candidate": cache.name,
        "cache": str(cache_path),
        "cache_meta": cache.meta,
        "config": {"seed": seed, "boot": boot, "heads": list(heads),
                   "variants": var_list, "hidden": hidden, "lr": LR,
                   "weight_decay": WEIGHT_DECAY, "max_epochs": max_epochs,
                   "patience": patience, "topic_pairs": topic_n, "topic_tie": TOPIC_TIE,
                   "full_graph_edges": FULL_GRAPH_EDGES},
        "counts": {"cached_edges": len(cache.edge_ids),
                   "fit_obs": enc_fit["n"], "val_obs": enc_val["n"],
                   "heldout_obs": enc_held["n"],
                   "topic_fit_pairs": enc_tfit["n"], "topic_val_pairs": enc_tval["n"],
                   "topic_heldout_edges": len(ts_held)},
        "selected": {"head": best["head"], "variant": best["variant"],
                     "val_agreement": best["val_agreement"]},
        "selection": selection,
        "topic_selected": ({"head": b_best["head"], "variant": b_best["variant"],
                            "val_agreement": b_best["val_agreement"]} if b_best else None),
        "topic_selection": b_selection,
        "A": {"macro": A, "per_facet": per_facet, "per_pair_type": per_type,
              "items": A_items},
        "B": {"spearman": B, "n": len(B_items), "items": B_items},
        "C": {"excess": C, "per_facet_pair": C_pairs, "items": C_items},
        "D": {"within_chunk_share": dict(zip(FACETS, Dvals)), "items": D_items},
        "E": E,
        "F": F,
        "G": G,
        "wall_s": round(time.perf_counter() - t0, 1),
    }
    if not quiet:
        def _s(v, fmt="%.4f"):
            return "-" if v is None else fmt % v
        print(f"  A {_s(A)} | B {_s(B)} | C {_s(C, '%+.4f')} | "
              f"D {[_s(v, '%.3f') for v in Dvals]}", flush=True)
        print(f"done | {result['wall_s']}s", flush=True)
    return result


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="cheap heads on one frozen backbone cache")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--rows", default="output/facet_neural/rows_export.jsonl")
    ap.add_argument("--stats", default="output/facet_stats/herb-eval-volmax.jsonl")
    ap.add_argument("--edges", default="output/facet_pairs/bakeoff/edges.jsonl")
    ap.add_argument("--out", default="")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--boot", type=int, default=BOOT)
    ap.add_argument("--topic-pairs", type=int, default=TOPIC_PAIRS)
    ap.add_argument("--max-epochs", type=int, default=MAX_EPOCHS)
    a = ap.parse_args(argv)

    r = run(a.cache, a.answers, a.rows, a.stats, a.edges, a.seed, a.boot,
            a.topic_pairs, max_epochs=a.max_epochs)
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, indent=1), encoding="utf-8")
        print(f"  -> {p}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
