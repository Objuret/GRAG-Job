"""The CLI's own transcript of the proof calls on the MADE-UP question, against what the harness kept.

Only the made-up question (output/walkthrough) is read here, so text may be shown. No transcript of a
call on a test question is opened.

    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/main/cli_transcript_proof_call.py
"""
import calendar
import difflib
import io
import json
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[4]
LANE = Path.home() / ".claude" / "projects" / "C--Users-jocke-AppData-Local-Temp-herb-claude-lane"
BASE = REPO / "output" / "research" / "2026-10-08-keep-everything-proof"


def ts(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def files(a, b):
    out = []
    with os.scandir(LANE) as it:
        for e in it:
            if e.name.endswith(".jsonl") and ts(a) <= e.stat().st_mtime <= ts(b):
                out.append(e.path)
    return sorted(out, key=os.path.getmtime)


def load(p):
    return [json.loads(x) for x in open(p, encoding="utf-8", errors="replace") if x.strip()]


def user_text(o):
    c = (o.get("message") or {}).get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = [b.get("text") for b in c if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p) or None
    return None


row = json.loads((BASE / "lucene__answer" / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()[0])
call = next(c for c in row["calls"] if c["kind"] == "chat")
kept_answer = json.loads(call["text"])["answer"]
tr = load(files("2026-10-08T00:21:45Z", "2026-10-08T00:22:10Z")[0])

print("== the answer call (lucene proof) ==")
first_user = next(o for o in tr if o.get("type") == "user" and user_text(o))
sent = user_text(first_user)
print(f"prompt the harness kept: {len(call['prompt'])} chars | user message in the CLI's transcript: "
      f"{len(sent)} chars | the kept prompt is inside it verbatim: {call['prompt'] in sent}")
if call["prompt"] in sent:
    i = sent.index(call["prompt"])
    print(f"   text before it ({i} chars): {sent[:i]!r}")
    print(f"   text after it ({len(sent) - i - len(call['prompt'])} chars): {sent[i + len(call['prompt']):]!r}")
else:
    # where do the two texts part?
    n = next((k for k, (x, y) in enumerate(zip(call["prompt"], sent)) if x != y), min(len(sent), len(call["prompt"])))
    print(f"   same for the first {n} chars; kept prompt goes on {call['prompt'][n:n + 80]!r}; "
          f"transcript goes on {sent[n:n + 80]!r}")
    print(f"   transcript's last 120 chars: {sent[-120:]!r}")
    print(f"   kept prompt's last 120 chars: {call['prompt'][-120:]!r}")
    print(f"   newline counts: kept {call['prompt'].count(chr(10))} LF / {call['prompt'].count(chr(13))} CR; "
          f"transcript {sent.count(chr(10))} LF / {sent.count(chr(13))} CR")
for o in tr:
    t = o.get("type")
    if t == "user" and user_text(o):
        print("   user record:", {k: o[k] for k in ("entrypoint", "permissionMode", "promptSource", "version") if k in o})
    elif t == "ai-title":
        print("   ai-title record:", o.get("aiTitle"))
    elif t == "attachment":
        a = o.get("attachment") or {}
        print("   attachment record:", json.dumps(a, ensure_ascii=False)[:500])
    elif t == "queue-operation":
        print("   queue-operation:", o.get("operation"), "| content chars:", len(o.get("content") or ""))
    elif t == "assistant":
        m = o["message"]
        for b in m["content"]:
            bt = b.get("type")
            if bt == "thinking":
                print(f"   assistant block thinking: text {len(b.get('thinking') or '')} chars, signature "
                      f"{len(b.get('signature') or '')} chars | effort on the record: {o.get('effort')!r} | "
                      f"version {o.get('version')} | model {m.get('model')}")
            elif bt == "text":
                print(f"   assistant block text: {len(b['text'])} chars | similarity to the kept answer "
                      f"({len(kept_answer)} chars): {difflib.SequenceMatcher(None, b['text'], kept_answer).ratio():.2f}"
                      f" | starts: {b['text'][:200]!r}")
            elif bt == "tool_use":
                inp = b.get("input") or {}
                print(f"   assistant block tool_use: name {b.get('name')!r} | input keys {sorted(inp)} | "
                      f"input.answer equals the kept answer: {inp.get('answer') == kept_answer}")
    elif t == "user":
        for b in (o["message"].get("content") or []):
            if isinstance(b, dict) and b.get("type") == "tool_result":
                print("   tool_result:", json.dumps(b.get("content"), ensure_ascii=False)[:200])

print("\n== the calls of the vector answer + evaluation proof ==")
ev_calls = [json.loads(x) for x in (BASE / "vector__answer__eval" / "eval_calls.jsonl")
            .read_text(encoding="utf-8").splitlines() if x.strip()]
kept = [c for c in ev_calls if c.get("kind") == "chat"]
vrow = json.loads((BASE / "vector__answer__eval" / "arm_outputs.jsonl").read_text(encoding="utf-8").splitlines()[0])
kept.append({**next(c for c in vrow["calls"] if c["kind"] == "chat"), "score": "(the answer call)"})
for p in files("2026-10-08T09:55:45Z", "2026-10-08T09:59:40Z"):
    t = load(p)
    u = next((o for o in t if o.get("type") == "user" and user_text(o)), None)
    if u is None:
        continue
    s = user_text(u)
    match = next((c for c in kept if c["prompt"] in s or s in c["prompt"]), None)
    asst = [o for o in t if o.get("type") == "assistant"]
    blocks = [b.get("type") for o in asst for b in o["message"]["content"]]
    eff = sorted({repr(o.get("effort")) for o in asst})
    models = sorted({str(o["message"].get("model")) for o in asst})
    outs = sorted({o["message"].get("usage", {}).get("output_tokens") for o in asst})
    think = sum(len(b.get("thinking") or "") for o in asst for b in o["message"]["content"] if b.get("type") == "thinking")
    text = sum(len(b.get("text") or "") for o in asst for b in o["message"]["content"] if b.get("type") == "text")
    name = f"call for {match.get('score')}" if match else "no kept prompt matches"
    extra = (len(s) - len(match["prompt"])) if match else None
    print(f"   {name}: user message {len(s)} chars ({extra} more than the kept prompt) | model {models} | "
          f"effort on the record {eff} | blocks {blocks} | thinking text {think} chars | text {text} chars | "
          f"output_tokens {outs} | title record: {any(o.get('type') == 'ai-title' for o in t)}")
