"""Give each start of a run that recorded no code version (git gave no answer in the shell the start
ran in) the commit that its clone's HEAD named when the start began, by the clone's own reflog; say
exactly what was changed.

    git -c safe.directory=* reflog --date=iso-strict --format="%H|%gd|%gs" > reflog.txt   (in the clone)
    python tools/correct_code_version_from_reflog.py <run folder> <reflog.txt> [--write]

The reflog is written on the machine whose clone ran the starts, and is copied into the folder as
code_reflog.txt. Without --write it only prints what it would change and what it checked. It keeps
run_manifest.json as recorded as run_manifest.as_recorded.json on the first write of any
correction, never changed after.

Rule "code-version-reflog/1".
  1. A start (an entry of legs) is corrected when its code_version.commit is empty.
  2. Its commit is the one the clone's HEAD moved to last before the start's started_at, by the
     reflog, and its branch the one the reflog's last checkout before then moved to. dirty and
     code_state stay empty: whether the working copy differed from the commit, and how, is not
     recorded.
  3. A start that recorded its commit must be the commit rule 2 gives for it; otherwise nothing is
     written.
  4. The run's top-level code_version is its last start's, as the harness writes it.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "code-version-reflog/1"
SCRIPT = "correct_code_version_from_reflog.py"
EVIDENCE = "code_reflog.txt"
HIS_WORDS = ("\"resume and finish them, make sure they are all finished, correct, complete with all data, "
             "metadata and so on\" (2026-10-26)")
REPO = Path(__file__).resolve().parents[1]
# the arms are in prod/ and test/: FIELDS.md takes an arm's own words from its file
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]
WHEN = re.compile(r"HEAD@\{(.+)\}")
CHECKOUT = re.compile(r"^checkout: moving from \S+ to (\S+)$")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def moves(reflog):
    """(time, commit, what) of each move of HEAD, the oldest first."""
    out = []
    for line in Path(reflog).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        commit, selector, what = line.split("|", 2)
        out.append((datetime.fromisoformat(WHEN.search(selector).group(1)), commit, what))
    return sorted(out)


def at(moved, when):
    """Rule 2: the commit and branch of HEAD at a time."""
    t = datetime.fromisoformat(when)
    before = [m for m in moved if m[0] <= t]
    if not before:
        return None, None
    branch = next((CHECKOUT.match(w).group(1) for _, _, w in reversed(before) if CHECKOUT.match(w)), None)
    return before[-1][1], branch


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("reflog")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.run)
    moved = moves(args.reflog)
    path = d / "run_manifest.json"
    raw = path.read_bytes()
    man = json.loads(raw.decode("utf-8"))
    legs = man.get("legs") or []
    changes, agree, disagree = [], 0, []
    for i, leg in enumerate(legs):
        commit, branch = at(moved, leg["started_at"])
        cv = leg.get("code_version") or {}
        if cv.get("commit"):
            if cv["commit"] == commit:
                agree += 1
            else:
                disagree.append({"leg": leg.get("leg"), "recorded": cv["commit"], "reflog": commit})
            continue
        if commit is None:
            raise SystemExit(f"leg {leg.get('leg')}: the reflog has no move of HEAD before {leg['started_at']}")
        new = {"commit": commit, "branch": branch, "dirty": None}
        changes.append({"where": f"run_manifest.json legs[{i}] (leg {leg.get('leg')})", "field": "code_version",
                        "recorded": cv, "corrected": new})
        leg["code_version"] = new
    if legs and (man.get("code_version") or {}).get("commit") != legs[-1]["code_version"]["commit"]:
        changes.append({"where": "run_manifest.json", "field": "code_version",
                        "recorded": man.get("code_version"), "corrected": dict(legs[-1]["code_version"])})
        man["code_version"] = dict(legs[-1]["code_version"])
    checks = [{"what": "rule 3: each start that recorded its commit is the commit the reflog gives for it",
               "holds": not disagree, "looked_at": agree + len(disagree), **({"differs": disagree} if disagree else {})}]
    print(f"{d.name}: {len(legs)} starts; {sum(1 for c in changes if c['where'].startswith('run_manifest.json legs'))} "
          f"get a commit from the reflog")
    for c in changes:
        print(f"  {c['where']}: {c['corrected']}")
    for c in checks:
        print(f"  check {'holds' if c['holds'] else 'DOES NOT HOLD'}: {c['what']} (looked at {c['looked_at']})")
    if disagree:
        raise SystemExit("rule 3 does not hold; nothing written")
    if not changes:
        print("nothing to correct")
        return
    if not args.write:
        print("  (nothing written; --write does it)")
        return
    before = sha(path)
    kept = d / "run_manifest.as_recorded.json"
    if not kept.exists():
        shutil.copy2(path, kept)
    text = json.dumps(man, ensure_ascii=False, indent=2, default=repr)
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)
    shutil.copy2(args.reflog, d / EVIDENCE)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)
    earlier = (json.loads((d / "corrections.json").read_text(encoding="utf-8"))["corrections"]
               if (d / "corrections.json").exists() else [])
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": ("The run's starts recorded no code version: git gave no answer in the shell they ran in "
                          "on the desktop. The commit each one ran on is the one its clone's HEAD named when it "
                          "began, by the clone's own reflog."),
        "rule": {"id": RULE, "text": __doc__.split(f'Rule "{RULE}".', 1)[1].strip()},
        "not_changed_and_worth_knowing": [
            "Whether a start's working copy differed from its commit, and how, is not recorded: dirty and "
            "code_state stay empty. A start whose git answered may show that it did.",
        ],
        "changes": changes,
        "checks": checks,
        "evidence": {"file": EVIDENCE, "sha256": sha(d / EVIDENCE),
                     "what": "the clone's reflog, written on the machine that ran the starts"},
        "files": {"run_manifest.json": {"sha256_before": before, "sha256_corrected": sha(path),
                                        "as_recorded": kept.name}},
        "script": f"{SCRIPT}, in this folder",
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    from harness import fields
    fields.write(d, stamp_files=True)
    print(f"written: {len(changes)} changes; corrections.json, {EVIDENCE}, {SCRIPT}")


if __name__ == "__main__":
    main()
