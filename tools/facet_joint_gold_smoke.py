"""Prepare, execute once, and report aggregate-only standard 10smoke results.

Preparation reads code and frozen retrieval artifacts, never benchmark records.
Only explicit --run starts the existing answer and RAGAS runner processes.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
ARM = "artefact_facet_joint"
GENERATOR = "claude-sonnet-5"
JUDGE = "claude-haiku-4-5"
RUN_ROOT = ROOT / "output/k=chars"
PREFIX = ARM + "__10smoke__cb72000__"
JUDGE_SUFFIX = "__j-claude-haiku-4-5__10smoke"
PLAN = "smoke_plan.json"
USAGE_FIELDS = (
    "calls", "tokens_in", "tokens_out", "cached_input_tokens", "reasoning_tokens",
    "time_s", "attempts", "request_s", "wait_s", "retry_s",
)


class SafeStop(Exception):
    """Only fixed, content-free reason codes belong in this exception."""


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_new(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def emit(data):
    print(json.dumps(data, ensure_ascii=False, allow_nan=False), flush=True)


def literals(path):
    """Inspect module constants without importing any model or benchmark loader."""
    values = {}
    for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        values[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        pass
    return values


def commands(folder):
    python = str(Path(sys.executable).resolve())
    runner = str(ROOT / "prod/run.py")
    return {
        "generation": [python, "-u", runner, "--arm", ARM, "--set", "10smoke",
                       "--char-budget", "72000", "--workers", "4", "--generator",
                       GENERATOR, "--no-eval", "--out", str(folder)],
        "judge": [python, "-u", runner, "--rejudge", str(folder), "--set", "10smoke",
                  "--judge", JUDGE, "--workers", "16"],
    }


def frozen_inputs():
    arm = ROOT / "test/arms" / (ARM + ".py")
    if not arm.is_file():
        raise SafeStop("adapter_not_ready")
    registry = literals(ROOT / "prod/run.py")
    if any(ARM not in registry.get(k, ()) for k in ("ARMS", "CHAR_BUDGET_ARMS")):
        raise SafeStop("adapter_not_registered")
    declared = literals(arm)
    if ARM == 'artefact_facet_area':
        # The area wrapper inherits the base configuration. Resolve this known
        # composition statically, without importing the retrieval/model stack.
        declared = literals(ROOT / 'test/arms/artefact_facet_joint.py')
        declared['SMOKE_PROVENANCE_PATHS'] = (*declared['SMOKE_PROVENANCE_PATHS'],
                                             'test/arms/artefact_facet_area.py')
        declared['SMOKE_MODEL_CONFIG'] = {**declared['SMOKE_MODEL_CONFIG'],
                                        'scope_scheduling': 'area_first'}
    # Adapter declares only code/artifact paths, never questions or gold files.
    paths = declared.get("SMOKE_PROVENANCE_PATHS")
    if not isinstance(paths, (list, tuple)) or not paths:
        raise SafeStop("adapter_provenance_not_ready")
    files = {Path(__file__).resolve(), ROOT / "prod/run.py", arm}
    files.update((ROOT / "prod/harness").rglob("*.py"))
    files.update((ROOT / "prod/eval").rglob("*.py"))
    for relative in paths:
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or path.is_relative_to(ROOT / "data"):
            raise SafeStop("invalid_provenance_path")
        if not path.is_file():
            raise SafeStop("provenance_input_missing")
        files.add(path)
    metrics = literals(ROOT / "prod/eval/ragas_catalog.py").get("SELECTED")
    if (not isinstance(metrics, list) or len(metrics) != 14 or
            len(set(metrics)) != len(metrics) or not all(isinstance(m, str) for m in metrics)):
        raise SafeStop("standard_metric_catalog_changed")
    models = declared.get("SMOKE_MODEL_CONFIG")
    if not isinstance(models, dict):
        raise SafeStop("adapter_model_config_not_ready")
    return ({str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}, metrics, models)


def prepare():
    inputs, metrics, adapter_models = frozen_inputs()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = RUN_ROOT / (PREFIX + stamp)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "private").mkdir()
    model_config = {"generator": GENERATOR, "judge": JUDGE,
                    "adapter": adapter_models}
    model_hash = hashlib.sha256(json.dumps(model_config, sort_keys=True).encode()).hexdigest()
    plan = {
        "schema_version": 1, "prepared_at": utc(), "folder": str(folder),
        "judge_folder": str(folder.with_name(folder.name + JUDGE_SUFFIX)),
        "commands": commands(folder), "input_sha256": inputs, "metrics": metrics,
        "models": model_config, "model_config_sha256": model_hash,
        "provenance": "Frozen Volmax graph snapshot; this is not a live database retrieval claim.",
        "benchmark_policy": "Standard 10smoke and standard RAGAS only; no gold-driven tuning or metric filtering.",
    }
    write_new(folder / PLAN, plan)
    write_new(folder / "prepared.json", {"at": utc(), "plan_sha256": sha(folder / PLAN)})
    emit({"phase": "prepared", "folder": str(folder), "metric_count": len(metrics),
          "model_calls": 0, "benchmark_records_read": 0})
    return 0


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def usage_only(value):
    if not isinstance(value, dict):
        return {}
    return {k: value[k] for k in USAGE_FIELDS if numeric(value.get(k))}


def json_rows(path):
    if path.is_file():
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def aggregate_answers(folder):
    """Read records mechanically; never return question/answer/context/ID values."""
    path = folder / "run_manifest.json"
    manifest = read_json(path) if path.is_file() else {}
    count = nonempty = 0
    ids = set()
    usage = {"generator": Counter(), "retrieval": Counter()}
    search_seconds = 0.0
    for row in json_rows(folder / "arm_outputs.jsonl"):
        count += 1
        ids.add(row["id"])
        nonempty += isinstance(row.get("answer"), str) and bool(row["answer"].strip())
        for role in usage:
            usage[role].update(usage_only(row.get(role)))
        if numeric(row.get("search_time_s")):
            search_seconds += row["search_time_s"]
    failures = sum(1 for _ in json_rows(folder / "failures.jsonl"))
    stats = {"answers": count, "unique_answers": len(ids), "nonempty_answers": nonempty,
             "failures": failures, "search_seconds_sum": search_seconds,
             "usage": {k: dict(v) for k, v in usage.items()}}
    for k in ("n_questions", "n_ran", "n_failed", "n_exhausted"):
        stats[k] = manifest.get(k) if numeric(manifest.get(k)) else None
    stats["build_usage"] = usage_only((manifest.get("build_stats") or {}).get("model"))
    stats["ready_for_judge"] = (
        count == len(ids) == nonempty == 10 and failures == 0 and
        stats["n_questions"] == stats["n_ran"] == 10 and stats["n_failed"] == 0 and
        manifest.get("generator_model") == GENERATOR and manifest.get("arm") == ARM and
        manifest.get("char_budget") == 72000)
    return stats


def aggregate_metrics(folder, metrics):
    """Keep the evaluator's exact metric names and all selected metrics."""
    sums = Counter()
    good = Counter()
    errors = Counter()
    seen = set()
    unknown = duplicate = 0
    for row in json_rows(folder / "eval_results.jsonl"):
        metric = row.get("metric")
        if metric not in metrics:
            unknown += 1
            continue
        key = (row.get("question_id"), metric)
        if key in seen:
            duplicate += 1
        seen.add(key)
        if row.get("status") == "ok" and numeric(row.get("value")):
            sums[metric] += row["value"]
            good[metric] += 1
        else:
            errors[metric] += 1
    path = folder / "eval_manifest.json"
    manifest = read_json(path) if path.is_file() else {}
    by_metric = {m: {"mean": sums[m] / good[m] if good[m] else None,
                     "ok": good[m], "errors": errors[m],
                     "missing": max(0, 10 - good[m] - errors[m])} for m in metrics}
    return {"metrics": by_metric, "metric_count": len(metrics),
            "error_cells": sum(errors.values()), "unknown_metric_cells": unknown,
            "duplicate_cells": duplicate,
            "missing_cells": sum(v["missing"] for v in by_metric.values()),
            "judge_usage": usage_only(manifest.get("judge_usage")),
            "judge_elapsed_s": manifest.get("judge_elapsed_s") if numeric(manifest.get("judge_elapsed_s")) else None,
            "judge_model_matches": manifest.get("judge_model") == JUDGE}


def verify_plan(folder):
    folder = folder.resolve()
    if folder.parent != RUN_ROOT.resolve() or not folder.name.startswith(PREFIX):
        raise SafeStop("invalid_prepared_folder")
    plan = read_json(folder / PLAN)
    if sha(folder / PLAN) != read_json(folder / "prepared.json")["plan_sha256"]:
        raise SafeStop("plan_changed")
    if plan["folder"] != str(folder) or plan["commands"] != commands(folder):
        raise SafeStop("prepared_commands_changed")
    inputs, metrics, models = frozen_inputs()
    if (inputs != plan["input_sha256"] or metrics != plan["metrics"] or
            models != plan["models"]["adapter"]):
        raise SafeStop("frozen_inputs_changed")
    if (folder / "started.json").exists():
        raise SafeStop("already_started_no_automatic_retry")
    if (folder / "arm_outputs.jsonl").exists() or Path(plan["judge_folder"]).exists():
        raise SafeStop("output_already_exists")
    return plan


def run_child(folder, phase, command):
    write_new(folder / (phase + "_started.json"), {"at": utc()})
    emit({"phase": phase + "_started"})
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    # Existing runner/model retry behavior remains unchanged; no phase is retried here.
    with (folder / "private" / (phase + ".log")).open("xb") as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, check=False)
    status = {"phase": phase + "_completed", "at": utc(), "return_code": result.returncode,
              "elapsed_s": round(time.monotonic() - started, 3)}
    write_new(folder / (phase + "_completed.json"), status)
    emit(status)
    return status


def execute(folder):
    folder = folder.resolve()
    plan = verify_plan(folder)
    write_new(folder / "started.json", {"at": utc(), "pid": os.getpid()})
    started = time.monotonic()
    report = {"phase": "started", "generation": None, "evaluation": None}
    code = 1
    try:
        generation = run_child(folder, "generation", plan["commands"]["generation"])
        report["generation"] = generation
        answers = aggregate_answers(folder)
        report["answers"] = answers
        emit({"phase": "generation_audit", **answers})
        if generation["return_code"] != 0:
            raise SafeStop("generation_process_failed")
        if not answers["ready_for_judge"]:
            raise SafeStop("generation_gate_failed")
        # Protect the frozen policy again at the phase boundary.
        if frozen_inputs()[0] != plan["input_sha256"]:
            raise SafeStop("frozen_inputs_changed_before_judge")
        judge = run_child(folder, "judge", plan["commands"]["judge"])
        report["evaluation"] = judge
        metrics = aggregate_metrics(Path(plan["judge_folder"]), plan["metrics"])
        report["ragas"] = metrics
        emit({"phase": "ragas_audit", **metrics})
        if judge["return_code"] != 0:
            raise SafeStop("judge_process_failed")
        if (metrics["unknown_metric_cells"] or metrics["duplicate_cells"] or
                metrics["missing_cells"] or not metrics["judge_model_matches"]):
            raise SafeStop("evaluation_shape_incomplete")
        code = 0
        report["phase"] = "completed_with_metric_errors" if metrics["error_cells"] else "completed"
    except SafeStop as exc:
        report.update(phase="stopped", reason_code=str(exc))
    except BaseException:
        # Never stringify private record data or exceptions on stdout/stderr.
        with (folder / "private/wrapper_error.log").open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        report.update(phase="stopped", reason_code="wrapper_exception_private_log")
    finally:
        report["elapsed_s"] = round(time.monotonic() - started, 3)
        write_new(folder / "aggregate_report.json", report)
        write_new(folder / "completed.json", {"at": utc(), "phase": report["phase"], "exit_code": code})
        emit({"phase": report["phase"], "elapsed_s": report["elapsed_s"],
              "reason_code": report.get("reason_code"), "exit_code": code})
    return code


def main():
    global ARM, PREFIX
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('artefact_facet_joint', 'artefact_facet_area'),
                        default='artefact_facet_joint')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true", help="freeze a new plan; default, no model calls")
    mode.add_argument("--run", type=Path, metavar="PREPARED_FOLDER", help="execute that frozen plan once")
    args = parser.parse_args()
    ARM = args.arm
    PREFIX = ARM + '__10smoke__cb72000__'
    try:
        return execute(args.run) if args.run else prepare()
    except SafeStop as exc:
        emit({"phase": "refused", "reason_code": str(exc)})
    except Exception:
        emit({"phase": "refused", "reason_code": "preflight_failed"})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
