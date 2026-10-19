"""The first rows of a run that is under way: keys and counts only, no question, answer or context text."""
import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
d = Path(sys.argv[1])
rows = [json.loads(x) for x in (d / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
print(f"rows so far {len(rows)}")
for r in rows[:2]:
    chat = [c for c in r.get("calls") or [] if c.get("kind") == "chat"]
    emb = [c for c in r.get("calls") or [] if c.get("kind") == "embed"]
    c = chat[0] if chat else {}
    e = c.get("envelope") or {}
    print(f"row keys {sorted(r)}")
    print(f"   answer chars {len(r['answer'])} | contexts {len(r['contexts'])} ({sum(map(len, r['contexts']))} chars) | ids {len(r['context_ids'])} | search_time_s {r['search_time_s']:.3f} | leg {r.get('leg')}")
    print(f"   generator {r['generator']}")
    print(f"   timing {r.get('timing')}")
    print(f"   meta.char_budget {(r.get('meta') or {}).get('char_budget')}")
    rk = (r.get('meta') or {}).get('ranking') or {}
    print(f"   meta.ranking: n_units {rk.get('n_units')} n_ranked {rk.get('n_ranked')} scores {len(rk.get('scores') or [])} next_score {rk.get('next_score')}")
    print(f"   calls: chat {len(chat)}, embed {len(emb)} | chat call keys {sorted(c)}")
    print(f"   applied {c.get('applied')} | not_applied {sorted(c.get('not_applied') or {})} | config dir set: {'CLAUDE_CONFIG_DIR' in (c.get('env_set') or {})} | tries {[(a['n'], a['outcome'], round(a['seconds'], 1)) for a in c.get('attempts') or []]}")
    print(f"   envelope keys {sorted(e)} | num_turns {e.get('num_turns')} | models {sorted((e.get('modelUsage') or {}).keys())}")
