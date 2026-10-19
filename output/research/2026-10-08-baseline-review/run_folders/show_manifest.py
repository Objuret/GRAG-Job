"""Print a run or eval manifest of any folder with long strings and long lists shortened.
A manifest holds no question, answer, context or gold text. A value under a key naming a
secret is printed only as whether it is the harness's mask.

    python show_manifest.py <folder name> <run_manifest.json|eval_manifest.json>
"""
import json
import sys

from folders import ALL

sys.stdout.reconfigure(encoding="utf-8")
name, fname = sys.argv[1], sys.argv[2]
assert fname in ("run_manifest.json", "eval_manifest.json")
SECRET = ("PASSWORD", "TOKEN", "KEY", "SECRET")


def short(v, key=""):
    if isinstance(v, dict):
        return {k: short(x, k) for k, x in v.items()}
    if isinstance(v, list):
        if len(v) > 8:
            return [short(x) for x in v[:3]] + [f"... {len(v)} items ..."]
        return [short(x) for x in v]
    if isinstance(v, str) and any(w in key.upper() for w in SECRET):
        return "<set>" if v == "<set>" else f"<NOT MASKED, {len(v)} chars>"
    if isinstance(v, str) and len(v) > 160:
        return f"<str {len(v)} chars> " + v[:160]
    return v


m = json.loads((ALL[name] / fname).read_text(encoding="utf-8"))
if "legs" in m and isinstance(m["legs"], list):
    for leg in m["legs"]:
        cs = leg.get("code_state") or {}
        if "untracked_sha256" in cs:
            cs["untracked_sha256"] = f"<{len(cs['untracked_sha256'])} files hashed>"
if "code_state" in m and m["code_state"]:
    m["code_state"]["untracked_sha256"] = f"<{len(m['code_state']['untracked_sha256'])} files hashed>"
print(json.dumps(short(m), indent=1, ensure_ascii=False))
