"""What a proof folder made with the fixed lane holds: per call what was applied, and the CLI's own
transcript of the same call (structure only). Made-up question only.

    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/proof_now/show_fixed.py <folder>
"""
import io
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
d = Path(sys.argv[1])
LANE = Path.home() / ".claude-herb-lane" / "projects" / "C--Users-jocke-AppData-Local-Temp-herb-claude-lane"


def transcript(session_id):
    f = LANE / f"{session_id}.jsonl"
    if not f.is_file():
        return "no transcript file"
    kinds, blocks, models, efforts, entry = Counter(), Counter(), Counter(), Counter(), Counter()
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        kinds[e.get("type")] += 1
        if e.get("entrypoint"):
            entry[e["entrypoint"]] += 1
        for k in ("effort", "effortLevel"):
            if e.get(k):
                efforts[e[k]] += 1
        m = e.get("message") or {}
        if e.get("type") == "assistant":
            models[m.get("model")] += 1
            for b in m.get("content") or []:
                blocks[b.get("type")] += 1
    return (f"entries {dict(kinds)} | assistant blocks {dict(blocks)} | models {dict(models)} | "
            f"effort fields {dict(efforts)} | entrypoint {dict(entry)}")


def show_call(c, indent="   "):
    e = c.get("envelope") or {}
    u = e.get("usage") or {}
    print(f"{indent}call: model {c['model']} | system {len(c['system'])} chars | prompt {len(c['prompt'])} chars | "
          f"tries {[(a['n'], a['outcome'], round(a['seconds'], 2)) for a in c['attempts']]}")
    print(f"{indent}   applied {json.dumps(c.get('applied'))}")
    print(f"{indent}   not_applied {json.dumps(c.get('not_applied'))}")
    print(f"{indent}   env_set {json.dumps(c.get('env_set'))} | env_unset {c.get('env_unset')}")
    print(f"{indent}   envelope: num_turns {e.get('num_turns')} stop {e.get('stop_reason')} duration_ms {e.get('duration_ms')} "
          f"api_ms {e.get('duration_api_ms')} | in {u.get('input_tokens')} cache_creation {u.get('cache_creation_input_tokens')} "
          f"cache_read {u.get('cache_read_input_tokens')} out {u.get('output_tokens')} | models {sorted((e.get('modelUsage') or {}).keys())}")
    print(f"{indent}   kept usage {c.get('usage')} | text {len(c.get('text') or '')} chars")
    print(f"{indent}   CLI's own transcript: {transcript(e.get('session_id'))}")


rows = [json.loads(x) for x in (d / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
man = json.loads((d / "run_manifest.json").read_text(encoding="utf-8"))
for r in rows:
    print(f"row {r['id']}: answer {len(r['answer'])} chars | contexts {len(r['contexts'])} "
          f"({sum(map(len, r['contexts']))} chars) | generator {r['generator']}")
    for c in r.get("calls") or []:
        if c["kind"] == "chat":
            show_call(c)
g = man.get("generator") or {}
print(f"\nmanifest.generator: payload {json.dumps(g.get('payload'))}")
print(f"   applied {json.dumps(g.get('applied'))}")
print(f"   not_applied {json.dumps(g.get('not_applied'))}")
print(f"   env_set {json.dumps(g.get('env_set'))} | env_unset {g.get('env_unset')}")
print(f"manifest.lane: {json.dumps(man.get('lane'))}")
print(f"manifest.env: {json.dumps({k: (v if len(str(v)) < 40 else str(v)[:37] + '...') for k, v in (man.get('env') or {}).items()})}")
env = man.get("environment") or {}
print(f"manifest.environment: python {env.get('python')} at {env.get('python_executable')} | packages {env.get('packages')} | packages_all {len(env.get('packages_all') or [])} lines")
print(f"manifest.code_version {man.get('code_version')}")
for leg in man.get("legs") or []:
    cs = leg.get("code_state") or {}
    f = d / cs.get("diff_file", "-")
    import hashlib
    ok = f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() == cs.get("diff_sha256")
    print(f"   start {leg['leg']}: {leg['started_at'][11:19]}-{leg['finished_at'][11:19]} answered {leg['n_answered']} of todo {leg['n_todo']} | "
          f"code_version {leg['code_version']['commit'][:7]} dirty {leg['code_version']['dirty']} | diff file {cs.get('diff_file')} "
          f"sha256 of the file equals the recorded one: {ok} | untracked files hashed {len(cs.get('untracked_sha256') or {})}")
ev = d / "eval_manifest.json"
if ev.is_file():
    em = json.loads(ev.read_text(encoding="utf-8"))
    print(f"\neval_manifest: judge_model {em.get('judge_model')} | backend {em.get('judge_backend')} | usage {em.get('judge_usage')}")
    for leg in em.get("judge_legs") or []:
        s = leg.get("settings") or {}
        print(f"   scoring start {s.get('started_at', '')[11:19]}: judge_model {leg.get('judge_model')} | calls {(leg.get('usage') or {}).get('calls')} | "
              f"tries {s.get('judge_max_tries')} | empty-reply tries {s.get('judge_empty_reply_tries')} | cells {s.get('cells')} | scores {len(s.get('scores') or [])}")
        print(f"      judge_call {json.dumps(s.get('judge_call'))}")
        print(f"      ragas {s.get('ragas')} run_config {s.get('ragas_run_config')} do_not_track {s.get('ragas_do_not_track')}")
    res = [json.loads(x) for x in (d / "eval_results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    print(f"   eval_results rows {len(res)}: " + ", ".join(f"{r['metric']}={r['status']}" for r in res))
    calls = [json.loads(x) for x in (d / "eval_calls.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    chats = [c for c in calls if c.get("kind") == "chat"]
    print(f"   eval_calls lines {len(calls)}: chat {len(chats)}, embed {len(calls) - len(chats)}")
    for c in chats:
        print(f"   score {c.get('score')}:")
        show_call(c, indent="      ")
