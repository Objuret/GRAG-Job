"""The whole graph read before anything is measured: every label with its count and its keys,
every relation type between which labels with its count and its keys, and how the structural
relations fan out (per relation type: how many targets a source has, how many sources a target
has). Read only; no model call; no gold."""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("NEO4J_DATABASE", "herb-eval-volmax")

from graph import db  # noqa: E402

DB = os.environ["NEO4J_DATABASE"]
with db._driver() as driver, driver.session(database=DB) as s:
    print(f"database {DB}")
    labels = s.run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC").data()
    for row in labels:
        keys = s.run(f"MATCH (n:`{row['l']}`) WITH n LIMIT 2000 UNWIND keys(n) AS k RETURN DISTINCT k ORDER BY k").value()
        print(f"  {row['l']:12s} {row['c']:7d}  {', '.join(keys)}")
    rels = s.run("MATCH (a)-[r]->(b) RETURN labels(a)[0] AS a, type(r) AS t, labels(b)[0] AS b, count(*) AS c "
                 "ORDER BY c DESC").data()
    print("relations")
    for row in rels:
        keys = s.run(f"MATCH (:`{row['a']}`)-[r:`{row['t']}`]->(:`{row['b']}`) WITH r LIMIT 500 UNWIND keys(r) AS k "
                     "RETURN DISTINCT k ORDER BY k").value()
        fan = s.run(f"MATCH (a:`{row['a']}`)-[r:`{row['t']}`]->(b:`{row['b']}`) WITH a, count(b) AS k "
                    "RETURN min(k) AS lo, percentileDisc(k, 0.5) AS mid, max(k) AS hi, count(a) AS n").single()
        back = s.run(f"MATCH (a:`{row['a']}`)-[r:`{row['t']}`]->(b:`{row['b']}`) WITH b, count(a) AS k "
                     "RETURN min(k) AS lo, percentileDisc(k, 0.5) AS mid, max(k) AS hi, count(b) AS n").single()
        print(f"  {row['a']:9s} -{row['t']:20s}-> {row['b']:9s} {row['c']:7d} | per source {fan['lo']}/{fan['mid']}/{fan['hi']}"
              f" over {fan['n']} | per target {back['lo']}/{back['mid']}/{back['hi']} over {back['n']}"
              + (f" | keys {', '.join(keys)}" if keys else ""))
print("done")
