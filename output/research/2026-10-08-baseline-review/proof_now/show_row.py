"""What a proof folder of today's code holds: the row, its calls, the manifest's starts. Made-up question only."""
import io, json, sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
d = Path(sys.argv[1])
old = Path(sys.argv[2]) if len(sys.argv) > 2 else None

def paths(v, p=""):
    if isinstance(v, dict):
        for k, w in v.items():
            yield from paths(w, f"{p}.{k}" if p else k)
    elif isinstance(v, list):
        for w in v[:3]:
            yield from paths(w, p + "[]")
    else:
        yield p

rows = [json.loads(x) for x in (d / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
print(f"rows {len(rows)} | ids {[r['id'] for r in rows]}")
for r in rows:
    g, rt = r["generator"], r["retrieval"]
    rk = (r.get("meta") or {}).get("ranking") or {}
    print(f"\nrow {r['id']}: answer {len(r['answer'])} chars | contexts {len(r['contexts'])} ({sum(map(len, r['contexts']))} chars), ids {len(r['context_ids'])} | search {r['search_time_s']:.3f} s | leg {r.get('leg')}")
    print(f"   generator {g}")
    print(f"   retrieval {rt}")
    print(f"   timing {r.get('timing')}")
    print(f"   meta.ranking: n_units {rk.get('n_units')} n_ranked {rk.get('n_ranked')} scores {len(rk.get('scores') or [])} next_score {rk.get('next_score')}")
    print(f"   dollar key anywhere in the row: {any('cost' in p.lower() and 'envelope' not in p for p in paths(r))}")
    for c in r.get("calls") or []:
        if c["kind"] == "chat":
            e = c.get("envelope") or {}
            u = e.get("usage") or {}
            print(f"   call chat: model {c['model']} | flags {c['flags']} | effort field {c.get('effort')!r} | dropped {c.get('payload_dropped')} | prompt {len(c['prompt'])} chars | tries {[(a['n'], a['outcome'], round(a['seconds'], 2)) for a in c['attempts']]}")
            print(f"        started {c['started_at'][11:23]} finished {c['finished_at'][11:23]} | kept usage {c['usage']}")
            print(f"        envelope: num_turns {e.get('num_turns')} stop {e.get('stop_reason')} duration_ms {e.get('duration_ms')} api_ms {e.get('duration_api_ms')} ttft {e.get('ttft_ms')} | usage in {u.get('input_tokens')} cache_creation {u.get('cache_creation_input_tokens')} cache_read {u.get('cache_read_input_tokens')} out {u.get('output_tokens')} | iterations {len(u.get('iterations') or [])} | models {sorted((e.get('modelUsage') or {}).keys())} | session {e.get('session_id')}")
        else:
            print(f"   call embed: {c['input_type']} prefix {c['prefix']!r} device {c['device']} tokens {c['tokens']} encode_s {c['encode_s']:.3f} lock_wait_s {c['lock_wait_s']:.6f} started {c['started_at'][11:23]}")
print(f"\nmanifest: generator.payload {json.dumps((man.get('generator') or {}).get('payload'))} | workers {man.get('workers')} | top_k {man.get('top_k')} | lane cli {((man.get('lane') or {}).get('cli_version'))} | env {man.get('env')}")
print(f"   code_version {man['code_version']} | code_state: diff_file {man['code_state'].get('diff_file')} untracked {len(man['code_state'].get('untracked_sha256') or {})}")
print(f"   index {json.dumps(man.get('index'))[:420]}")
for leg in man.get("legs") or []:
    print(f"   start {leg['leg']}: {leg['started_at'][11:19]}-{leg['finished_at'][11:19]} wall {leg['wall_s']:.1f} s cpu {leg.get('process_cpu_s')} workers {leg['workers']} answered {leg['n_answered']} todo {leg['n_todo']} prepare {leg['prepare_s']:.1f} s peak mem {leg['peak_memory_bytes']/1e9:.2f} GB embedder_load {leg.get('embedder_load_s')}")
if old and (old / "arm_outputs.jsonl").is_file():
    o = json.loads((old / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    a, b = set(paths(o)), set(paths(rows[0]))
    print(f"\nagainst the earlier proof row ({old.name}): key paths only in the earlier one: {sorted(a - b)} | only in today's: {sorted(b - a)}")
    om = json.loads((old / "run_manifest.json").read_text(encoding="utf-8"))
    a, b = set(paths(om)), set(paths(man))
    print(f"manifest key paths only in the earlier one: {sorted(a - b)[:20]} | only in today's: {sorted(b - a)[:20]}")
    print(f"same delivered ids as the earlier proof: {o['context_ids'] == rows[0]['context_ids']} | same context text: {o['contexts'] == rows[0]['contexts']} | same answer text: {o['answer'] == rows[0]['answer']}")
