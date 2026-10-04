"""What the raw answers look like before any model reads them.

Per facet: the tie rate; the order-flip rate (the same pair asked in both presentation orders,
the canonical answers differing — the canonical form already maps both presentations onto the
sorted edge ids, so a flip is the judge changing its mind with the order, not a bookkeeping
artefact); the repeat-flip rate (the identical question asked again, the answers differing); and
the cycles — triangles a > b > c > a — over the comparison graph.

Cycles matter because a scalar score cannot produce one: every cyclic triangle is a comparison
the ranker must get wrong somewhere. The count is reported beside the number of triangles
present, so it reads against its own opportunity.

Connectivity is reported per facet because a comparison graph in many components has no single
scale joining them; the components and the degree distribution say how much of the order is
pinned by the labels and how much by the shared encoder alone.

Counts only. Nothing here decides anything.

    python test/graph/facet_pairs/diagnostics.py --out output/facet_pairs/diagnostics
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, str(_p))

try:  # package first: the plain name collides with facet_neural's own data.py
    from . import data as D
except ImportError:  # run as a script on the desktop
    import data as D  # noqa: E402

FACETS = D.FACETS


def flip_rates(obs: list) -> dict:
    """Per facet: order flips (both presentation orders of one pair) and repeat flips."""
    order_groups, repeat_groups = {}, {}
    for o in obs:
        if o.get("pair_id") is None:
            continue
        r = 0 if o.get("repeat") is None else int(o["repeat"])
        order_groups.setdefault((o["pair_id"], o["facet"], r), []).append(o)
        repeat_groups.setdefault((o["pair_id"], o["facet"], o.get("order")), []).append(o)
    out = {}
    for facet in FACETS:
        rows = [o for o in obs if o["facet"] == facet]
        og = [v for k, v in order_groups.items()
              if k[1] == facet and len({o.get("order") for o in v}) > 1]
        rg = [v for k, v in repeat_groups.items()
              if k[1] == facet and len({o.get("repeat") for o in v}) > 1]
        o_flip = sum(1 for v in og if len({o["outcome"] for o in v}) > 1)
        r_flip = sum(1 for v in rg if len({o["outcome"] for o in v}) > 1)
        out[facet] = {
            "n_observations": len(rows),
            "n_ties": sum(1 for o in rows if o["outcome"] == "equal"),
            "tie_rate": (sum(1 for o in rows if o["outcome"] == "equal") / len(rows)
                         if rows else None),
            "n_order_groups": len(og), "order_flips": o_flip,
            "order_flip_rate": o_flip / len(og) if og else None,
            "n_repeat_groups": len(rg), "repeat_flips": r_flip,
            "repeat_flip_rate": r_flip / len(rg) if rg else None,
        }
    return out


def majority_orientation(obs: list, facet: str) -> dict:
    """Per unordered edge pair, the majority decided outcome; ties and splits dropped."""
    votes = {}
    for o in obs:
        if o["facet"] != facet or o["outcome"] == "equal":
            continue
        k = (o["a_edge_id"], o["b_edge_id"])
        v = votes.setdefault(k, [0, 0])
        v[0 if o["outcome"] == "first" else 1] += 1
    out = {}
    for (a, b), (fa, fb) in votes.items():
        if fa > fb:
            out[(a, b)] = (a, b)      # a beats b
        elif fb > fa:
            out[(a, b)] = (b, a)
    return out


def graph_stats(obs: list, facet: str) -> dict:
    """Components, degree distribution and cyclic triangles of one facet's comparison graph."""
    adj, edges = {}, set()
    for o in obs:
        if o["facet"] != facet:
            continue
        a, b = o["a_edge_id"], o["b_edge_id"]
        edges.add((a, b))
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    if not adj:
        return {"nodes": 0, "edges": 0}
    parent = {n: n for n in adj}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    comps = {}
    for n in adj:
        comps.setdefault(find(n), 0)
        comps[find(n)] += 1
    deg = sorted(len(v) for v in adj.values())

    wins = majority_orientation(obs, facet)
    beats = set(wins.values())
    nodes = sorted(adj)
    idx = {n: i for i, n in enumerate(nodes)}
    triangles = cyclic = 0
    for a in nodes:
        na = {x for x in adj[a] if idx[x] > idx[a]}
        for b in sorted(na):
            for c in sorted(x for x in adj[b] if idx[x] > idx[b] and x in na):
                triangles += 1
                tri = [(a, b), (b, c), (a, c)]
                if all(t in wins for t in tri):
                    d = [wins[t] for t in tri]
                    outdeg = {}
                    for u, v in d:
                        outdeg[u] = outdeg.get(u, 0) + 1
                        outdeg.setdefault(v, 0)
                    if set(outdeg.values()) == {1}:
                        cyclic += 1
    return {
        "nodes": len(adj), "edges": len(edges),
        "components": len(comps),
        "largest_component": max(comps.values()),
        "degree_min": deg[0], "degree_median": statistics.median(deg),
        "degree_mean": statistics.fmean(deg), "degree_max": deg[-1],
        "oriented_pairs": len(wins),
        "triangles": triangles, "cyclic_triangles": cyclic,
        "cyclic_share": cyclic / triangles if triangles else None,
        "beats_relations": len(beats),
    }


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="the raw answers, counted")
    ap.add_argument("--answers", default="output/facet_pairs/answers")
    ap.add_argument("--sets", default="", help="comma-separated set names; default every set")
    ap.add_argument("--control-set", default="control",
                    help="the set the order-flip rate is reported on")
    ap.add_argument("--out", default="output/facet_pairs/diagnostics")
    a = ap.parse_args(argv)

    sets = [s for s in a.sets.split(",") if s] or None
    rows = D.load_answer_rows(a.answers, sets=sets)
    obs = D.observations(rows)
    print(f"facet pairs diagnostics | answer rows {len(rows)} | observations {len(obs)}",
          flush=True)

    control = [o for o in obs if o.get("set") == a.control_set]
    result = {
        "n_answer_rows": len(rows), "n_observations": len(obs),
        "sets": sorted({o.get("set") for o in obs}),
        "all_sets": flip_rates(obs),
        "control_set": {"name": a.control_set, "n_observations": len(control),
                        "rates": flip_rates(control)},
        "comparison_graph": {f: graph_stats(obs, f) for f in FACETS},
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diagnostics.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    (out / "diagnostics.md").write_text(render_md(result), encoding="utf-8")
    for f in FACETS:
        r = result["all_sets"][f]
        g = result["comparison_graph"][f]
        print(f"  {f:<13} n {r['n_observations']:>6} ties {_p(r['tie_rate'])} "
              f"order-flip {_p(r['order_flip_rate'])} repeat-flip {_p(r['repeat_flip_rate'])} "
              f"| nodes {g.get('nodes', 0)} components {g.get('components', 0)} "
              f"cyclic {g.get('cyclic_triangles', 0)}/{g.get('triangles', 0)}", flush=True)
    print(f"done | -> {out}", flush=True)
    return 0


def _p(v, nd=3):
    return "-" if v is None else f"%.{nd}f" % v


def render_md(r: dict) -> str:
    L = [f"# facet_pairs — the raw answers", "",
         f"{r['n_answer_rows']} answer rows, {r['n_observations']} observations, sets: "
         f"{', '.join(str(s) for s in r['sets'])}", "",
         "## rates, every set", "",
         "| facet | observations | ties | tie rate | order groups | order flips | rate | "
         "repeat groups | repeat flips | rate |", "|---|---|---|---|---|---|---|---|---|---|"]
    for f in FACETS:
        v = r["all_sets"][f]
        L.append(f"| {f} | {v['n_observations']} | {v['n_ties']} | {_p(v['tie_rate'])} | "
                 f"{v['n_order_groups']} | {v['order_flips']} | {_p(v['order_flip_rate'])} | "
                 f"{v['n_repeat_groups']} | {v['repeat_flips']} | "
                 f"{_p(v['repeat_flip_rate'])} |")
    c = r["control_set"]
    L += ["", f"## the control set `{c['name']}` ({c['n_observations']} observations)", "",
          "| facet | tie rate | order-flip rate | repeat-flip rate |", "|---|---|---|---|"]
    for f in FACETS:
        v = c["rates"][f]
        L.append(f"| {f} | {_p(v['tie_rate'])} | {_p(v['order_flip_rate'])} | "
                 f"{_p(v['repeat_flip_rate'])} |")
    L += ["", "## the comparison graph", "",
          "| facet | nodes | pairs | components | largest | degree min/median/max | "
          "oriented | triangles | cyclic | share |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for f in FACETS:
        g = r["comparison_graph"][f]
        if not g.get("nodes"):
            L.append(f"| {f} | 0 | 0 | | | | | | | |")
            continue
        L.append(f"| {f} | {g['nodes']} | {g['edges']} | {g['components']} | "
                 f"{g['largest_component']} | {g['degree_min']}/{g['degree_median']:.0f}/"
                 f"{g['degree_max']} | {g['oriented_pairs']} | {g['triangles']} | "
                 f"{g['cyclic_triangles']} | {_p(g['cyclic_share'])} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
