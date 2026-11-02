"""Join each arm's runs over the hundred and the 715 into one folder of the 815, and keep every run of the arm
inside that folder as recorded (his 2026-10-31 "why the fuck are you separating them AFTER the run!?"; his
"Yep", 2026-11-01, to: each arm gets one folder for the 815, each run kept inside it as recorded, as with the
artefact's split run, and the workbook made again from these folders the same, cell for cell).

    python tools/merge_runs.py            checks every join and move and prints them; writes nothing
    python tools/merge_runs.py --write    writes data/answerable815.jsonl and the arms' folders, then moves
                                          the runs into them

An arm's folder, output/k=chars/<arm>__answerable815__cb72000/ (PLAN):
  - its top: the arm's final runs on the hundred and on the 715 joined into one run of the 815, with the
    hundred's re-judging (factual_correctness and context_entity_recall, judged after the run on its answers
    by prod/run.py --rejudge) joined to the hundred's run;
  - parts/: those runs and the re-judging, each moved whole;
  - runs_without_answers/: each pair of the arm's runs without answers, one over the hundred and one over the
    715, joined the same way into one run of the 815 named by its kind (runs_without_answers/<kind>/), with
    its two runs under its own parts/; the pair of first_question_warm runs, two questions each, is moved
    whole, not joined;
  - redo/: the run that answered and judged again the questions now handed other texts, moved whole;
  - sources/ (the artefact): the run whose stored first calls its run on the hundred read, and the run that
    embedded the 715's query texts in one pass, moved whole.

A join:
  1. The runs' questions do not overlap and together are the 815 of data/answerable815.jsonl (HERB's
     answerable questions in its questions file's order); each run answered every question of its set and
     each of its records names only its own questions.
  2. MUST_EQUAL, and every field of inputs but ids_sha256, must be the same in every run, and EVAL_EQUAL in
     every scoring, a re-judging's included; the join stops and writes nothing when one differs. Every other
     top-level field that differs is left empty at the top, each run's value in merge.json
     (sources[].manifest_values, sources[].eval_values).
  3. arm_outputs, failures, eval_results, eval_calls and eval_failures: each run's lines in the order the run
     wrote them, the runs in PLAN's order (the hundred's first), a re-judging's lines after its run's. A row's
     leg is its start's new number; every other line is the run's, byte for byte, its line end LF.
  4. A re-judging: its answers must be its run's, its lines of the run's other scores the run's, its calls and
     its failures only of its two scores and the run's questions, and the run must hold neither score; only
     its two scores' lines of eval_results are joined, and all its calls and failures.
  5. run_manifest: the first run's, with the starts of every run in the order they began, numbered again, each
     with its run (source_run, source_leg), machine (environment) and switches (env); n_questions, n_ran,
     n_failed and n_exhausted counted again; inputs.ids_sha256 that of data/answerable815.jsonl.
  6. eval_manifest: the first run's, with every scoring start of every run, a re-judging's included, in the
     order they began, each with its run (source_run); judge_usage and judge_elapsed_s added again;
     judge_settings what every start holds the same, started_at the first start, finished_at the last end,
     interrupted whether any start was, embedding and cells added, and a field the starts differ in left
     empty (each start's own value stays in judge_legs[].settings).
  7. judge_calls_without_record.json and code.*.diff: copied from the run that has them.
  8. merge.json: what was joined and checked, the sha256 of every file of every run as it stood before, and
     (in the arm's folder) every folder moved into the arm's folder, its path before and after; FIELDS.md by
     prod/harness/fields.py. A relation of fields.relations that fails in the joined folder must fail in one
     of its runs too.
Nothing is moved until every join of every arm is written and checked; a check that fails removes the new
folders and moves nothing. A move renames the folder whole and checks every file is there with its size after
it. A record inside a run that names another run's folder (model_call_times*.json, delivered_vs_final.json, a
relative path in corrections.json, merge.json) stays as recorded; the arm's merge.json says where each folder
went. No model call.
"""
import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
K = REPO / "output" / "k=chars"
sys.path[:0] = [str(REPO / "prod"), str(REPO / "test")]

SET_NAME = "answerable815"
SET_FILE = REPO / "data" / f"{SET_NAME}.jsonl"
QUESTIONS = REPO / "data" / "questions.jsonl"
# the sets the runs were given: a run's manifest names its file by the file's sha256 (inputs.ids_sha256)
PART_SETS = (REPO / "data" / "gold100.jsonl", REPO / "data" / "answerable715.jsonl")
REJUDGED_SCORES = ("factual_correctness", "context_entity_recall")
REJUDGED = "__j-claude-haiku-4-5-20251001__gold100"
# what decides what the joined lines are; inputs too, but ids_sha256
MUST_EQUAL = ("arm", "generator_model", "interpreter_model", "top_k", "char_budget", "graph")
EVAL_EQUAL = ("scorer", "arm", "judge_model", "judge_backend", "judge_effort")
# counted again over the 815, or made of every run's
COUNTED = ("n_questions", "n_ran", "n_failed", "n_exhausted", "timestamp", "legs", "inputs")
EVAL_COUNTED = ("judge_legs", "judge_usage", "judge_elapsed_s", "judge_settings", "source_run", "timestamp")
SETTINGS_ADDED = ("embedding", "cells")


def final(hundred, the715):
    return [(hundred, hundred + REJUDGED), (the715, None)]


def pair(prefix, kind, day):
    return [(f"{prefix}__gold100__cb72000__{day}_{kind}", None), (f"{prefix}__answerable715__cb72000__{day}_{kind}", None)]


def without_answers(prefix, kinds):
    # a joined pair is named by its kind alone: the arm's folder names the arm and the set, and a path on
    # Windows must stay under 260 characters for git
    return {kind: pair(prefix, kind, day) for kind, day in kinds}


def warm(prefix):
    return [f"{prefix}__gold100__cb72000__20261028_first_question_warm",
            f"{prefix}__answerable715__cb72000__20261028_first_question_warm"]


KINDS = (("metadata_search_alone", "20261031"), ("metadata_retrieval", "20261031"), ("search_1worker", "20261027"))
PLAN = {
    f"lucene__{SET_NAME}__cb72000": {
        "join": final("lucene__gold100__cb72000__20261008T234209Z", "lucene__answerable715__cb72000__20261023T112745Z"),
        "runs_without_answers": without_answers("lucene", KINDS),
        "moved": {"runs_without_answers": warm("lucene"), "redo": ["lucene__metadata_redo__cb72000__20261031"]},
    },
    f"vector__{SET_NAME}__cb72000": {
        "join": final("vector__gold100__cb72000__20261017T061242Z", "vector__answerable715__cb72000__20261024T004317Z"),
        "runs_without_answers": without_answers("vector", KINDS),
        "moved": {"runs_without_answers": warm("vector"), "redo": ["vector__metadata_redo__cb72000__20261031"]},
    },
    f"artefact_v4__{SET_NAME}__cb72000": {
        "join": final("artefact_v4__gold100__cb72000__20261023T021439Z",
                      "artefact_v4__answerable715__cb72000__20261025T211532Z"),
        "runs_without_answers": without_answers("artefact_v4", KINDS + (("metadata_edges_retrieval", "20261031"),)),
        "moved": {"runs_without_answers": warm("artefact_v4"), "redo": ["artefact_v4__metadata_redo__cb72000__20261031"],
                  "sources": ["artefact_v4__gold100__cb72000__20261020T041923Z",
                              "artefact_v4__answerable715__cb72000__20261027_query_embeddings"]},
    },
    f"gold_evidence__{SET_NAME}__cb72000": {
        "join": [("gold_evidence__gold100__cb72000__20261031", None), ("gold_evidence__answerable715__cb72000__20261031", None)],
        "runs_without_answers": {},
        "moved": {},
    },
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lines(path):
    """A JSON-lines file's lines, each with an LF line end; none when the file is not there."""
    p = Path(path)
    if not p.is_file():
        return
    with p.open("rb") as fh:
        for raw in fh:
            if raw.strip():
                yield raw.rstrip(b"\r\n") + b"\n"


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def files_of(d):
    return {p.relative_to(d).as_posix(): p for p in sorted(Path(d).rglob("*")) if p.is_file()}


def ids_in(path):
    return [json.loads(x)["id"] for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def ids_bytes(ids):
    return "".join(json.dumps({"id": i}, ensure_ascii=False) + "\n" for i in ids).encode("utf-8")


def rel(path):
    return Path(path).relative_to(REPO).as_posix()


def added(parts):
    """Counts added key by key; a value that is not a number is kept when all agree and left empty when not."""
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


def shared_settings(settings):
    """The joined scoring's settings (rule 6) and the fields left empty."""
    settings = [s for s in settings if s]
    if not settings:
        return None, []
    out, empty = {}, []
    for key in dict.fromkeys(k for s in settings for k in s):
        values = [s.get(key) for s in settings]
        if key == "started_at":
            out[key] = min(v for v in values if v) if any(values) else None
        elif key == "finished_at":
            out[key] = max(v for v in values if v) if any(values) else None
        elif key == "interrupted":
            out[key] = any(values)
        elif key in SETTINGS_ADDED:
            out[key] = added(values)
        elif all(key in s for s in settings) and all(v == values[0] for v in values):
            out[key] = values[0]
        else:
            out[key] = None
            empty.append(key)
    return out, empty


def whole_set():
    """The 815: HERB's answerable questions in its questions file's order, each in one of the runs' sets."""
    answerable = [i for i in ids_in(QUESTIONS) if "::a::" in i]
    every = [i for p in PART_SETS for i in ids_in(p)]
    if len(answerable) != len(set(answerable)) or sorted(every) != sorted(answerable):
        sys.exit(f"{[rel(p) for p in PART_SETS]} are not HERB's answerable questions, each once")
    return answerable


class Run:
    """A run to join, as it stands before the join, and the re-judging of its answers, if any."""

    def __init__(self, name, rejudged=None):
        self.name, self.dir = name, K / name
        if not (self.dir / "run_manifest.json").is_file() or (self.dir / ".run.lock").exists():
            sys.exit(f"{name}: no run_manifest.json, or a run is still writing into it")
        self.manifest = read(self.dir / "run_manifest.json")
        self.eval = read(self.dir / "eval_manifest.json") if (self.dir / "eval_manifest.json").is_file() else None
        self.re = K / rejudged if rejudged else None
        if self.re is not None and not (self.re / "eval_manifest.json").is_file():
            sys.exit(f"{rejudged}: no eval_manifest.json")
        self.re_eval = read(self.re / "eval_manifest.json") if self.re else None
        by_sha = {sha_file(p): p for p in PART_SETS}
        self.set_file = by_sha.get(self.manifest["inputs"]["ids_sha256"])
        if self.set_file is None:
            sys.exit(f"{name}: its ids file is none of {[rel(p) for p in PART_SETS]}")
        self.ids = ids_in(self.set_file)
        self.files = {k: sha_file(p) for k, p in files_of(self.dir).items()}
        self.re_files = {k: sha_file(p) for k, p in files_of(self.re).items()} if self.re else None
        self.counts = {}


def check(run, problems):
    """Rules 1 and 4 for one run; counts its lines."""
    mine = set(run.ids)
    rows, exhausted, answers = [], 0, {}
    for raw in lines(run.dir / "arm_outputs.jsonl"):
        r = json.loads(raw)
        rows.append(r["id"])
        exhausted += bool(((r.get("meta") or {}).get("char_budget") or {}).get("exhausted"))
        if run.re is not None:
            answers[r["id"]] = (r["question"], r["answer"], r["contexts"], r["context_ids"])
    if sorted(rows) != sorted(mine):
        problems.append(f"{run.name}: its answer rows are not the questions of {rel(run.set_file)}, each once")
    m = run.manifest
    if (m["n_questions"], m["n_ran"], m["n_failed"]) != (len(mine), len(mine), 0):
        problems.append(f"{run.name}: not every question of its set was answered")
    n = {"n_rows": len(rows), "exhausted": exhausted}
    for what, file, key in (("n_failure_lines", "failures.jsonl", "id"), ("n_score_rows", "eval_results.jsonl", "question_id"),
                            ("n_eval_calls", "eval_calls.jsonl", "question_id"),
                            ("n_eval_failure_lines", "eval_failures.jsonl", "question_id")):
        n[what] = 0
        for raw in lines(run.dir / file):
            n[what] += 1
            q = json.loads(raw).get(key)
            if q is not None and q not in mine:
                problems.append(f"{run.name}: {file} names a question outside its set")
                break
    run.counts = n
    if run.re is None:
        return
    cells = {}
    for raw in lines(run.dir / "eval_results.jsonl"):
        r = json.loads(raw)
        cells[(r["question_id"], r["metric"])] = r
    if any(m_ in REJUDGED_SCORES for _, m_ in cells):
        problems.append(f"{run.name}: it judged {REJUDGED_SCORES} itself, and {run.re.name} judged them again")
    judged = {}
    for raw in lines(run.re / "arm_outputs.jsonl"):
        r = json.loads(raw)
        judged[r["id"]] = (r["question"], r["answer"], r["contexts"], r["context_ids"])
    if judged != answers:
        problems.append(f"{run.re.name}: it judged other answers than {run.name}'s")
    re = {"n_score_rows": 0, "n_eval_calls": 0, "n_eval_failure_lines": 0}
    for raw in lines(run.re / "eval_results.jsonl"):
        r = json.loads(raw)
        if r["metric"] in REJUDGED_SCORES:
            re["n_score_rows"] += 1
        elif r != cells.get((r["question_id"], r["metric"])):
            problems.append(f"{run.re.name}: a line of {r['metric']} is not {run.name}'s")
            break
    for what, file, key in (("n_eval_calls", "eval_calls.jsonl", "score"), ("n_eval_failure_lines", "eval_failures.jsonl", "metric")):
        for raw in lines(run.re / file):
            re[what] += 1
            r = json.loads(raw)
            if r.get(key) not in REJUDGED_SCORES or r.get("question_id") not in mine:
                problems.append(f"{run.re.name}: {file} holds a line of another score or question")
                break
    run.re_counts = re


class Join:
    """One run of the 815 made of the runs over its parts (rules 1 to 7), checked and made, not yet written."""

    def __init__(self, out, runs, whole, now):
        self.out, self.runs, self.whole, self.now = out, runs, whole, now
        problems = []
        sets = [set(r.ids) for r in runs]
        if sum(len(s) for s in sets) != len(set().union(*sets)) or set().union(*sets) != set(whole):
            problems.append("the runs' sets overlap, or together are not the 815")
        for r in runs:
            check(r, problems)
        self.checked = list(MUST_EQUAL) + ["inputs (but ids_sha256)"]
        for key in MUST_EQUAL:
            if any(r.manifest.get(key) != runs[0].manifest.get(key) for r in runs):
                problems.append(f"run_manifest {key} differs")
        ins = [{k: v for k, v in (r.manifest.get("inputs") or {}).items() if k != "ids_sha256"} for r in runs]
        if any(i != ins[0] for i in ins):
            problems.append("run_manifest inputs differ in more than ids_sha256")
        # the starts of every run, in the order they began (rule 5)
        legs = sorted(((leg.get("started_at") or "", n, r, leg) for n, r in enumerate(runs)
                       for leg in r.manifest.get("legs") or []), key=lambda x: (x[0], x[1]))
        self.renumber, self.legs = {}, []
        for n, (_, _, r, leg) in enumerate(legs, 1):
            if (r.name, leg.get("leg")) in self.renumber:
                problems.append(f"{r.name}: two starts numbered {leg.get('leg')}")
            self.renumber[(r.name, leg.get("leg"))] = n
            entry = dict(leg)
            entry.update(leg=n, source_run=r.name, source_leg=leg.get("leg"),
                         environment=leg["environment"] if "environment" in leg else r.manifest.get("environment"),
                         env=leg["env"] if "env" in leg else r.manifest.get("env"))
            self.legs.append(entry)
        man = copy.deepcopy(runs[0].manifest)
        self.left_empty = []
        for key in dict.fromkeys(k for r in runs for k in r.manifest):
            if key in COUNTED or key in MUST_EQUAL:
                continue
            if any(r.manifest.get(key) != runs[0].manifest.get(key) for r in runs):
                man[key] = None
                self.left_empty.append(key)
        n_ran = sum(r.counts.get("n_rows", 0) for r in runs)
        man.update(n_questions=len(whole), n_ran=n_ran, n_failed=len(whole) - n_ran,
                   n_exhausted=(None if man.get("char_budget") is None
                                else sum(r.counts.get("exhausted", 0) for r in runs)),
                   timestamp=now, legs=self.legs)
        man["inputs"] = dict(runs[0].manifest["inputs"], ids_sha256=hashlib.sha256(ids_bytes(whole)).hexdigest())
        self.manifest = man
        # the scoring (rule 6)
        self.eval, self.eval_left_empty, self.settings_left_empty = None, [], []
        judged = [r.eval is not None for r in runs]
        if any(judged) and not all(judged):
            problems.append("some runs were scored and some were not")
        if all(judged):
            from harness.contract import ModelUsage
            evs = [r.eval for r in runs] + [r.re_eval for r in runs if r.re_eval]
            for key in EVAL_EQUAL:
                if any(e.get(key) != evs[0].get(key) for e in evs):
                    problems.append(f"eval_manifest {key} differs")
            self.checked += [f"eval_manifest.{k}" for k in EVAL_EQUAL]
            ev = copy.deepcopy(runs[0].eval)
            for key in dict.fromkeys(k for r in runs for k in r.eval):
                if key in EVAL_COUNTED or key in EVAL_EQUAL:
                    continue
                if any(r.eval.get(key) != runs[0].eval.get(key) for r in runs):
                    ev[key] = None
                    self.eval_left_empty.append(key)
            jlegs = [dict(leg, source_run=r.name) for r in runs for leg in r.eval.get("judge_legs") or []]
            jlegs += [dict(leg, source_run=r.re.name) for r in runs if r.re for leg in r.re_eval.get("judge_legs") or []]
            began = lambda x: ((x.get("settings") or {}).get("started_at") or x.get("begun_at") or "")  # noqa: E731
            jlegs.sort(key=began)
            starts = [(x.get("settings") or {}).get("started_at") for x in jlegs]
            starts = [s for s in starts if s]
            if len(starts) != len(set(starts)):
                problems.append("two scoring starts began at the same time")
            settings, self.settings_left_empty = shared_settings([x.get("settings") for x in jlegs])
            names = list(ModelUsage.__dataclass_fields__)
            ev.update(source_run=rel(out), timestamp=now, judge_legs=jlegs,
                      judge_usage={k: sum(int((x.get("usage") or {}).get(k) or 0) for x in jlegs) for k in names},
                      judge_elapsed_s=sum(float(x.get("elapsed_s") or 0.0) for x in jlegs),
                      judge_settings=settings)
            self.eval = ev
        kept = [r.name for r in runs if (r.dir / "judge_calls_without_record.json").is_file()]
        if len(kept) > 1:
            problems.append("more than one run has judge_calls_without_record.json")
        self.problems = problems

    def write(self):
        out = self.out
        out.mkdir(parents=True, exist_ok=False)
        with (out / "arm_outputs.jsonl").open("wb") as fa, (out / "failures.jsonl").open("wb") as ff:
            for r in self.runs:
                for fh, file in ((fa, "arm_outputs.jsonl"), (ff, "failures.jsonl")):
                    for raw in lines(r.dir / file):
                        rec = json.loads(raw)
                        if rec.get("leg") is not None:
                            rec["leg"] = self.renumber[(r.name, rec["leg"])]
                        fh.write((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
        if self.eval is not None:
            for file in ("eval_results.jsonl", "eval_calls.jsonl", "eval_failures.jsonl"):
                with (out / file).open("wb") as fh:
                    for r in self.runs:
                        for raw in lines(r.dir / file):
                            fh.write(raw)
                        for raw in lines(r.re / file) if r.re else ():
                            if file != "eval_results.jsonl" or json.loads(raw)["metric"] in REJUDGED_SCORES:
                                fh.write(raw)
            (out / "eval_manifest.json").write_text(json.dumps(self.eval, ensure_ascii=False, indent=2),
                                                    encoding="utf-8", newline="\n")
        (out / "run_manifest.json").write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2),
                                               encoding="utf-8", newline="\n")
        for r in self.runs:
            for p in sorted(r.dir.glob("code.*.diff")) + sorted(r.dir.glob("judge_calls_without_record.json")):
                if not (out / p.name).is_file():
                    shutil.copyfile(p, out / p.name)

    def record(self, moved):
        """merge.json (rule 8)."""
        return {
            "merged_at": self.now,
            "tool": "tools/merge_runs.py",
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
            "argv": list(sys.argv),
            "whole_set": {"file": rel(SET_FILE), "sha256": sha_file(SET_FILE), "n_questions": len(self.whole)},
            "checked_equal": self.checked,
            "left_empty": self.left_empty,
            "eval_left_empty": self.eval_left_empty,
            "judge_settings_left_empty": self.settings_left_empty,
            "sources": [dict({
                "name": r.name, "path": rel(r.dir), "n_questions": len(r.ids),
                "ids_sha256": r.manifest["inputs"]["ids_sha256"],
                "host": ((r.manifest.get("environment") or {}).get("host")),
                **{k: r.counts[k] for k in ("n_rows", "n_failure_lines", "n_score_rows", "n_eval_calls",
                                            "n_eval_failure_lines")},
                "legs": [{"source_leg": leg.get("leg"), "leg": self.renumber[(r.name, leg.get("leg"))]}
                         for leg in r.manifest.get("legs") or []],
                "manifest_values": {k: r.manifest.get(k) for k in self.left_empty},
                "eval_values": {k: (r.eval or {}).get(k) for k in self.eval_left_empty},
                "files_sha256": r.files,
            }, **({"rejudged": {"name": r.re.name, "path": rel(r.re), "scores": list(REJUDGED_SCORES),
                                **r.re_counts, "files_sha256": r.re_files}} if r.re else {})) for r in self.runs],
            "moved": moved,
            "kept_raw": "parts/<name>/: every run joined here and its re-judging, moved whole, every file byte for "
                        "byte as it stood before (sources[].files_sha256)",
        }


def failing(d):
    from harness import fields
    return {text for text, ok, _ in fields.relations(d) if not ok}


def move(src, dst):
    before = {k: p.stat().st_size for k, p in files_of(src).items()}
    if dst.exists():
        sys.exit(f"{rel(dst)} is there already")
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)
    if {k: p.stat().st_size for k, p in files_of(dst).items()} != before:
        sys.exit(f"{rel(dst)}: not every file of {src.name} is there with its size after the move")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    whole = whole_set()
    if SET_FILE.is_file() and SET_FILE.read_bytes() != ids_bytes(whole):
        sys.exit(f"{rel(SET_FILE)} is there and holds other ids")
    now = datetime.now(timezone.utc).isoformat()
    arms = []
    for arm, plan in PLAN.items():
        top = K / arm
        if top.exists():
            sys.exit(f"{rel(top)} is there already; nothing written")
        joins = [Join(top, [Run(name, re) for name, re in plan["join"]], whole, now)]
        for name, runs in plan["runs_without_answers"].items():
            joins.append(Join(top / "runs_without_answers" / name, [Run(n, re) for n, re in runs], whole, now))
        moves = []
        for j in joins:
            for r in j.runs:
                moves += [(r.dir, j.out / "parts" / r.name)] + ([(r.re, j.out / "parts" / r.re.name)] if r.re else [])
        for sub, names in plan["moved"].items():
            for name in names:
                if not (K / name / "run_manifest.json").is_file():
                    sys.exit(f"{name}: no run folder")
                moves.append((K / name, top / sub / name))
        arms.append((arm, joins, moves))
        for j in joins:
            print(f"{rel(j.out)}: {len(j.runs)} runs, {j.manifest['n_ran']}/{j.manifest['n_questions']} answered, "
                  f"{len(j.legs)} starts, {len((j.eval or {}).get('judge_legs') or [])} scoring starts; left empty: "
                  f"{j.left_empty}; eval: {j.eval_left_empty}; judge_settings: {j.settings_left_empty}")
            for problem in j.problems:
                print("  PROBLEM:", problem)
        print(f"  {len(moves)} folders to move into {rel(top)}")
    if any(j.problems for _, joins, _ in arms for j in joins):
        sys.exit("a join does not hold; nothing written")
    if not args.write:
        print("checked; nothing written (--write writes)")
        return

    from harness import fields
    SET_FILE.write_bytes(ids_bytes(whole))
    made = []
    try:
        for arm, joins, moves in arms:
            made.append(K / arm)
            moved = [{"name": src.name, "from": rel(src), "to": rel(dst)} for src, dst in moves]
            for j in joins:
                j.write()
                new = failing(j.out) - set().union(*(failing(r.dir) for r in j.runs))
                if new:
                    raise SystemExit(f"{rel(j.out)}: relations that fail here and in none of its runs: {sorted(new)}")
                mine = [m for m in moved if m["to"].startswith(rel(j.out) + "/parts/")]
                (j.out / "merge.json").write_text(json.dumps(j.record(moved if j.out == K / arm else mine),
                                                             ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
                fields.write(j.out)
                gaps = fields.undescribed(j.out)
                if gaps:
                    raise SystemExit(f"{rel(j.out)}: fields without a word: {gaps}")
                print(f"written {rel(j.out)}")
    except BaseException:
        for d in made:
            shutil.rmtree(d, ignore_errors=True)
        print("the new folders are removed; nothing was moved")
        raise
    done = []
    try:
        for arm, joins, moves in arms:
            for src, dst in moves:
                move(src, dst)
                done.append(rel(dst))
            print(f"{arm}: {len(moves)} folders moved in")
    except BaseException:
        print(f"a move stopped after {len(done)} folders; moved:", *done, sep="\n  ")
        raise
    big = sorted(rel(p) for arm, _, _ in arms for p in (K / arm).rglob("*") if p.is_file() and p.stat().st_size > 100_000_000)
    print("files over 100 MB (for .gitignore):")
    for b in big:
        print(" ", b)


if __name__ == "__main__":
    main()
