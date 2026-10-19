"""Internal consistency of the four proof folders (C, the made-up question).

    python consistency_c.py

Reads rows, manifests, eval rows, eval_calls.jsonl and the diff files of C and prints the
numbers each check compares. C's question is made up, so its text may be read here.
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from folders import GROUPS, REPO

sys.stdout.reconfigure(encoding="utf-8")
C = GROUPS["C"]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def rows(p):
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def secs(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


def mtime(p):
    return datetime.fromtimestamp(Path(p).stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


def walk(v, path=""):
    yield path, v
    if isinstance(v, dict):
        for k, x in v.items():
            yield from walk(x, path + "." + k if path else k)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from walk(x, f"{path}[{i}]")


def norm(path):
    """a[3].b -> a[].b"""
    out, i = [], 0
    while i < len(path):
        if path[i] == "[":
            out.append("[]")
            i = path.index("]", i) + 1
        else:
            out.append(path[i])
            i += 1
    return "".join(out)


def dollar_paths(obj):
    """Every key whose name speaks of money, with its value; split by who wrote it."""
    own, cli = [], []
    for path, v in walk(obj):
        leaf = path.rsplit(".", 1)[-1].lower()
        if ("cost" in leaf or "usd" in leaf) and not isinstance(v, (dict, list)):
            inside = ".envelope." in "." + path + "."
            (cli if inside else own).append((norm(path), v))
    return own, cli


def section(t):
    print()
    print("#" * 6, t)


def dollars():
    section("DOLLAR FIELDS  (own = written by the harness; cli = inside the CLI raw envelope)")
    for name, folder in C.items():
        for f in sorted(folder.iterdir()):
            if f.suffix not in (".json", ".jsonl") or f.stat().st_size == 0:
                continue
            objs = rows(f) if f.suffix == ".jsonl" else [load(f)]
            own, cli = [], []
            for o in objs:
                a, b = dollar_paths(o)
                own += a
                cli += b
            print(f"  {name:<8} {f.name:<20} written {mtime(f)}  own: {len(own)} fields, non-zero {sum(1 for _, v in own if v)}   cli: {len(cli)} fields, non-zero {sum(1 for _, v in cli if v)}")
            for p, k in sorted(Counter(p for p, _ in own).items()):
                vals = [v for q, v in own if q == p]
                print(f"             own  {p:<44} x{k}  values {vals[:6]}")
            for p, k in sorted(Counter(p for p, _ in cli).items()):
                print(f"             cli  {p:<60} x{k}")


def tokens_and_side_call():
    section("ROW TOKENS AGAINST THE ENVELOPE, AND THE SIDE CALL UNDER envelope.modelUsage")
    for name, folder in C.items():
        row = rows(folder / "arm_outputs.jsonl")[0]
        man = load(folder / "run_manifest.json")
        chats = [c for c in row["calls"] if c.get("kind") == "chat"]
        print(f"  {name}: calls in the row {len(row['calls'])} (chat {len(chats)}, embed {sum(1 for c in row['calls'] if c.get('kind') == 'embed')})")
        for c in chats:
            env, u = c["envelope"], c["envelope"]["usage"]
            parts = (u["input_tokens"], u["cache_creation_input_tokens"], u["cache_read_input_tokens"])
            g = row["generator"]
            print(f"     envelope.usage input/cache_creation/cache_read/output : {parts} / {u['output_tokens']}   sum of the three in: {sum(parts)}")
            print(f"     calls[].usage prompt/completion/cached               : {c['usage']['prompt_tokens']} / {c['usage']['completion_tokens']} / {c['usage']['cached_input_tokens']}")
            print(f"     row generator tokens_in/tokens_out/cached            : {g['tokens_in']} / {g['tokens_out']} / {g['cached_input_tokens']}")
            print(f"     generator.tokens_in == envelope sum: {g['tokens_in'] == sum(parts)}   tokens_out == envelope output: {g['tokens_out'] == u['output_tokens']}   cached == cache_read: {g['cached_input_tokens'] == u['cache_read_input_tokens']}")
            print(f"     envelope num_turns {env['num_turns']}  stop_reason {env['stop_reason']}  iterations {len(u['iterations'])}  duration_ms {env['duration_ms']}  duration_api_ms {env['duration_api_ms']}  ttft_ms {env['ttft_ms']}")
            side = {}
            for model, mu in env["modelUsage"].items():
                tin = mu["inputTokens"] + mu["cacheCreationInputTokens"] + mu["cacheReadInputTokens"]
                print(f"     modelUsage {model:<28} in {mu['inputTokens']} + cache_creation {mu['cacheCreationInputTokens']} + cache_read {mu['cacheReadInputTokens']} = {tin}   out {mu['outputTokens']}   costUSD {mu['costUSD']}")
                if model != c["model"]:
                    side[model] = (tin, mu["outputTokens"])
            print(f"     the call's model: {c['model']}   other models under modelUsage: {sorted(side)}")
            ints = Counter()
            for path, v in walk({"row": {k: v for k, v in row.items() if k != "calls"}, "manifest": man}):
                if isinstance(v, int) and not isinstance(v, bool):
                    ints[v] += 1
            for model, (tin, tout) in side.items():
                print(f"     side call {model}: in {tin}, out {tout}   the row outside calls[] or the manifest holds an integer equal to in: {ints[tin] > 0}, to in+main in ({tin + sum(parts)}): {ints[tin + sum(parts)] > 0}, to out+main out ({tout + u['output_tokens']}): {ints[tout + u['output_tokens']] > 0}")
            if "cost_usd" in c:
                tot = sum(mu["costUSD"] for mu in env["modelUsage"].values())
                print(f"     calls[].cost_usd {c['cost_usd']}   envelope.total_cost_usd {env['total_cost_usd']}   sum modelUsage costUSD {tot:.6f}   row generator.cost_usd {row['generator'].get('cost_usd')}")


def timing():
    section("timing.wall_s AGAINST ITS PARTS")
    for name, folder in C.items():
        row = rows(folder / "arm_outputs.jsonl")[0]
        t, g, r = row["timing"], row["generator"], row["retrieval"]
        parts = row["search_time_s"] + r["time_s"] + g["time_s"]
        print(f"  {name}: wall_s {t['wall_s']:.6f}   search_time_s {row['search_time_s']:.6f} + retrieval.time_s {r['time_s']:.6f} + generator.time_s {g['time_s']:.6f} = {parts:.6f}   remainder {t['wall_s'] - parts:.6f} s")
        print(f"     finished_at - started_at {secs(t['started_at'], t['finished_at']):.6f} s   answered_at - timing.finished_at {secs(t['finished_at'], row['answered_at']):.6f} s   thread {t['thread']}   leg {row['leg']}")
        for c in row["calls"]:
            if c["kind"] == "chat":
                a = c["attempts"]
                print(f"     chat call: started_at..finished_at {secs(c['started_at'], c['finished_at']):.6f} s   attempts {len(a)} seconds {[round(x['seconds'], 6) for x in a]}   generator.request_s {g['request_s']:.6f}   generator.time_s {g['time_s']:.6f}   envelope duration_ms {c['envelope']['duration_ms']}")
            else:
                print(f"     embed call: started_at..finished_at {secs(c['started_at'], c['finished_at']):.6f} s   encode_s {c['encode_s']:.6f}   lock_wait_s {c['lock_wait_s']:.9f}   retrieval.time_s {r['time_s']:.6f}   tokens_in {c['tokens_in']} (retrieval.tokens_in {r['tokens_in']})")
                keys = sorted(k for k in c if k not in ("texts",))
                print(f"       embed call keys: {keys}")
                print(f"       model {c['model']}  revision {c['revision']}  device {c['device']}  dtype {c['dtype']}  input_type {c['input_type']}  prefix {c['prefix']!r}  batch {c['batch']}  n_texts {c['n_texts']}  text == the question: {c['texts'] == [row['question']]}   a vector or its hash in the record: {any(k in c for k in ('vector', 'vectors', 'embedding', 'sha256'))}")


def the_cut_and_prompt():
    section("THE CUT, THE RANKING AND THE PROMPT")
    for name, folder in C.items():
        row = rows(folder / "arm_outputs.jsonl")[0]
        cb = row["meta"]["char_budget"]
        ctx = row["contexts"]
        print(f"  {name}: sum(len(contexts)) {sum(len(c) for c in ctx)}   kept {cb['kept']}   len(context_ids) {len(row['context_ids'])}   len(contexts) {len(ctx)}   boundary {cb['boundary']}   ids unique {len(set(row['context_ids'])) == len(row['context_ids'])}")
        rk = row["meta"].get("ranking")
        if rk is None:
            print("     meta.ranking: absent")
        else:
            s = rk["scores"]
            desc = all(a >= b for a, b in zip(s, s[1:]))
            print(f"     meta.ranking: n_units {rk['n_units']}  n_ranked {rk['n_ranked']}  len(scores) {len(s)} (len(contexts) {len(ctx)})  scores non-increasing {desc}  first {s[0]}  last {s[-1]}  next_score {rk['next_score']}  last >= next {s[-1] >= rk['next_score']}  ties among delivered {len(s) - len(set(s))}")
        for c in row["calls"]:
            if c["kind"] != "chat":
                continue
            built = "Documents:" + chr(10) + (chr(10) * 2).join(ctx) + chr(10) * 2 + "Question: " + row["question"]
            print(f"     prompt chars {len(c['prompt'])}   == 'Documents:' + contexts joined by a blank line + 'Question: ' + question: {c['prompt'] == built}   = 72000 + 2*{len(ctx) - 1} + 23 + {len(row['question'])} = {72000 + 2 * (len(ctx) - 1) + 23 + len(row['question'])}")
            print(f"     flags {c['flags']}")
            print(f"     system chars {len(c['system'])}   schema keys {sorted(c['schema'])}   timeout_s {c['timeout_s']}   max_tries {c['max_tries']}   payload_dropped {c['payload_dropped']}")
            man = load(folder / "run_manifest.json")
            gi = man.get("generator") or {}
            print(f"     manifest generator.payload keys {sorted((gi.get('payload') or {}))}   system == call system: {gi.get('system') == c['system']}   schema == call schema: {gi.get('schema') == c['schema']}   timeout == : {gi.get('timeout_s') == c['timeout_s']}")
            print(f"     answer == envelope.structured_output.answer: {row['answer'] == (c['envelope'].get('structured_output') or {}).get('answer')}   calls[].text chars {len(c['text'])}  envelope.result chars {len(c['envelope']['result'])}")


def evaluation():
    section("EVAL ROWS AGAINST eval_calls.jsonl  (C.vecAE)")
    folder = C["C.vecAE"]
    ev = rows(folder / "eval_results.jsonl")
    calls = rows(folder / "eval_calls.jsonl")
    em = load(folder / "eval_manifest.json")
    by = defaultdict(list)
    for c in calls:
        by[(c.get("question_id"), c.get("score"), c.get("eval_leg"))].append(c)
    print(f"  eval rows {len(ev)}   eval_calls lines {len(calls)}   kinds {dict(Counter((c['kind'], c['phase']) for c in calls))}")
    print(f"  {'score':<26}{'status':>7}{'value':>10}{'chat_calls':>11}{'lines':>6}{'tok_in row':>11}{'tok_in lines':>13}{'tok_out row':>12}{'tok_out lines':>14}{'chat_s row':>11}{'sum try s':>10}{'embed_calls':>12}{'wall_s':>9}")
    match = 0
    for r in ev:
        u = r["components"]["usage"]
        mine = [c for c in by[(r["question_id"], r["metric"], u["eval_leg"])] if c["kind"] == "chat"]
        tin = sum(c["usage"]["prompt_tokens"] for c in mine)
        tout = sum(c["usage"]["completion_tokens"] for c in mine)
        tries = sum(a["seconds"] for c in mine for a in c["attempts"])
        ok = (u["chat_calls"] == len(mine) and u["tokens_in"] == tin and u["tokens_out"] == tout)
        match += ok
        print(f"  {r['metric']:<26}{r['status']:>7}{r['value']:>10.4f}{u['chat_calls']:>11}{len(mine):>6}{u['tokens_in']:>11}{tin:>13}{u['tokens_out']:>12}{tout:>14}{u['chat_s']:>11.2f}{tries:>10.2f}{u['embed_calls']:>12}{u['wall_s']:>9.2f}")
    print(f"  rows whose chat_calls, tokens_in and tokens_out equal their lines in eval_calls.jsonl: {match}/{len(ev)}")
    print(f"  shared key: eval row (question_id, metric, components.usage.eval_leg) = call line (question_id, score, eval_leg); lines with no eval row: {sum(len(v) for k, v in by.items() if k[0] is None)}")
    print(f"  eval_leg values in rows {sorted(set(r['components']['usage']['eval_leg'] for r in ev))}   in call lines {sorted(set(c['eval_leg'] for c in calls))}")
    chat = [c for c in calls if c["kind"] == "chat"]
    emb = [c for c in calls if c["kind"] == "embed"]
    ju = em["judge_usage"]
    print(f"  manifest judge_usage calls {ju['calls']} / chat lines {len(chat)}   tokens_in {ju['tokens_in']} / sum prompt_tokens {sum(c['usage']['prompt_tokens'] for c in chat)}   tokens_out {ju['tokens_out']} / {sum(c['usage']['completion_tokens'] for c in chat)}   request_s {ju['request_s']:.3f} / sum try seconds {sum(a['seconds'] for c in chat for a in c['attempts']):.3f}   attempts {ju['attempts']} / {sum(len(c['attempts']) for c in chat)}")
    for c in chat:
        env = c["envelope"]
        u = env["usage"]
        side = {m: mu["inputTokens"] + mu["cacheCreationInputTokens"] + mu["cacheReadInputTokens"] for m, mu in env["modelUsage"].items() if m != c["model"]}
        print(f"     chat seq {c['seq']} {c['score']:<20} model {c['model']}  prompt chars {len(c['prompt'])}  in {u['input_tokens']}+{u['cache_creation_input_tokens']}+{u['cache_read_input_tokens']}  out {u['output_tokens']}  num_turns {env['num_turns']}  tries {len(c['attempts'])}  flags {c['flags']}  system chars {len(c['system'])}  side models in-tokens {side}")
    print(f"  embed lines {len(emb)}:")
    for c in emb:
        print(f"     phase {c['phase']}  question_id {c['question_id']}  score {c['score']}  input_type {c['input_type']}  prefix {c['prefix']!r}  n_texts {c['n_texts']}  tokens_in {c['tokens_in']}  encode_s {c['encode_s']:.4f}  device {c['device']}  revision {c['revision'][:12]}  text chars {[len(t) for t in c['texts']]}")
    print(f"  embed_calls summed over eval rows: {sum(r['components']['usage']['embed_calls'] for r in ev)}   rows of the two embedding scores: " + ", ".join(f"{r['metric']} embed_calls {r['components']['usage']['embed_calls']}" for r in ev if r['metric'] in ('semantic_similarity', 'answer_correctness')))
    print("  eval_manifest:")
    print(f"     top-level judge_model {em['judge_model']}   judge_backend {em['judge_backend']}   timestamp {em['timestamp']}   judge_elapsed_s {em['judge_elapsed_s']:.3f}")
    js = em.get("judge_settings") or {}
    print(f"     top-level judge_settings: started_at {js.get('started_at')}  finished_at {js.get('finished_at')}  wall_s {js.get('wall_s')}  cells {js.get('cells')}  embedding {js.get('embedding')}  judge_model {js.get('judge_model')}")
    for i, leg in enumerate(em.get("judge_legs") or [], 1):
        s = leg.get("settings")
        print(f"     leg {i}: timestamp {leg['timestamp']}  judge_model {leg['judge_model']}  calls {leg['usage']['calls']}  elapsed_s {leg['elapsed_s']:.3f}  has settings {s is not None}" + ("" if s is None else f"  settings.started_at {s.get('started_at')}  cells {s.get('cells')}  embedding {s.get('embedding')}"))
    print(f"     embed lines in eval_calls.jsonl {len(emb)} (tokens {sum(c['tokens_in'] for c in emb)}, encode_s {sum(c['encode_s'] for c in emb):.4f})   embedding.requests anywhere in the manifest: {[v for p, v in walk(em) if p.endswith('embedding.requests')]}")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def manifests():
    section("WHAT EACH RUN MANIFEST SAYS")
    for name, folder in C.items():
        m = load(folder / "run_manifest.json")
        env = m["environment"]
        print(f"  {name}  (written {mtime(folder / 'run_manifest.json')})")
        print(f"     commit {m['code_version']['commit'][:12]}  branch {m['code_version']['branch']}  dirty {m['code_version']['dirty']}")
        cs = m["code_state"]
        print(f"     code_state: status lines {len(cs['status'])}  diff_file {cs['diff_file']}  diff_sha256 {cs['diff_sha256'][:16]}  untracked files hashed {len(cs['untracked_sha256'])}")
        print(f"     host {env['host']}  platform {env['platform']}  python {env['python']}  exe {env['python_executable']}")
        print(f"     cpu {env['cpu']!r}  cpu_count {env['cpu_count']}  ram_bytes {env['ram_bytes']}  keys naming a GPU: {[k for k in env if 'gpu' in k.lower() or 'cuda' in k.lower()]}")
        print(f"     packages {env['packages']}")
        print(f"     embedder {env['embedder']}")
        print(f"     workers {m['workers']}  top_k {m['top_k']}  char_budget {m['char_budget']}  flags {m['flags']}  env {m['env']}  retrieval_flags {m['retrieval_flags']}")
        print(f"     lane {m['lane']}")
        idx = dict(m["index"])
        note = idx.pop("cache_cost_note", None)
        print(f"     index {idx}")
        if note is not None:
            print(f"     index.cache_cost_note {note}")
        print(f"     inputs {m['inputs']}")
        print(f"     questions_file {m['questions_file']}")
        print(f"     build_stats {m['build_stats']}")
        print(f"     generator_model {m['generator_model']}  generator keys {sorted(m['generator'] or {})}")
        for leg in m["legs"]:
            cpu = leg.get("process_cpu_s")
            print(f"     leg {leg['leg']}: {leg['started_at']} .. {leg['finished_at']}  wall_s {leg['wall_s']:.3f}  process_cpu_s {cpu}  prepare_s {leg['prepare_s']:.3f}  embedder_load_s {leg['embedder_load_s']}  peak_memory_bytes {leg['peak_memory_bytes']}  pid {leg['pid']}  n_todo {leg['n_todo']}  n_answered {leg['n_answered']}  workers {leg['workers']}  retrieval_only {leg['retrieval_only']}  evaluator {leg['evaluator']}  diff_file {leg['code_state']['diff_file']}  argv {leg['argv']}")
            widx = (leg.get("index") or {}).get("embedder_warm_s")
            if widx is not None:
                print(f"             index.embedder_warm_s {widx}")

    section("THE DIFF FILES AGAINST THE MANIFEST HASH")
    for name, folder in C.items():
        m = load(folder / "run_manifest.json")
        named = sorted(set(leg["code_state"]["diff_file"] for leg in m["legs"]))
        for f in sorted(folder.glob("*.diff")):
            raw = f.read_bytes()
            lf = raw.replace(bytes([13, 10]), bytes([10]))
            want = [leg["code_state"]["diff_sha256"] for leg in m["legs"] if leg["code_state"]["diff_file"] == f.name]
            n_files = sum(1 for line in lf.split(bytes([10])) if line.startswith(b"diff --git "))
            new_files = sum(1 for line in lf.split(bytes([10])) if line.startswith(b"new file mode"))
            has_capture = b"diff --git a/prod/harness/capture.py" in lf
            print(f"  {name} {f.name}: {len(raw)} B, CR-LF pairs {raw.count(bytes([13, 10]))}, files in the diff {n_files} (new files {new_files}), capture.py in the diff {has_capture}")
            print(f"       sha256 of the bytes {sha_bytes(raw)[:16]}   of the bytes with CR-LF as LF {sha_bytes(lf)[:16]}   manifest diff_sha256 {sorted(set(w[:16] for w in want))}   named by legs {named}")
        us = m["code_state"]["untracked_sha256"]
        same = {p: (hashlib.sha256((REPO / p).read_bytes()).hexdigest() == h) if (REPO / p).is_file() else None for p, h in us.items()}
        print(f"       untracked files hashed in the manifest: {len(us)}; a copy of any in the run folder: {any((folder / Path(p).name).exists() for p in us)}; hash equals the file on disk now: {sum(1 for v in same.values() if v)} of {len(us)}  (differ now: {[p for p, v in same.items() if v is False]})")


if __name__ == "__main__":
    dollars()
    tokens_and_side_call()
    timing()
    the_cut_and_prompt()
    evaluation()
    manifests()
