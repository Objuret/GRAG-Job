"""The answers that the CLI did not accept for their form, in the final runs' calls whose transcripts are on
this laptop: what the first answer held, whether its content is the accepted answer, and what each way of
counting such a call gives (every request, the first request only, the last request only). Structure and
numbers only; no text of a question, answer or transcript is printed.

    python output/research/2026-10-28-first-request/rejected_answers.py
"""
import json
import statistics as st
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
K = REPO / "output" / "k=chars"
T = Path.home() / ".claude-herb-lane" / "projects" / "C--Users-jocke-AppData-Local-Temp-herb-claude-lane"
SRC = ["artefact_v4__gold100__cb72000__20261020T041923Z", "artefact_v4__answerable715__cb72000__20261025T211532Z"]


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def find_answer(x, depth=0):
    """The first object, at any depth or inside a JSON string, that holds description and tags."""
    if depth > 6:
        return None
    if isinstance(x, str):
        s = x.strip()
        if s[:1] in "{[":
            try:
                return find_answer(json.loads(s), depth + 1)
            except ValueError:
                return None
        return None
    if isinstance(x, dict):
        if "description" in x and "tags" in x:
            return x
        x = list(x.values())
    if isinstance(x, list):
        for v in x:
            f = find_answer(v, depth + 1)
            if f is not None:
                return f
    return None


def canon(a):
    tl = lambda v: [(o.get("t"), o.get("facet"), o.get("matters")) if isinstance(o, dict) else o for o in (v or [])]  # noqa: E731
    return a.get("description"), tl(a.get("tags")), tl(a.get("query_tags"))


def requests(path):
    msgs, prompt, results = OrderedDict(), None, []
    for line in path.open(encoding="utf-8"):
        if not line.strip():
            continue
        o = json.loads(line)
        m = o.get("message") or {}
        if o.get("type") == "assistant" and m.get("id"):
            g = msgs.setdefault(m["id"], {"types": set(), "inp": None, "calls": 0, "out": 0, "in": 0, "end": 0.0})
            u = m.get("usage") or {}
            for b in m.get("content") or []:
                g["types"].add(b.get("type"))
                if b.get("type") == "tool_use":
                    g["calls"] += 1
                    if g["inp"] is None:
                        g["inp"] = b.get("input")
            g["out"] = max(g["out"], int(u.get("output_tokens") or 0))
            g["in"] = max(g["in"], int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
                          + int(u.get("cache_read_input_tokens") or 0))
            g["end"] = max(g["end"], ts(o["timestamp"]))
        elif o.get("type") == "user":
            c = m.get("content")
            if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                results.append(ts(o["timestamp"]))
            elif prompt is None:
                prompt = ts(o["timestamp"])
    reqs = list(msgs.values())
    # a request starts after the last tool result of the request before it, or after that request's last record
    # when it made no tool call
    starts, k = [prompt], 0
    for g in reqs[:-1]:
        k += g["calls"]
        starts.append(results[k - 1] if g["calls"] else g["end"])
    for g, s in zip(reqs, starts):
        g["span"] = g["end"] - s
    return reqs


def main():
    n = with_answer = identical = same_desc = 0
    tops, keep, first, last = Counter(), [], [], []
    out_all, out_first, in_all, in_first = [], [], [], []
    for name in SRC:
        for line in open(K / name / "arm_outputs.jsonl", encoding="utf-8"):
            r = json.loads(line)
            c = next(x for x in r["calls"] if x.get("kind") == "chat" and x.get("role") != "answer" and x.get("ok"))
            path = T / f"{c['envelope']['session_id']}.jsonl"
            if not path.exists():
                continue
            reqs = requests(path)
            api = c["envelope"]["duration_api_ms"] / 1000
            e = next(x for x in r["retrieval"] if x["kind"] == "chat")
            measured = abs((e["time_s"] - e["retry_s"]) - api) < 1e-6
            out_all.append(c["usage"]["completion_tokens"])
            out_first.append(reqs[0]["out"])
            in_all.append(c["usage"]["prompt_tokens"])
            in_first.append(reqs[0]["in"])
            if measured:
                total = sum(g["span"] for g in reqs)
                keep.append(api)
                first.append(api * reqs[0]["span"] / total)
                last.append(api * reqs[-1]["span"] / total)
            if len(reqs) < 2:
                continue
            n += 1
            a = reqs[0]["inp"]
            tops["placeholder name of the tool format ($...)" if isinstance(a, dict) and any(k.startswith("$") for k in a)
                 else "other wrong or missing field" if isinstance(a, dict) else "no tool call"] += 1
            found = find_answer(a)
            if found is not None:
                with_answer += 1
                identical += canon(found) == canon(c["envelope"]["structured_output"])
                same_desc += found.get("description") == c["envelope"]["structured_output"].get("description")
    m = lambda x: f"mean {st.mean(x):.2f}, median {st.median(x):.2f}"  # noqa: E731
    print(f"first calls with more than one model request and a transcript here: {n}")
    print(f"  what the first answer held: {dict(tops)}")
    print(f"  a whole answer readable inside the first answer: {with_answer}; identical to the accepted answer "
          f"(description, tags, question tags, facets, true or false): {identical}; same description: {same_desc}")
    print(f"interpreter seconds on the {len(keep)} calls with a transcript whose value is their own server time:")
    print(f"  every request: {m(keep)}")
    print(f"  the first request only: {m(first)}")
    print(f"  the last request only: {m(last)}")
    print(f"interpreter tokens on the {len(out_all)} calls with a transcript:")
    print(f"  output, every request: {m(out_all)}; the first request only: {m(out_first)}")
    print(f"  input, every request: {m(in_all)}; the first request only: {m(in_first)}")


if __name__ == "__main__":
    main()
