"""Hold a run folder's cost one model at a time, take the model calls out of the artefact's search
time, give the build cost one entry per model, and count the graph; say exactly what was changed.

    python correct_usage_by_model.py <run folder> [--write]

Without --write it only prints what it would change and what it checked. Numbers, ids and stamps
only: no question, answer or context text is printed. It starts from the files from before it:
for a folder corrected for sleep, the files correct_slept_tries.py makes from the files as recorded
(run that one first); for any other folder, the files as the run wrote them, which it keeps as
*.as_recorded.* on the first write and never changes. The graph is counted when it runs.

Rule "usage-by-model/1".
  1. A row's retrieval is its own call records summed per model (harness.capture.usage_by_model),
     the answer call left out. The answer call is the record whose system text is the harness's
     answer instruction; it is marked role: answer, and its tokens must be the generator's.
  2. The entries must hold what the row recorded: the same calls, tokens in, tokens out and cached
     tokens in all.
  3. artefact_v4 only: search_time_s loses the embedder's seconds (lock_wait_s + encode_s of the
     row's embed records) and the seconds of the first-call tries that did not answer (the chat
     entry's retry_s).
  4. build_stats gets one entry per model, from the run's own manifest: lucene none; vector the
     embedder, from its build_stats and the stored file's cost note; artefact_v4 from
     index.build_cost (artefact_v4.build_stats_from_cost).
  5. artefact_v4 only: the graph block takes the graph's last build record and the graph counted
     now (orchestrator.graph_census), after a check that the graph holds now what the run counted
     at its start.
  6. artefact_v4 only: the sha256 of the code files (meta.provenance.source_sha256) and of the
     build cost file (index.build_cost_file_sha256) become those of the commit's files, their
     line ends as git holds them (LF), after a check that each recorded value is the commit's
     file with the Windows line ends the checkout wrote.
"""
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RULE = "usage-by-model/1"
HIS_WORDS = ("\"That sounds indeed like you have fufkcing smashes a bunch of data together that does "
             "not belong together.. I sure as fuck hope you did not do that on the actual data\" · "
             "\"well, this is the data-cleanup phase so perhaps be less fucking retarded with the "
             "answers then\" · \"yes, make sure all the correct data is in those folders first of "
             "all, then i have another task for you\" (2026-10-20)")
SCRIPT = "correct_usage_by_model.py"


def raw_sha(path):
    """The sha256 of the bytes on disk, as the sleep correction recorded its files."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha(path):
    """The sha256 of a file with the line ends git holds (LF): the harness writes CR LF on
    Windows and git keeps LF, so this is the sha256 a checkout on any machine gives back."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def corrections_of(d):
    p = d / "corrections.json"
    if not p.is_file():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data["corrections"]) if "corrections" in data else [data]


def sources(d, earlier):
    """The files from before this correction, and where they are kept."""
    rows, man = d / "arm_outputs.jsonl", d / "run_manifest.json"
    kept_rows, kept_man = d / "arm_outputs.as_recorded.jsonl", d / "run_manifest.as_recorded.json"
    slept = [c for c in earlier if (c.get("rule") or {}).get("id") == "slept-try/1"]
    if any((c.get("rule") or {}).get("id") == RULE for c in earlier):
        if slept:
            raise SystemExit("this folder was corrected for sleep before: run correct_slept_tries.py "
                             "on it first, then this script again")
        return kept_rows, kept_man, "as recorded"
    if slept:
        want = {name: f["sha256_corrected"] for name, f in slept[-1]["files"].items()}
        if raw_sha(rows) != want["arm_outputs.jsonl"] or raw_sha(man) != want["run_manifest.json"]:
            raise SystemExit("the files are not those the sleep correction left")
        return rows, man, "as the sleep correction left them (correct_slept_tries.py, from the files as recorded)"
    return rows, man, "as recorded"


def close(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def git_file(repo, commit, path):
    """The commit's file, its line ends as git holds them."""
    return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=repo, capture_output=True,
                          check=True).stdout


def as_in_git(repo, commit, path, recorded):
    """The sha256 of the commit's file (LF), and whether `recorded` is that file with the line
    ends git holds or with the Windows line ends a checkout writes."""
    lf = git_file(repo, commit, path).replace(b"\r\n", b"\n")
    ours = hashlib.sha256(lf).hexdigest()
    return ours, recorded in (ours, hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest())


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    p.add_argument("folder")
    p.add_argument("--repo", help="the repository whose harness reads the folder (default: three "
                                  "folders up from it)")
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    d = Path(args.folder).resolve()
    repo = Path(args.repo).resolve() if args.repo else d.parents[2]
    sys.path[:0] = [str(repo / "prod"), str(repo / "test")]
    from harness import capture, fields, orchestrator, provenance
    from harness.contract import GENERATOR_SYSTEM, BuildStats, build_stats_record
    # the code this correction runs on: the script imports the harness and the arms from it
    code = {**provenance.code_version(), **{k: v for k, v in provenance.code_state().items()
                                             if k != "diff"}}

    earlier = corrections_of(d)
    src_rows, src_man, before = sources(d, earlier)
    # run again, it starts from the files from before it and so replaces its own entry
    earlier = [c for c in earlier if (c.get("rule") or {}).get("id") != RULE]
    man = json.loads(src_man.read_text(encoding="utf-8"))
    arm = man["arm"]
    lines = src_rows.read_bytes().split(b"\n")

    changes, checks, new_lines = [], [], []
    tally = {"rows": 0, "answer_marked": 0, "answer_is_the_generators": 0, "sums_hold": 0,
             "chat_tries_hold": 0, "no_second_twice": 0, "same_code_hashes": 0}
    code_hashes = None
    if arm == "artefact_v4":
        commit = man["code_version"]["commit"]
        first = json.loads(next(line for line in lines if line.strip()))
        recorded_code = first["meta"]["provenance"]["source_sha256"]
        code_hashes, held = {}, []
        for path, value in recorded_code.items():
            ours, ok = as_in_git(repo, commit, path.replace("\\", "/"), value)
            code_hashes[path] = ours
            held.append(ok)
            changes.append({"where": "arm_outputs.jsonl, every row: meta.provenance.source_sha256",
                            "field": path, "recorded": value, "corrected": ours})
        checks.append({"what": "each code file's recorded sha256 is the commit's file, with the "
                               "line ends git holds or those the checkout wrote",
                       "holds": all(held), "looked_at": len(held), "detail": f"commit {commit[:7]}"})
    worst = {"wall_gap_min": None, "below_min": None, "below_max": None}
    for n, line in enumerate(lines):
        if not line.strip():
            new_lines.append(line)
            continue
        row = json.loads(line)
        tally["rows"] += 1
        where = f"arm_outputs.jsonl row {n} ({row['id']})"
        calls = row.get("calls") or []
        answers = [i for i, c in enumerate(calls) if c.get("kind") == "chat" and c.get("ok")
                   and c.get("system") == GENERATOR_SYSTEM]
        if len(answers) != 1:
            raise SystemExit(f"{where}: {len(answers)} answer calls, not one")
        a = calls[answers[0]]
        if a.get("role") != "answer":
            a["role"] = "answer"
            changes.append({"where": where, "field": f"calls[{answers[0]}].role",
                            "recorded": None, "corrected": "answer"})
        tally["answer_marked"] += 1
        g = row["generator"]
        if (a["usage"]["prompt_tokens"], a["usage"]["completion_tokens"]) == (g["tokens_in"], g["tokens_out"]):
            tally["answer_is_the_generators"] += 1

        old = row["retrieval"]
        if not isinstance(old, dict):
            raise SystemExit(f"{where}: retrieval is already one entry per model")
        new = capture.usage_by_model([c for c in calls if c.get("role") != "answer"])
        held = {k: sum(e[k] for e in new) for k in ("calls", "tokens_in", "tokens_out",
                                                     "cached_input_tokens")}
        if held == {k: old[k] for k in held}:
            tally["sums_hold"] += 1
        else:
            raise SystemExit(f"{where}: the entries hold {held}, the row recorded "
                             f"{ {k: old[k] for k in held} }")
        chat = [e for e in new if e["kind"] == "chat"]
        if chat:
            e = chat[0]
            if (e["attempts"] == old["attempts"] and close(e["request_s"], old["request_s"], 1e-3)
                    and close(e["retry_s"], old["retry_s"], 1e-3)):
                tally["chat_tries_hold"] += 1
        # the arm's own time_s left out the tries that did not answer; its retry_s held them
        below = old["time_s"] + old["retry_s"] - sum(e["time_s"] for e in new)
        worst["below_min"] = below if worst["below_min"] is None else min(worst["below_min"], below)
        worst["below_max"] = below if worst["below_max"] is None else max(worst["below_max"], below)
        if sum(e["time_s"] for e in new) > old["time_s"] + 1e-3:
            worst.setdefault("left_out", []).append(row["id"])
        row["retrieval"] = new
        changes.append({"where": where, "field": "retrieval", "recorded": old, "corrected": new})

        if arm == "artefact_v4":
            prov = row["meta"]["provenance"]
            if prov["source_sha256"] == recorded_code:
                tally["same_code_hashes"] += 1
            prov["source_sha256"] = dict(code_hashes)
            embed_s = sum(float(c.get("lock_wait_s") or 0.0) + float(c.get("encode_s") or 0.0)
                          for c in calls if c.get("kind") == "embed")
            refused_s = sum(e["retry_s"] for e in chat)
            corrected = row["search_time_s"] - embed_s - refused_s
            if corrected < 0:
                raise SystemExit(f"{where}: the search time would go below zero")
            changes.append({"where": where, "field": "search_time_s",
                            "recorded": row["search_time_s"], "corrected": corrected,
                            "taken_out": {"embedder_s": embed_s, "refused_first_call_tries_s": refused_s}})
            row["search_time_s"] = corrected
        gap = row["timing"]["wall_s"] - (row["search_time_s"] + sum(e["time_s"] for e in new)
                                         + g["time_s"])
        worst["wall_gap_min"] = gap if worst["wall_gap_min"] is None else min(worst["wall_gap_min"], gap)
        if gap >= -0.5:
            tally["no_second_twice"] += 1
        new_lines.append(json.dumps(row, ensure_ascii=False, default=repr).encode("utf-8"))

    rows_n = tally["rows"]
    checks += [
        {"what": "every row has one answer call, its record marked role: answer",
         "holds": tally["answer_marked"] == rows_n, "looked_at": rows_n},
        {"what": "the answer call's tokens are the generator's",
         "holds": tally["answer_is_the_generators"] == rows_n, "looked_at": rows_n},
        {"what": "the entries hold the calls, tokens in, tokens out and cached tokens the row "
                 "recorded", "holds": tally["sums_hold"] == rows_n, "looked_at": rows_n},
        {"what": "no second is counted twice: search_time_s, the retrieval's time_s and "
                 "generator.time_s add up to no more than timing.wall_s, half a second allowed",
         "holds": tally["no_second_twice"] == rows_n, "looked_at": rows_n,
         "detail": f"the smallest gap left in a row: {worst['wall_gap_min']:.3f} s"},
        {"what": "in every row the retrieval entries' seconds are no more than the arm's own sum "
                 "with its retry_s, a millisecond allowed",
         "holds": worst["below_min"] >= -1e-3, "looked_at": rows_n,
         "detail": f"the arm's own sum was {worst['below_min']:.4f} to {worst['below_max']:.4f} s "
                   "more in a row: its own work around the calls"
                   + (f"; its time_s left out the tries that did not answer in "
                      f"{', '.join(worst['left_out'])}" if worst.get("left_out") else "")},
    ]
    if arm == "artefact_v4":
        checks.append({"what": "the first call's entry has the tries, request and retry seconds "
                               "the arm recorded from the lane, to within a millisecond",
                       "holds": tally["chat_tries_hold"] == rows_n, "looked_at": rows_n})
        checks.append({"what": "every row recorded the same code files with the same sha256",
                       "holds": tally["same_code_hashes"] == rows_n, "looked_at": rows_n})

    # build_stats, one entry per model
    old_bs = man["build_stats"]
    if arm == "artefact_v4":
        from arms import artefact_v4
        bs = build_stats_record(artefact_v4.build_stats_from_cost(man["index"]["build_cost"]))
        commit = man["code_version"]["commit"]
        committed = git_file(repo, commit, "test/graph/build_cost.json")
        checks.append({"what": "the build cost in the manifest is the commit's "
                               "test/graph/build_cost.json, word for word",
                       "holds": json.loads(committed) == man["index"]["build_cost"],
                       "looked_at": 1, "detail": f"commit {commit[:7]}"})
        held = []
        for where, index in [("run_manifest.json index", man["index"])] + [
                (f"run_manifest.json legs[leg={leg['leg']}].index", leg["index"])
                for leg in man.get("legs") or [] if isinstance(leg.get("index"), dict)]:
            ours, ok = as_in_git(repo, commit, "test/graph/build_cost.json",
                                 index["build_cost_file_sha256"])
            held.append(ok)
            changes.append({"where": where, "field": "build_cost_file_sha256",
                            "recorded": index["build_cost_file_sha256"], "corrected": ours})
            index["build_cost_file_sha256"] = ours
        checks.append({"what": "the build cost file's recorded sha256 is the commit's file, with "
                               "the line ends git holds or those the checkout wrote",
                       "holds": all(held), "looked_at": len(held)})
    elif arm == "vector":
        from arms import vector
        m = old_bs["model"]
        note = (man.get("index") or {}).get("cache_cost_note") or {}
        bs = build_stats_record(BuildStats(old_bs["build_time_s"], models=[vector._build_entry(
            m["calls"], m["tokens_in"], m["tokens_out"], m["time_s"], note.get("device"),
            vector._seconds_note(note))]))
    else:
        m = old_bs.get("model") or {}
        if any(m.get(k) for k in ("calls", "tokens_in", "tokens_out")) or old_bs.get("models"):
            raise SystemExit(f"{arm}: a build with a model this script does not know")
        bs = build_stats_record(BuildStats(old_bs["build_time_s"], models=[]))
    changes.append({"where": "run_manifest.json", "field": "build_stats", "recorded": old_bs,
                    "corrected": bs})
    man["build_stats"] = bs

    if arm == "artefact_v4":
        from arms import artefact_v4
        then = json.loads(lines[0])["meta"]["provenance"]
        now = artefact_v4.prepare_over_corpus(then["corpus_argument"]).provenance
        same = {k: now[k] == then[k] for k in ("database", "run_id", "facet_layer", "counts",
                                               "topic_on_the_edge_against_the_vectors_max_abs")}
        checks.append({"what": "the graph holds now what the run counted at its start: the "
                               "database, the edges' run, the facet layer with its hashes, every "
                               "count, the topic check",
                       "holds": all(same.values()), "looked_at": len(same),
                       "detail": ", ".join(k for k, v in same.items() if not v) or "all the same"})
        if not all(same.values()):
            raise SystemExit("the graph is not what the run read: nothing is written")
        counted = orchestrator.graph_census(man["graph"]["database"])
        if counted.get("census") is None:
            raise SystemExit(f"the graph could not be counted: {counted.get('census_error')}")
        graph = orchestrator.graph_identity(man["graph"]["database"], counted)
        changes.append({"where": "run_manifest.json", "field": "graph", "recorded": man["graph"],
                        "corrected": graph})
        man["graph"] = graph
        checks.append({"what": "the graph's last build record was found", "looked_at": 1,
                       "holds": graph["graph_version"] is not None,
                       "detail": f"written {graph['build_timestamp']}; the steps after it are in "
                                 "index.build_cost"})

    print(f"{d.name} ({arm}); from the files {before}")
    for c in checks:
        print(f"  [{'ok' if c['holds'] else 'NO'}] {c['what']} | {c['looked_at']} looked at"
              + (f" | {c['detail']}" if c.get("detail") else ""))
    print(f"  changes: {len(changes)} ({sum(1 for c in changes if c['field'] == 'retrieval')} "
          f"retrieval, {sum(1 for c in changes if c['field'] == 'search_time_s')} search_time_s, "
          f"{sum(1 for c in changes if c['field'].endswith('.role'))} answer marks, "
          f"{sum(1 for c in changes if c['where'] == 'run_manifest.json')} in the manifest)")
    if not all(c["holds"] for c in checks):
        raise SystemExit("a check does not hold: nothing is written")
    if not args.write:
        print("  (nothing written; --write does it)")
        return

    rows_path, man_path = d / "arm_outputs.jsonl", d / "run_manifest.json"
    kept = {"arm_outputs.jsonl": d / "arm_outputs.as_recorded.jsonl",
            "run_manifest.json": d / "run_manifest.as_recorded.json"}
    before_sha = {"arm_outputs.jsonl": sha(src_rows), "run_manifest.json": sha(src_man)}
    for name, copy in kept.items():
        if not copy.exists():
            shutil.copy2(d / name, copy)
    tmp = rows_path.with_name(rows_path.name + ".tmp")
    tmp.write_bytes(b"\n".join(new_lines))
    tmp.replace(rows_path)
    tmp = man_path.with_name(man_path.name + ".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=2, default=repr), encoding="utf-8")
    tmp.replace(man_path)
    if Path(__file__).resolve() != (d / SCRIPT).resolve():
        shutil.copy2(__file__, d / SCRIPT)

    slept = any((c.get("rule") or {}).get("id") == "slept-try/1" for c in earlier)
    what = {
        "artefact_v4": "The row's retrieval held the first call (claude-sonnet-5) and the "
                       "embedder's requests added into one sum: a language model's tokens and the "
                       "embedder's tokens were one number, and attempts counted the first call's "
                       "tries while calls counted both; in the two questions whose first call was "
                       "refused and asked again, its time_s left out the refused call's seconds, "
                       "which only its retry_s held. search_time_s held the embedder's seconds, "
                       "which were also in retrieval.time_s, and, in those two questions, the "
                       "refused call's seconds. build_stats held the seconds of the run's start, "
                       "not what building the graph cost, which stood only in index.build_cost. "
                       "The graph block named the database only: the checkout the run was made "
                       "from had no build record of the graph, and nothing counted the graph. The "
                       "sha256 of the code files and of the build cost file were of the files with "
                       "the Windows line ends the checkout wrote, so none matched the commit's.",
        "vector": "The row's retrieval and build_stats each held one sum without the model's "
                  "name, a form the arms cannot share without adding two models together; "
                  "build_stats counted 0 attempts for its calls.",
        "lucene": "The row's retrieval and build_stats each held one sum, all zero, in the form "
                  "the arms cannot share without adding two models together.",
    }[arm]
    entry = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "ordered_by": HIS_WORDS,
        "what_happened": what,
        "rule": {"id": RULE, "text": __doc__.split(f"Rule \"{RULE}\".")[1].strip()},
        "not_changed_and_worth_knowing": [
            "No answer, context, id, score or judge call is changed; the call records are changed "
            "only by the answer call's role.",
            "A retrieval entry's seconds are the tries' and the embedder's own seconds from the call "
            "records. The sum the arm recorded held the seconds around each call, so the entries "
            "hold a little less; that rest is the arm's own work, in timing.wall_s.",
            "timing.wall_s and the stamps are unchanged."
            + (" The sleep correction before this one stands as it was." if slept else ""),
        ] + ([
            "The graph census counts and reads no value. That the graph counted now is the graph "
            "the run read rests on the check named in checks: the counts and the facet layer's "
            "hashes the run recorded at its start are those of now.",
            "The graph's last build record is from before the October steps of index.build_cost; "
            "its version and census hash describe the graph as that build left it.",
        ] if arm == "artefact_v4" else []),
        "changes": changes,
        "checks": checks,
        "files": {name: {"sha256_before": before_sha[name], "sha256_corrected": sha(d / name),
                         "line_ends": "the sha256 are of the file with the line ends git holds (LF)",
                         "before": (f"{kept[name].name}, as recorded" if not slept else
                                    f"made by correct_slept_tries.py from {kept[name].name}")}
                  for name in kept},
        "script": f"{SCRIPT}, in this folder; run on the files from before it, with the code "
                  "named in code, it gives these files again (the graph is counted when it runs)",
        "code": code,
    }
    (d / "corrections.json").write_text(json.dumps({"corrections": earlier + [entry]},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    fields.write(d, stamp_files=True)
    print(f"  written: arm_outputs.jsonl, run_manifest.json, corrections.json ({len(earlier) + 1} "
          f"corrections), FIELDS.md, {SCRIPT}")
    for text, ok, detail in fields.relations(d):
        print(f"  [{'ok' if ok else 'NO'}] {text} | {detail}")
    gaps = fields.undescribed(d)
    print(f"  fields without a word: {len(gaps)}" + (f" {gaps}" if gaps else ""))


if __name__ == "__main__":
    main()
