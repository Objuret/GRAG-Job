"""Stage the unchanged seven-question fresh capture, snapshot and retrieval smoke.

--stage prepare makes no model calls. Other stages explicitly launch existing
tools; capture allows at most 7 GENERATE + 14 SCORE attempts with their original
started markers and no retries. A failed/uncertain stage stops the chain.
All artifacts stay under independent_sources/fresh_smoke; no new retrieval policy.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output/research/2026-09-22-joint-streams/independent_sources"
OUT = BASE / "fresh_smoke"
QUESTIONS = BASE / "questions.json"
BETA = ["1", ".25", ".25", ".25", ".25"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)


def command(tool, *args):
    return [sys.executable, "-X", "utf8", str(ROOT / "tools" / tool), *map(str, args)]


def commands(protocol, questions):
    capture = command("facet_independent_capture.py", "--questions", QUESTIONS,
                      "--out", OUT / "query_capture", "--spec", protocol)
    snapshot = command("facet_independent_snapshot.py", "--capture", OUT / "query_capture/query_captures.json",
                       "--questions", QUESTIONS, "--out", OUT / "query_snapshot")
    retrievals = [command("facet_retrieval_demo.py", "--query-bundle", OUT,
                         "--question-id", q["id"], "--reading-index", repeat,
                         "--coefficients", *BETA, "--source-character-budget", 72000,
                         "--verified-area", "--output", OUT / "retrieval" / f"{q['id']}_0_score_{repeat}")
                  for q in questions for repeat in (0, 1)]
    return {"prepare": [capture], "capture": [[*capture, "--run"]],
            "snapshot": [snapshot], "retrieve": retrievals}


def invoke(cmd, log):
    # One subprocess invocation only. Existing capture tool owns its per-call caps.
    with log.open("x", encoding="utf-8") as f:
        p = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, text=True)
    if p.returncode:
        raise RuntimeError(f"Stage command exited {p.returncode}; preserved log: {log}")


def capture_ready():
    doc = read(OUT / "query_capture/query_captures.json")
    expected = {q["id"]: q["question"] for q in read(QUESTIONS)}
    captures = doc["captures"]
    if len(captures) != 7 or {c["question_id"]: c["question"] for c in captures} != expected:
        raise ValueError("Fresh capture does not contain exactly the seven unchanged raw questions")
    failed = []
    for c in captures:
        rs = c.get("readings", [])
        if (not c["generation_validation"]["ok"] or len(rs) != 2
                or {r["repeat"] for r in rs} != {0, 1} or any(not r["ok"] for r in rs)):
            failed.append(c["question_id"])
    counts = doc["counts"]
    if counts["started_generation_attempts"] > 7 or counts["started_score_attempts"] > 14:
        raise ValueError("Capture attempt cap exceeded")
    if failed or counts["successful_generations"] != 7 or counts["successful_readings"] != 14:
        raise ValueError(f"Incomplete/failed readings preserved; downstream stages blocked: {failed}")
    return counts


def verify_plan(plan):
    for path, expected in plan["input_sha256"].items():
        if sha(ROOT / path) != expected:
            raise ValueError(f"Frozen smoke dependency changed: {path}")


def prepare(protocol):
    if not protocol.is_file():
        raise ValueError("Freeze fresh_smoke/PROTOCOL.md before preparing or running stages")
    questions = read(QUESTIONS)
    if not isinstance(questions, list) or len(questions) != 7 or len({q["id"] for q in questions}) != 7:
        raise ValueError("Expected the existing seven distinct raw questions")
    paths = [Path(__file__), QUESTIONS, protocol, ROOT / "tools/facet_retrieval_demo.py",
             ROOT / "tools/facet_independent_capture.py", ROOT / "tools/facet_independent_snapshot.py",
             ROOT / "tools/facet_route_capture.py", ROOT / "test/artefact/querytagger.py",
             ROOT / "test/artefact/querytagger_split_check.py", ROOT / "prod/harness/chat.py",
             ROOT / "prod/harness/embed.py"]
    paths += [ROOT / "test/artefact" / name for name in (
        "facet_retrieval_pipeline.py", "facet_scope_recruitment.py", "facet_joint_candidate.py",
        "facet_stream_envelope.py", "facet_recruitment_candidate.py", "facet_need_frontier.py")]
    plan_path = OUT / "stage_plan.json"
    frozen = {"commands": commands(protocol, questions), "generation_attempt_limit": 7,
              "score_attempt_limit": 14, "retrievals": 14, "coefficients": BETA,
              "source_character_budget": 72000, "scope": "Reuse exact-question/reading archived areas; no new resolution.",
              "failure_policy": "Stop on failed/incomplete stage. Never automatically retry. Preserve transport/started markers and outputs.",
              "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths}}
    if plan_path.exists():
        existing = read(plan_path)
        if existing != frozen:
            raise ValueError("Existing smoke plan differs; do not silently replace it")
    else:
        write_new(plan_path, frozen)
    verify_plan(frozen)
    done = OUT / "prepare.complete.json"
    if done.exists():
        if sha(OUT / "query_capture/manifest.json") != read(done)["capture_manifest_sha256"]:
            raise ValueError("Prepared capture manifest changed")
        return frozen
    marker = OUT / "prepare.started.json"
    write_new(marker, {"started_utc": datetime.now(timezone.utc).isoformat()})
    existing_capture = (OUT / "query_capture/manifest.json").exists()
    if not existing_capture:
        invoke(frozen["commands"]["prepare"][0], OUT / "prepare.log")
    capture_manifest = read(OUT / "query_capture/manifest.json")
    if (capture_manifest["generation_attempt_limit"], capture_manifest["score_attempt_limit"],
            capture_manifest["total_attempt_limit"]) != (7, 14, 21):
        raise ValueError("Existing capture tool changed its attempt caps")
    if ({j['question_id']: j['question'] for j in capture_manifest['jobs']}
            != {q['id']: q['question'] for q in questions}
            or capture_manifest['spec_sha256'] != sha(protocol)):
        raise ValueError("Existing capture manifest differs from frozen questions/protocol")
    for path, expected in capture_manifest['source_sha256'].items():
        if sha(ROOT / path) != expected:
            raise ValueError("Existing capture dependency changed: " + path)
    write_new(done, {"capture_manifest_sha256": sha(OUT / "query_capture/manifest.json"),
                     "model_calls_by_this_prepare": 0, "adopted_existing_capture_manifest": existing_capture})
    return frozen


def snapshot_ready():
    manifest = read(OUT / "query_snapshot/manifest.json")
    if manifest["completed_capture_sha256"] != sha(OUT / "query_capture/query_captures.json"):
        raise ValueError("Snapshot does not describe the completed fresh capture")
    for name, expected in manifest["output_sha256"].items():
        if sha(OUT / "query_snapshot" / name) != expected:
            raise ValueError("Fresh snapshot output hash mismatch: " + name)


def complete_stage(stage, adopted):
    folder = OUT / {"capture": "query_capture", "snapshot": "query_snapshot", "retrieve": "retrieval"}[stage]
    write_new(OUT / f"{stage}.complete.json", {
        "completed_utc": datetime.now(timezone.utc).isoformat(), "adopted_existing_outputs_without_calls": adopted,
        "output_sha256": {str(p.relative_to(OUT)): sha(p) for p in sorted(folder.rglob("*")) if p.is_file()},
        "claims": "Stage completion only; no retrieval-quality metric inferred."})


def run_stage(stage, plan):
    verify_plan(plan)
    complete = OUT / f"{stage}.complete.json"
    if complete.exists():
        for path, expected in read(complete)['output_sha256'].items():
            if sha(OUT / path) != expected:
                raise ValueError("Completed stage output changed: " + path)
        print(f"{stage} already complete and verified; no commands invoked.")
        return
    if stage == "capture" and any((OUT / "query_capture").glob("*.started.json")):
        # Do not collect/restart while a direct capture may still be writing.
        capture_ready()
        complete_stage(stage, adopted=True)
        print("Adopted completed direct capture; no calls invoked.")
        return
    if stage in ("snapshot", "retrieve"):
        capture_ready()
    if stage == "retrieve":
        snapshot_ready()
    if stage == "snapshot" and (OUT / "query_snapshot/manifest.json").exists():
        snapshot_ready()
        complete_stage(stage, adopted=True)
        print("Adopted completed direct snapshot; no embedding invoked.")
        return
    if stage == "snapshot" and (OUT / "query_snapshot/protocol.json").exists():
        raise ValueError("Snapshot was started but is incomplete; inspect it rather than retry")
    write_new(OUT / f"{stage}.started.json", {"started_utc": datetime.now(timezone.utc).isoformat(),
                                            "commands": plan["commands"][stage]})
    try:
        for i, cmd in enumerate(plan["commands"][stage]):
            print(f"{stage}: {i+1}/{len(plan['commands'][stage])}", flush=True)
            invoke(cmd, OUT / f"{stage}.{i:02d}.log")
        if stage == "capture":
            capture_ready()
        verify_plan(plan)
        complete_stage(stage, adopted=False)
    except Exception as exc:
        write_new(OUT / f"{stage}.failed.json", {"error": f"{type(exc).__name__}: {exc}",
                                               "policy": "Outputs and started markers preserved; no automatic retry."})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("prepare", "capture", "embed", "retrieve"),
                        help="One explicit stage; completed direct capture/embedding may be adopted without calls.")
    args = parser.parse_args()
    try:
        plan = prepare(OUT / "PROTOCOL.md")
        if args.stage != "prepare":
            run_stage("snapshot" if args.stage == "embed" else args.stage, plan)
        print("Prepared without model calls." if args.stage == "prepare" else "Requested stage completed.", flush=True)
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
