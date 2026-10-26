"""Split a question set in two for two machines, and merge the two run folders into one.

    python tools/merge_split_run.py split --set gold|10smoke|FILE [--first N] --out-dir DIR
    python tools/merge_split_run.py merge --set gold|10smoke|FILE --out DIR [--accept FILE] RUN_A RUN_B

split writes DIR/<set>.a.jsonl (the first N ids of the set, half of them when N is not given) and
DIR/<set>.b.jsonl (the rest), each line {"id": ...} with LF line ends, so the same command gives the
same bytes on any machine. Each machine runs prod/run.py with --set on one of the two files.

merge takes the two run folders made from those two files and writes one run folder:
  - it stops, and writes nothing, when the two runs differ in anything that decides what a run
    computes: the arm, the commit and how the code differed from it (every start of both runs), the
    graph as counted, the arm's index, build_stats, the character budget, the flags, the arm's
    switches, the models, the corpus and questions files (sha256), the installed packages, the
    embedder, or the scoring's settings (judge, RAGAS version, timeouts, tries, scores); and when
    the two id files are not the two halves of the set as split writes them. What a machine has of
    its own is not compared and is kept per run in merge.json (machine_facts): the build of torch,
    which follows the machine's hardware, the embedder's device, and how many judge calls a scoring
    start had in flight. A difference in how the code differed from the commit (code_state, of the
    runs or of their starts) goes through only when --accept names it in a file, {"accept": [{"path":
    "code_state" or "legs[].code_state", "why": ..., "checked": ...}]}, and is kept in merge.json
    (accepted_differences) with each run's or start's value;
  - arm_outputs, failures, eval_results, eval_calls and eval_failures in the order of the set's
    questions; each start of both runs one leg, in the order they began, numbered again, with its
    run's machine (environment) and switches (env) in it; a row's leg the new number;
  - run_manifest counted again over the whole set (n_questions, n_ran, n_failed, n_exhausted), with
    the whole set's ids sha256; a top-level field whose value differed between the two runs (the
    machine, the program path of the model lane) is left empty, and each run's value is in
    merge.json;
  - eval_manifest with every scoring start of both runs and the judge's totals added up again;
  - merge.json: what was merged, what was checked, and the sha256 of every file of both runs;
  - the two runs under halves/, byte for byte;
  - FIELDS.md, written by prod/harness/fields.py.
Nothing is sent to a model.
"""
import argparse
import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# run_manifest fields that must be the same in both runs (dotted paths)
SAME_RUN = ("arm", "generator_model", "interpreter_model", "top_k", "char_budget", "build_stats",
            "retrieval_flags", "flags", "graph", "index", "code_state", "code_version.commit",
            "code_version.branch", "inputs.questions_sha256", "inputs.corpus",
            "environment.packages", "environment.packages_all", "environment.embedder")
# flags that name a folder on each machine (the first call's store): compared by being set
PATH_FLAGS = ("HERB_V4_CACHE",)
# fields that hold a machine's own paths: compared with the user's home folder taken out
SAME_RUN_HOMED = ("generator",)
# per-machine top-level fields: kept when the two runs agree, else left empty and kept per run in
# merge.json (and per leg in the manifest's legs)
PER_MACHINE = ("questions_file", "environment", "env", "lane", "workers", "code_version")
# a scoring start's settings that belong to that start or that machine, not to how it scored; how
# many judge calls it had in flight is the machine's, like its workers
SETTINGS_OWN = ("started_at", "finished_at", "interrupted", "workers", "argv", "pid",
                "python_executable", "wall_s", "embedding", "cells", "judge_inflight")
# a machine's own, not compared and kept per run in merge.json: torch's build follows its hardware
# (the CPU or a graphics card), and so does the device the embedder runs on (his 2026-10-22 "i want
# to do this on both the laptop and desktop every fucking time"; his 2026-10-25 "i keep fucking
# trying to force you to do thegoddamn vectors on the GPU!")
MACHINE_PACKAGES = ("torch",)
MACHINE_EMBEDDER = ("device",)
# the differences --accept can let through, each with why and what was checked
ACCEPTABLE = ("code_state", "legs[].code_state")


def _without_machine(path, value):
    """A compared field with a machine's own facts taken out (MACHINE_PACKAGES, MACHINE_EMBEDDER)."""
    if path == "environment.packages" and isinstance(value, dict):
        return {k: v for k, v in value.items() if k not in MACHINE_PACKAGES}
    if path == "environment.packages_all" and isinstance(value, list):
        return [p for p in value if str(p).split("==")[0].lower() not in MACHINE_PACKAGES]
    if path == "environment.embedder" and isinstance(value, dict):
        return {k: v for k, v in value.items() if k not in MACHINE_EMBEDDER}
    return value


def _ids_file(qset):
    if qset == "gold":
        return REPO / "data" / "gold100.jsonl"
    if qset == "10smoke":
        return REPO / "data" / "10smoke.jsonl"
    return Path(qset)


def _read_ids(path):
    ids = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                ids.append(json.loads(line)["id"])
            except (ValueError, KeyError, TypeError) as e:
                raise SystemExit(f"{path} line {n}: not a JSON object with an 'id'") from e
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{path} names a question twice")
    return ids


def _ids_bytes(ids):
    return "".join(json.dumps({"id": i}, ensure_ascii=False) + "\n" for i in ids).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _file_sha(path):
    return _sha(Path(path).read_bytes())


def split(args):
    whole = _ids_file(args.qset)
    ids = _read_ids(whole)
    first = len(ids) // 2 if args.first is None else args.first
    if not 0 < first < len(ids):
        raise SystemExit(f"--first must be between 1 and {len(ids) - 1}")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for tag, part in (("a", ids[:first]), ("b", ids[first:])):
        path = out / f"{whole.stem}.{tag}.jsonl"
        data = _ids_bytes(part)
        if path.is_file() and path.read_bytes() != data:
            raise SystemExit(f"{path} is there and holds other ids; nothing written")
        path.write_bytes(data)
        print(f"{path}  {len(part)} questions  sha256 {_sha(data)}")
    print(f"whole set {whole}  {len(ids)} questions  sha256 {_file_sha(whole)}")


def _get(d, dotted):
    for key in dotted.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def _run_code(state):
    """A code state as the run sees it: the changed and untracked files under prod/ and test/,
    the code a run loads; a file outside them (a tool, a document) does not change the run, so a
    state whose changes all lie outside them counts as clean (its diff hash is of all files)."""
    if not isinstance(state, dict):
        return state
    loaded = sorted(e for e in state.get("status") or []
                    if e[3:].replace("\\", "/").startswith(("prod/", "test/")))
    return state if loaded else {"status": []}


def _homeless(value, home):
    """The value with the machine's home folder written as ~, at any depth."""
    if isinstance(value, dict):
        return {k: _homeless(v, home) for k, v in value.items()}
    if isinstance(value, list):
        return [_homeless(v, home) for v in value]
    if isinstance(value, str) and home:
        for h in {home, home.replace("\\", "/")}:
            if h and value.lower().startswith(h.lower()):
                return "~" + value[len(h):].replace("\\", "/")
    return value


def _home_of(manifest):
    """The home folder of the machine a run ran on, read off its lane's config folder."""
    cfg = ((manifest.get("lane") or {}).get("env_set") or {}).get("CLAUDE_CONFIG_DIR")
    if not cfg:
        for leg in manifest.get("legs") or []:
            cfg = ((leg.get("lane") or {}).get("env_set") or {}).get("CLAUDE_CONFIG_DIR")
            if cfg:
                break
    return str(Path(cfg).parent) if cfg else None


def _scoring_settings(settings, home):
    """A scoring start's settings with what belongs to that start or machine taken out: what is
    left decides how it scored."""
    s = {k: v for k, v in (settings or {}).items() if k not in SETTINGS_OWN}
    lane = dict(s.get("lane") or {})
    for k in ("exe", "cwd"):
        lane.pop(k, None)
    if s.get("lane") is not None:
        s["lane"] = lane
    return _homeless(s, home)


def _jsonl(path):
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _write_jsonl(path, records):
    with Path(path).open("w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _usage_sum(entries, names):
    total = {n: 0 for n in names}
    for u in entries:
        for n in names:
            total[n] += (u or {}).get(n) or 0
    return total


def _added(parts):
    """The scoring starts' counts added key by key; a value that is not a number is kept when the
    starts agree and left empty when they do not."""
    parts = [p for p in parts if p]
    if not parts:
        return None
    out = {}
    for key in dict.fromkeys(k for p in parts for k in p):
        values = [p.get(key) for p in parts]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            out[key] = sum(values)
        else:
            out[key] = values[0] if all(v == values[0] for v in values) else None
    return out


def _merged_settings(settings):
    """The merged run's scoring settings: what the starts share, the first start and the last end,
    and their counts added; what each start has of its own and cannot be added is left empty here
    and stays in judge_legs[].settings. Returns the settings and the fields left empty."""
    settings = [s for s in settings if s]
    if not settings:
        return None, []
    out = dict(settings[-1])
    starts = [s["started_at"] for s in settings if s.get("started_at")]
    ends = [s["finished_at"] for s in settings if s.get("finished_at")]
    out["started_at"] = min(starts) if starts else None
    out["finished_at"] = max(ends) if ends else None
    out["interrupted"] = any(s.get("interrupted") for s in settings)
    out["embedding"] = _added([s.get("embedding") for s in settings])
    out["cells"] = _added([s.get("cells") for s in settings])
    empty = [k for k in SETTINGS_OWN
             if k not in ("started_at", "finished_at", "interrupted", "embedding", "cells")]
    for k in empty:
        out[k] = None
    return out, empty


class Run:
    def __init__(self, folder):
        self.dir = Path(folder)
        if not (self.dir / "run_manifest.json").is_file():
            raise SystemExit(f"{self.dir}: no run_manifest.json")
        if (self.dir / ".run.lock").exists():
            raise SystemExit(f"{self.dir}: a run is still writing into it (.run.lock)")
        self.name = self.dir.name
        self.manifest = json.loads((self.dir / "run_manifest.json").read_text(encoding="utf-8"))
        ev = self.dir / "eval_manifest.json"
        self.eval = json.loads(ev.read_text(encoding="utf-8")) if ev.is_file() else None
        self.rows = _jsonl(self.dir / "arm_outputs.jsonl")
        self.failures = _jsonl(self.dir / "failures.jsonl")
        self.results = _jsonl(self.dir / "eval_results.jsonl")
        self.calls = _jsonl(self.dir / "eval_calls.jsonl")
        self.eval_failures = _jsonl(self.dir / "eval_failures.jsonl")
        self.home = _home_of(self.manifest)
        self.files = {p.relative_to(self.dir).as_posix(): _file_sha(p)
                      for p in sorted(self.dir.rglob("*")) if p.is_file()}

    def judge_legs(self):
        ev = self.eval or {}
        legs = list(ev.get("judge_legs") or [])
        if not legs and (ev.get("judge_usage") or ev.get("judge_elapsed_s")):
            legs.append({"timestamp": ev.get("timestamp"), "judge_model": ev.get("judge_model"),
                         "judge_backend": ev.get("judge_backend"), "usage": ev.get("judge_usage"),
                         "elapsed_s": ev.get("judge_elapsed_s"),
                         "settings": ev.get("judge_settings")})
        return legs


def merge(args):
    sys.path.insert(0, str(REPO / "prod"))
    sys.path.insert(0, str(REPO / "test"))
    from harness import fields
    from harness.contract import ModelUsage

    whole_file = _ids_file(args.qset)
    ids = _read_ids(whole_file)
    at = {i: n for n, i in enumerate(ids)}
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is there and not empty; nothing written")
    runs = [Run(args.run_a), Run(args.run_b)]
    if runs[0].dir.resolve() == runs[1].dir.resolve():
        raise SystemExit("the two runs are one folder")
    problems = []
    accept, accepted = {}, []
    if args.accept:
        for a in json.loads(Path(args.accept).read_text(encoding="utf-8")).get("accept") or []:
            if a.get("path") not in ACCEPTABLE or not a.get("why") or not a.get("checked"):
                raise SystemExit(f"{args.accept}: an entry must name one of {ACCEPTABLE} as path, with "
                                 "why and checked; nothing written")
            accept[a["path"]] = a

    # the two id files must be the two halves of the set, as split writes them
    shas = [_get(r.manifest, "inputs.ids_sha256") for r in runs]
    cut = None
    for n in range(1, len(ids)):
        a, b = _sha(_ids_bytes(ids[:n])), _sha(_ids_bytes(ids[n:]))
        if shas == [a, b]:
            cut = n
        elif shas == [b, a]:
            cut = n
            runs.reverse()
        if cut:
            break
    if cut is None:
        raise SystemExit(f"the two runs' id files (inputs.ids_sha256 {shas}) are not the two "
                         f"halves of {whole_file} as `split` writes them; nothing written")
    halves = (ids[:cut], ids[cut:])
    for r, half in zip(runs, halves):
        mine = set(half)
        for what, recs, key in (("arm_outputs", r.rows, "id"), ("failures", r.failures, "id"),
                                ("eval_results", r.results, "question_id"),
                                ("eval_failures", r.eval_failures, "question_id")):
            stray = sorted({x.get(key) for x in recs} - mine)
            if stray:
                problems.append(f"{r.name}: {what} names {len(stray)} question(s) outside its half")
        stray = sorted({c.get("question_id") for c in r.calls} - mine - {None})
        if stray:
            problems.append(f"{r.name}: eval_calls names {len(stray)} question(s) outside its half")
        if len({x["id"] for x in r.rows}) != len(r.rows):
            problems.append(f"{r.name}: a question has more than one answer row")

    # what decides what a run computes must be the same in both
    checked = []
    for path in SAME_RUN:
        va, vb = (_get(r.manifest, path) for r in runs)
        if path == "code_state":
            va, vb = (_run_code(x) for x in (va, vb))
            checked.append("code_state (files the run loads: prod/, test/)")
            if va != vb and path in accept:
                accepted.append({"path": path, "why": accept[path]["why"],
                                 "checked": accept[path]["checked"],
                                 "values": {r.name: _get(r.manifest, path) for r in runs}})
                continue
        elif path in ("environment.packages", "environment.packages_all", "environment.embedder"):
            va, vb = (_without_machine(path, x) for x in (va, vb))
            checked.append(path + " (but " + ", ".join(
                MACHINE_EMBEDDER if path.endswith("embedder") else MACHINE_PACKAGES) + ")")
        elif path == "flags":
            # a flag that names a folder on the machine: the same flag set on both, its path kept
            # per run; the folder's content is the operator's to check before the merge
            va, vb = ({k: (v if k not in PATH_FLAGS else "<path>") for k, v in (x or {}).items()}
                      for x in (va, vb))
            checked.append("flags (" + ", ".join(
                f"{k}: " + " | ".join(str((_get(r.manifest, "flags") or {}).get(k)) for r in runs)
                for k in PATH_FLAGS) + ")")
        else:
            checked.append(path)
        if va != vb:
            problems.append(f"run_manifest {path} differs")
    for path in SAME_RUN_HOMED:
        va, vb = (_homeless(_get(r.manifest, path), r.home) for r in runs)
        checked.append(path + " (home folder taken out)")
        if va != vb:
            problems.append(f"run_manifest {path} differs")
    census = _get(runs[0].manifest, "graph.census_sha256")
    if runs[0].manifest.get("graph") is not None and not census:
        problems.append("the graph was not counted (graph.census_sha256 is empty)")
    first_leg = runs[0].manifest["legs"][0]
    let_through = []
    for r in runs:
        for leg in r.manifest.get("legs") or []:
            commit_differs = _get(leg, "code_version.commit") != _get(first_leg, "code_version.commit")
            state_differs = _run_code(leg.get("code_state")) != _run_code(first_leg.get("code_state"))
            # a start rebuilt from its log holds no code version: its state is the one let through
            rebuilt = leg.get("from_its_log") is not None and leg.get("code_version") is None
            if state_differs and "legs[].code_state" in accept and (rebuilt or not commit_differs):
                let_through.append({"run": r.name, "leg": leg.get("leg"),
                                    "code_state": leg.get("code_state")})
            elif commit_differs or state_differs:
                problems.append(f"{r.name} leg {leg.get('leg')}: the code differs from the first "
                                "start's")
    if let_through:
        a = accept["legs[].code_state"]
        accepted.append({"path": "legs[].code_state", "why": a["why"], "checked": a["checked"],
                         "values": let_through})
    checked.append("legs[].code_version.commit, legs[].code_state")

    # the scoring
    judged = [r.eval is not None for r in runs]
    if any(judged) and not all(judged):
        problems.append("one run was scored and the other was not")
    if all(judged):
        for key in ("scorer", "arm", "judge_model", "judge_backend", "judge_effort"):
            if runs[0].eval.get(key) != runs[1].eval.get(key):
                problems.append(f"eval_manifest {key} differs")
            checked.append(f"eval_manifest.{key}")
        ref = None
        for r in runs:
            for leg in r.judge_legs():
                s = _scoring_settings(leg.get("settings"), r.home)
                if ref is None:
                    ref = s
                elif s != ref:
                    diff = sorted(k for k in set(s) | set(ref) if s.get(k) != ref.get(k))
                    problems.append(f"{r.name}: a scoring start ran under other settings: {diff}")
        checked.append("judge_legs[].settings (all but " + ", ".join(SETTINGS_OWN)
                       + ", lane.exe, lane.cwd; home folder taken out)")
    if problems:
        raise SystemExit("the two runs cannot be merged; nothing written:\n  "
                         + "\n  ".join(problems))

    # the legs of both runs, in the order they began
    legs = []
    for r in runs:
        for leg in r.manifest.get("legs") or []:
            legs.append((leg.get("started_at") or "", r, leg))
    legs.sort(key=lambda x: x[0])
    renumber, new_legs = {}, []
    for n, (_, r, leg) in enumerate(legs, 1):
        renumber[(r.name, leg.get("leg"))] = n
        entry = dict(leg)
        entry.update(leg=n, source_run=r.name, source_leg=leg.get("leg"),
                     environment=r.manifest.get("environment"), env=r.manifest.get("env"))
        new_legs.append(entry)

    def relegged(rec, r):
        rec = dict(rec)
        if rec.get("leg") is not None:
            rec["leg"] = renumber[(r.name, rec["leg"])]
        return rec

    def ordered(recs_by_run, key):
        # the set's order; within one question, the order the run wrote them in
        tagged = [(at.get(rec.get(key), -1), n, i, rec)
                  for n, (r, recs) in enumerate(recs_by_run) for i, rec in enumerate(recs)]
        tagged.sort(key=lambda x: (x[0], x[1], x[2]))
        return [x[3] for x in tagged]

    rows = ordered([(r, [relegged(x, r) for x in r.rows]) for r in runs], "id")
    failures = ordered([(r, [relegged(x, r) for x in r.failures]) for r in runs], "id")
    results = ordered([(r, r.results) for r in runs], "question_id")
    eval_failures = ordered([(r, r.eval_failures) for r in runs], "question_id")
    # the embeddings made once before the cells (no question) first, by start
    prime = sorted(((c.get("eval_leg") or "", n, i, c) for n, r in enumerate(runs)
                    for i, c in enumerate(r.calls) if c.get("question_id") is None),
                   key=lambda x: x[:3])
    calls = [x[3] for x in prime] + ordered(
        [(r, [c for c in r.calls if c.get("question_id") is not None]) for r in runs],
        "question_id")

    now = datetime.now(timezone.utc).isoformat()
    man = copy.deepcopy(runs[0].manifest)
    left_empty = []
    for key in PER_MACHINE:
        va, vb = (r.manifest.get(key) for r in runs)
        if va != vb:
            man[key] = None
            left_empty.append(key)
    answered = {x["id"] for x in rows}
    man.update(
        n_questions=len(ids), n_ran=len(answered), n_failed=len(ids) - len(answered),
        n_exhausted=(None if man.get("char_budget") is None else sum(
            1 for x in rows if ((x.get("meta") or {}).get("char_budget") or {}).get("exhausted"))),
        timestamp=now, legs=new_legs)
    man["inputs"] = dict(man.get("inputs") or {}, ids_sha256=_file_sha(whole_file))

    ev, settings_left_empty = None, []
    if all(judged):
        jlegs = []
        for r in runs:
            for leg in r.judge_legs():
                jlegs.append(dict(leg, source_run=r.name))
        jlegs.sort(key=lambda x: ((x.get("settings") or {}).get("started_at")
                                  or x.get("timestamp") or ""))
        names = list(ModelUsage.__dataclass_fields__)
        ev = copy.deepcopy(runs[0].eval)
        # the merged settings are both starts' (the last start's settings alone were read as the
        # whole scoring's time and embedding count)
        settings, settings_left_empty = (_merged_settings([x.get("settings") for x in jlegs]) if jlegs
                                         else (ev.get("judge_settings"), []))
        ev.update(source_run=str(out), timestamp=now, judge_legs=jlegs,
                  judge_usage=_usage_sum([x.get("usage") for x in jlegs], names),
                  judge_elapsed_s=sum(float(x.get("elapsed_s") or 0.0) for x in jlegs),
                  judge_settings=settings)
        named = [x.get("judge_model") for x in jlegs if x.get("judge_model")]
        if named:
            ev["judge_model"] = named[-1]

    record = {
        "merged_at": now,
        "tool": "tools/merge_split_run.py",
        "tool_sha256": _sha(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "argv": list(sys.argv),
        "whole_set": {"file": str(whole_file), "sha256": _file_sha(whole_file),
                      "n_questions": len(ids)},
        "split_after": cut,
        "checked_equal": checked,
        "machine_facts": {r.name: {
            "host": _get(r.manifest, "environment.host"),
            **{p: (_get(r.manifest, "environment.packages") or {}).get(p) for p in MACHINE_PACKAGES},
            **{f"embedder_{k}": (_get(r.manifest, "environment.embedder") or {}).get(k)
               for k in MACHINE_EMBEDDER},
            "judge_inflight": sorted({(leg.get("settings") or {}).get("judge_inflight")
                                      for leg in r.judge_legs()} - {None}),
        } for r in runs},
        "accepted_differences": accepted,
        "left_empty": left_empty,
        "judge_settings_left_empty": settings_left_empty,
        "sources": [{
            "name": r.name, "path": str(r.dir.resolve()), "half": tag,
            "n_questions": len(half), "ids_sha256": _get(r.manifest, "inputs.ids_sha256"),
            "host": _get(r.manifest, "environment.host"),
            "n_rows": len(r.rows), "n_failure_lines": len(r.failures),
            "n_score_rows": len(r.results), "n_eval_calls": len(r.calls),
            "n_eval_failure_lines": len(r.eval_failures),
            "legs": [{"source_leg": leg.get("leg"), "leg": renumber[(r.name, leg.get("leg"))]}
                     for leg in r.manifest.get("legs") or []],
            "manifest_values": {k: r.manifest.get(k) for k in left_empty},
            "files_sha256": r.files,
        } for r, tag, half in zip(runs, ("a", "b"), halves)],
        "kept_raw": "halves/<name>/, every file byte for byte as its run wrote it",
    }

    out.mkdir(parents=True, exist_ok=True)
    for r in runs:
        dest = out / "halves" / r.name
        shutil.copytree(r.dir, dest)
        copied = {p.relative_to(dest).as_posix(): _file_sha(p)
                  for p in sorted(dest.rglob("*")) if p.is_file()}
        if copied != r.files:
            raise SystemExit(f"the copy of {r.name} under halves/ is not byte for byte its run")
    _write_jsonl(out / "arm_outputs.jsonl", rows)
    _write_jsonl(out / "failures.jsonl", failures)
    for r in runs:
        for diff in sorted(r.dir.glob("code.*.diff")):
            if not (out / diff.name).is_file():
                shutil.copyfile(diff, out / diff.name)
    (out / "run_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2),
                                           encoding="utf-8", newline="\n")
    if ev is not None:
        _write_jsonl(out / "eval_results.jsonl", results)
        _write_jsonl(out / "eval_calls.jsonl", calls)
        _write_jsonl(out / "eval_failures.jsonl", eval_failures)
        (out / "eval_manifest.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2),
                                                encoding="utf-8", newline="\n")
    (out / "merge.json").write_text(json.dumps(record, ensure_ascii=False, indent=2),
                                    encoding="utf-8", newline="\n")
    fields.write(out)

    print(f"merged {runs[0].name} ({len(runs[0].rows)} rows, {runs[0].manifest['environment']['host']})"
          f" + {runs[1].name} ({len(runs[1].rows)} rows, {runs[1].manifest['environment']['host']})"
          f"\n  -> {out}")
    print(f"{man['n_ran']}/{man['n_questions']} answered, {man['n_failed']} without a row; "
          f"{len(new_legs)} legs; {len(results)} score rows; {len(calls)} eval calls; "
          f"left empty (differed): {', '.join(left_empty) or 'none'}")
    if ev is not None:
        u = ev["judge_usage"]
        print(f"judge: {u['calls']} calls, in={u['tokens_in']} out={u['tokens_out']} tokens over "
              f"{len(ev['judge_legs'])} scoring starts")
    gaps = fields.undescribed(out)
    for g in gaps:
        print("  no word for:", g)
    bad = 0
    for text, ok, detail in fields.relations(out):
        bad += not ok
        print(f"  [{'ok' if ok else 'NO'}] {text} | {detail}")
    if gaps or bad:
        raise SystemExit(f"FIELDS.md written; {len(gaps)} field(s) without a word, {bad} check(s) "
                         "that do not hold")


def main():
    p = argparse.ArgumentParser(prog="merge_split_run.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split", help="write the two id files of a set")
    s.add_argument("--set", dest="qset", required=True, metavar="gold|10smoke|FILE")
    s.add_argument("--first", type=int, default=None, metavar="N",
                   help="how many questions the first file gets (default: half)")
    s.add_argument("--out-dir", required=True, metavar="DIR")
    m = sub.add_parser("merge", help="merge two run folders into one")
    m.add_argument("--set", dest="qset", required=True, metavar="gold|10smoke|FILE",
                   help="the whole set the two id files were split from")
    m.add_argument("--out", required=True, metavar="DIR", help="the merged folder (new)")
    m.add_argument("--accept", default=None, metavar="FILE",
                   help="the code differences to let through, each with why and what was checked")
    m.add_argument("run_a", metavar="RUN_A")
    m.add_argument("run_b", metavar="RUN_B")
    args = p.parse_args()
    split(args) if args.cmd == "split" else merge(args)


if __name__ == "__main__":
    main()
