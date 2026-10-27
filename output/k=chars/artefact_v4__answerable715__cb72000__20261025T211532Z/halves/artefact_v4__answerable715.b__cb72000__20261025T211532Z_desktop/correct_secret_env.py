"""Write every credential a run folder's manifests copied as "<set>", as the harness writes every
secret; say exactly what was changed, never the value.

    python tools/correct_secret_env.py <run folder> [--write]

Without --write it only prints what it would change. harness.provenance.settings_env copies the
environment variables that change what a run does into run_manifest.json and names a secret
"<set>"; it took a secret by the words in its name (PASSWORD, TOKEN, KEY, SECRET), and the name of
the lane's API key, CLAUDE_API (harness.chat._API_KEY), holds none of them, so a run with that key
set copied the key itself.

Rule "secret-env/1".
  1. A value is a credential when its name is CLAUDE_API (harness.chat._API_KEY), or holds
     PASSWORD, TOKEN, KEY or SECRET and does not end in _TOKENS (a limit counted in tokens), the
     names harness.provenance.settings_env names "<set>".
  2. Every such value in run_manifest.json and eval_manifest.json that is not "<set>" becomes
     "<set>", wherever in the file it stands; no other value changes.
  3. The value as recorded is kept nowhere, since it is a credential; each change names its place,
     and the sha256 of each file before and after are kept.
  4. After the change no file of the folder holds the value; otherwise nothing is written.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "secret-env/1"
SCRIPT = "correct_secret_env.py"
HIS_WORDS = ("\"resume and finish them, make sure they are all finished, correct, complete with all data, "
             "metadata and so on\" (2026-10-26)")
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
NAMES = ("CLAUDE_API",)
WORDS = ("PASSWORD", "TOKEN", "KEY", "SECRET")
FILES = ("run_manifest.json", "eval_manifest.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def credential(name):
    """Rule 1."""
    return (isinstance(name, str) and name == name.upper()
            and (name in NAMES or (any(w in name for w in WORDS) and not name.endswith("_TOKENS"))))


def walk(value, path, found):
    """Rule 2: every credential value that is not "<set>", with its place; the value becomes "<set>"."""
    if isinstance(value, dict):
        for k in list(value):
            here = f"{path}.{k}" if path else k
            if credential(k) and isinstance(value[k], str) and value[k] not in ("<set>", ""):
                found.append((here, value[k]))
                value[k] = "<set>"
            else:
                walk(value[k], here, found)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            walk(v, f"{path}[{i}]", found)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.run)
    plans, secrets = [], set()
    for name in FILES:
        path = d / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        found = []
        walk(data, "", found)
        secrets |= {v for _, v in found}
        if found:
            text = json.dumps(data, ensure_ascii=False, indent=2)
            if b"\r\n" in raw:
                text = text.replace("\n", "\r\n")
            plans.append((path, raw, text.encode("utf-8"), [where for where, _ in found]))
    for path, _, _, places in plans:
        print(f"{d.name}/{path.name}: {len(places)} credential value(s) to write as <set>: {', '.join(places)}")
    if not plans:
        print(f"{d.name}: no credential value in {', '.join(FILES)}")
        return
    # rule 4: after the change, no file of the folder holds a value
    after = {path: new for path, _, new, _ in plans}
    holding = []
    for f in sorted(x for x in d.rglob("*") if x.is_file()):
        data = after.get(f) if f in after else f.read_bytes()
        if any(s.encode("utf-8") in data for s in secrets):
            holding.append(f.relative_to(d).as_posix())
    if holding:
        raise SystemExit(f"{d.name}: after the change these files would still hold the value: {holding}; "
                         "nothing written")
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    files, changes = {}, []
    for path, raw, new, places in plans:
        before = hashlib.sha256(raw).hexdigest()
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(new)
        tmp.replace(path)
        files[path.name] = {"sha256_before": before, "sha256_corrected": sha(path),
                            "as_recorded": None}
        changes += [{"where": path.name, "field": where, "recorded": "a credential (not kept)",
                     "corrected": "<set>"} for where in places]
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        (d / SCRIPT).write_bytes(Path(__file__).read_bytes())
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": ("The run's manifest copied the value of the lane's API key, CLAUDE_API, because "
                          "harness.provenance.settings_env took a secret only by the words in its name. The "
                          "value is now \"<set>\", as the harness writes every secret."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "The value as recorded is kept in no file: it is a credential. The files' sha256 before the "
            "change are kept.",
            "No other value of any file changes.",
        ],
        "changes": changes,
        "files": files,
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} value(s) as <set>; corrections.json, {SCRIPT}")


if __name__ == "__main__":
    main()
