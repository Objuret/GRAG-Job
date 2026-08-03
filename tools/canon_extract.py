"""Extract genuinely human-authored user turns from Claude Code transcripts.

Streams the .jsonl session logs under one or more Claude Code project roots,
keeps the turns the human actually typed, and writes them verbatim alongside an
audit trail of what was rejected and why. Several machines' corpora can then be
merged into one chronological record.

    python tools/canon_extract.py
    python tools/canon_extract.py --sources DIR [DIR ...] --machine desktop \
        --name user_turns_desktop --no-sweep
    python tools/canon_extract.py --verify 15 --verify-floor 5 --name user_turns_desktop
    python tools/canon_extract.py --merge laptop=a.jsonl desktop=b.jsonl \
        --name user_turns_all

Rejection rules are named and ordered; every rejected turn records the first
rule that matched, so the filtering can be audited from the rejected sample.

Subagent transcripts (`<session>/subagents/agent-*.jsonl`) carry orchestrator
prompts in the `user` role, so they are dropped whole at discovery time and
counted separately.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

PROJECTS_ROOT = Path(r"C:\Users\jocke\.claude\projects")
DEFAULT_SOURCES = [
    PROJECTS_ROOT / "C--Coding-exjobbet-GRAG-Job-v3",
    PROJECTS_ROOT / "C--Coding-exjobbet-GRAG-Job",
]
DEFAULT_OUT = Path(r"C:\Coding\exjobbet\GRAG-Job\docs\canon\raw")
PROJECT_CWD_MARKERS = ("grag-job", "exjobbet")

# Transcript files that are not a human conversation, dropped whole.
SUBAGENT_DIR = "subagents"
JOURNAL_NAME = "journal.jsonl"

# Wrappers the client injects into an otherwise human turn. Stripped in place;
# a turn that is nothing but wrappers is rejected.
WRAPPER_RE = re.compile(
    r"<(ide_opened_file|ide_selection|system-reminder|local-command-caveat)>"
    r".*?</\1>\s*",
    re.DOTALL,
)

# Turns that are entirely a client/system artefact rather than typed input.
PREFIX_RULES = [
    ("task_notification", "<task-notification>"),
    ("command_expansion", "<command-name>"),
    ("command_expansion", "<command-message>"),
    ("command_expansion", "<command-args>"),
    ("command_expansion", "<local-command-stdout>"),
    ("command_expansion", "<bash-input>"),
    ("command_expansion", "<bash-stdout>"),
    ("hook_output", "<user-prompt-submit-hook>"),
    ("hook_output", "<session-start-hook>"),
    ("interrupt_marker", "[Request interrupted"),
    ("caveat_block", "Caveat: The messages below were generated"),
]

# Prompts emitted by the evaluation harness (RAGAS metric prompts, the tagger,
# the tag scorer, the query interpreter, the evidence walk) and by headless
# model-availability probes. Matched as (prefix, required substring or None).
HARNESS_TEMPLATES = [
    ("Given a question and an answer, analyze the complexity", None),
    ("Given a context, and an answer, analyze each sentence", None),
    ("Your task is to judge the faithfulness", None),
    ("Given a ground truth and an answer statements", None),
    ("Extract following from given question and ground truth", None),
    ("The output string did not satisfy the constraints", None),
    ("Documents:", None),
    ("Original query:", None),
    ("User query:", None),
    ("Question:", "Evidence so far"),
    ("Context:", "Reply ONLY JSON"),
    ("reply with exactly:", None),
]

PASTE_MIN_CHARS = 1500
PASTE_LINE_COUNT = 20
PASTE_LINE_CHARS = 600


def log(msg: str) -> None:
    print(msg, flush=True)


def message_text(obj: dict) -> tuple[str, bool]:
    """Return (joined text of human-visible blocks, saw_tool_result_block)."""
    message = obj.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content, False
    if isinstance(content, list):
        parts, tool_result = [], False
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text":
                parts.append(block.get("text", ""))
            elif kind == "tool_result":
                tool_result = True
        return "\n".join(parts), tool_result
    return "", False


def classify(obj: dict, in_headless_dir: bool = False) -> tuple[str | None, str]:
    """Return (rejection_rule or None, cleaned_text)."""
    raw, tool_result_block = message_text(obj)

    if "toolUseResult" in obj or tool_result_block:
        return "tool_result", raw
    if obj.get("isSidechain"):
        return "sidechain", raw
    if obj.get("isCompactSummary"):
        return "compact_summary", raw
    if obj.get("isMeta"):
        return "is_meta", raw

    stripped = raw.lstrip()
    for rule, prefix in PREFIX_RULES:
        if stripped.startswith(prefix):
            return rule, raw

    text = WRAPPER_RE.sub("", raw).strip()
    if not text:
        return ("wrapper_only" if raw.strip() else "empty"), raw

    if matches_harness_template(text):
        return "harness_template", text

    if in_headless_dir:
        return "headless_directory", text

    return None, text


def matches_harness_template(text: str) -> bool:
    for prefix, required in HARNESS_TEMPLATES:
        if text.startswith(prefix) and (required is None or required in text):
            return True
    return False


def is_paste(text: str) -> bool:
    if len(text) >= PASTE_MIN_CHARS:
        return True
    return text.count("\n") + 1 >= PASTE_LINE_COUNT and len(text) >= PASTE_LINE_CHARS


def iter_lines(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def collect_files(source: Path) -> tuple[list[Path], list[Path], Counter]:
    """Split a source tree into conversation transcripts and dropped files.

    Returns (conversation files, subagent files, drop counts by reason).
    """
    conversation: list[Path] = []
    subagents: list[Path] = []
    dropped: Counter = Counter()
    for path in sorted(source.rglob("*.jsonl")):
        parents = path.relative_to(source).parts[:-1]
        if path.name == JOURNAL_NAME:
            dropped["workflow_journal"] += 1
            continue
        if SUBAGENT_DIR in parents:
            dropped["subagent_transcript"] += 1
            subagents.append(path)
            continue
        conversation.append(path)
    return conversation, subagents, dropped


def measure_subagent_turns(files: list[Path]) -> dict:
    """Count what dropping the subagent transcripts actually removed."""
    stats = {"files": len(files), "records": 0, "user_turns": 0,
             "sidechain_records": 0, "would_have_been_kept": 0}
    for path in files:
        for obj in iter_lines(path):
            stats["records"] += 1
            if obj.get("isSidechain"):
                stats["sidechain_records"] += 1
            if obj.get("type") != "user":
                continue
            stats["user_turns"] += 1
            scratch = dict(obj)
            scratch.pop("isSidechain", None)
            if classify(scratch, False)[0] is None:
                stats["would_have_been_kept"] += 1
    return stats


def discover_sources(sources: list[Path], sweep: bool) -> list[Path]:
    found = [p for p in sources if p.is_dir()]
    if not sweep or not PROJECTS_ROOT.is_dir():
        return found
    known = {p.resolve() for p in found}
    for candidate in sorted(PROJECTS_ROOT.iterdir()):
        if not candidate.is_dir() or candidate.resolve() in known:
            continue
        for transcript in candidate.glob("*.jsonl"):
            hit = False
            for obj in iter_lines(transcript):
                cwd = (obj.get("cwd") or "").lower()
                if cwd and any(m in cwd for m in PROJECT_CWD_MARKERS):
                    hit = True
                    break
            if hit:
                log(f"  sweep: {candidate.name} references the project - included")
                found.append(candidate)
                break
    return found


def profile_sources(sources: list[Path], files_by_source: dict[Path, list[Path]]):
    """Pass 1 - measure each source directory's session shape.

    A directory where no session ever reaches a second human turn, across many
    sessions, holds one-shot programmatic calls rather than conversation. The
    test is measured rather than assumed, and the numbers behind it are printed
    and carried into the report.
    """
    profiles: dict[Path, dict] = {}
    total = sum(len(v) for v in files_by_source.values())
    done = 0
    for source in sources:
        candidates_per_session: Counter = Counter()
        templated = 0
        turns = 0
        for path in files_by_source[source]:
            done += 1
            if done % 250 == 0 or done == total:
                log(f"  pass 1/2  {done}/{total} files")
            for obj in iter_lines(path):
                if obj.get("type") != "user":
                    continue
                if "toolUseResult" in obj or obj.get("isMeta"):
                    continue
                session = obj.get("sessionId") or path.stem
                candidates_per_session[session] += 1
                turns += 1
                text, _ = message_text(obj)
                if matches_harness_template(WRAPPER_RE.sub("", text).strip()):
                    templated += 1
        n_sessions = len(candidates_per_session)
        max_turns = max(candidates_per_session.values(), default=0)
        rate = templated / turns if turns else 0.0
        headless = n_sessions >= 20 and max_turns <= 1 and rate >= 0.5
        profiles[source] = {
            "sessions": n_sessions,
            "turns": turns,
            "max_turns_per_session": max_turns,
            "template_rate": rate,
            "headless": headless,
        }
        verdict = "HEADLESS (all turns rejected)" if headless else "conversational"
        log(f"  {source.name}: {n_sessions} sessions, max {max_turns} human turn(s) "
            f"per session, {rate:.0%} templated -> {verdict}")
    return profiles


def extract(sources: list[Path], files_by_source: dict[Path, list[Path]],
            profiles: dict[Path, dict], machine: str | None, reject_examples: int):
    files = [p for s in sources for p in files_by_source[s]]
    kept: list[dict] = []
    rejected_examples: dict[str, list[dict]] = defaultdict(list)
    rules = Counter()
    seen_uuid: set[str] = set()
    seen_text: set[tuple[str, str]] = set()
    dupes = Counter()
    dupe_detail: list[dict] = []
    turns_seen = 0

    index = 0
    for source in sources:
        headless = profiles[source]["headless"]
        for path in files_by_source[source]:
            index += 1
            if index % 250 == 0 or index == len(files):
                log(f"  pass 2/2  {index}/{len(files)} files  kept={len(kept)}")
            for obj in iter_lines(path):
                if obj.get("type") != "user":
                    continue
                turns_seen += 1
                session = obj.get("sessionId") or path.stem
                rule, text = classify(obj, headless)

                if rule:
                    rules[rule] += 1
                    bucket = rejected_examples[rule]
                    if len(bucket) < reject_examples:
                        bucket.append(
                            {
                                "rule": rule,
                                "iso_timestamp": obj.get("timestamp"),
                                "session_file": path.name,
                                "char_len": len(text),
                                "text": text,
                            }
                        )
                    continue

                uuid = obj.get("uuid")
                if uuid and uuid in seen_uuid:
                    dupes["uuid"] += 1
                    dupe_detail.append({"key": "uuid", "uuid": uuid,
                                        "iso_timestamp": obj.get("timestamp"),
                                        "session_file": path.name,
                                        "text": text[:200]})
                    continue
                key = (obj.get("timestamp") or "", text)
                if key in seen_text:
                    dupes["timestamp_text"] += 1
                    dupe_detail.append({"key": "timestamp_text", "uuid": uuid,
                                        "iso_timestamp": obj.get("timestamp"),
                                        "session_file": path.name,
                                        "text": text[:200]})
                    continue
                if uuid:
                    seen_uuid.add(uuid)
                seen_text.add(key)

                row = {
                    "iso_timestamp": obj.get("timestamp"),
                    "session_file": path.name,
                    "session_id": session,
                    "uuid": uuid,
                    "cwd": obj.get("cwd"),
                    "git_branch": obj.get("gitBranch"),
                    "char_len": len(text),
                    "is_paste": is_paste(text),
                    "text": text,
                }
                if machine:
                    row["machine"] = machine
                kept.append(row)

    kept.sort(key=lambda r: (r["iso_timestamp"] or "", r["session_file"]))
    return kept, rules, rejected_examples, dupes, dupe_detail, turns_seen


def write_corpus(out: Path, name: str, kept: list[dict]) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    jsonl_path = out / f"{name}.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in kept:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    md_path = out / f"{name}.md"
    with md_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Human-authored user turns\n\n")
        handle.write(
            f"{len(kept)} turns, chronological. Verbatim text; no edits.\n\n---\n\n"
        )
        for row in kept:
            stamp = (row["iso_timestamp"] or "")[:16].replace("T", " ")
            origin = f" · {row['machine']}" if row.get("machine") else ""
            handle.write(f"## {stamp}{origin} · {row['session_file']}\n\n")
            if row["is_paste"]:
                handle.write(f"*paste / file drop · {row['char_len']} chars*\n\n")
            handle.write(row["text"].rstrip() + "\n\n")
    return jsonl_path, md_path


def write_rejected_sample(out: Path, suffix: str, rules, rejected_examples,
                          quota: int) -> Path:
    sample_path = out / f"rejected_sample{suffix}.md"
    order = sorted(rejected_examples, key=lambda r: -rules[r])
    picks: list[dict] = []
    while len(picks) < quota and order:
        for rule in list(order):
            bucket = rejected_examples[rule]
            if not bucket:
                order.remove(rule)
                continue
            picks.append(bucket.pop(0))
            if len(picks) >= quota:
                break
    with sample_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Rejected turns - audit sample\n\n")
        handle.write(
            f"{len(picks)} turns spread across every rule that fired, so the "
            "filtering can be checked by hand.\n\n"
        )
        for rule, count in rules.most_common():
            handle.write(f"- `{rule}` - {count} turns rejected\n")
        handle.write("\n---\n\n")
        for item in picks:
            stamp = (item["iso_timestamp"] or "")[:19].replace("T", " ")
            handle.write(f"## `{item['rule']}` · {stamp} · {item['session_file']}\n\n")
            body = item["text"][:1200]
            if len(item["text"]) > 1200:
                body += f"\n[... {item['char_len'] - 1200} more chars]"
            handle.write("```\n" + body.rstrip() + "\n```\n\n")
    return sample_path


MONTH_FLOOR = ("2026-05", "2026-06", "2026-07", "2026-08")


def month_table(handle, kept: list[dict]) -> None:
    counts = Counter((r["iso_timestamp"] or "")[:7] for r in kept)
    chars = Counter()
    for row in kept:
        chars[(row["iso_timestamp"] or "")[:7]] += row["char_len"]
    handle.write("| month | turns | characters |\n| --- | ---: | ---: |\n")
    for month in sorted(set(counts) | set(MONTH_FLOOR)):
        handle.write(f"| {month} | {counts.get(month, 0)} | {chars.get(month, 0):,} |\n")


def write_report(out: Path, suffix: str, kept, rules, dupes, dupe_detail, turns_seen,
                 files_by_source, sources, profiles, dropped_by_source,
                 subagent_stats, elapsed) -> Path:
    report_path = out / f"EXTRACT_REPORT{suffix}.md"
    sessions = {r["session_id"] for r in kept}
    total_chars = sum(r["char_len"] for r in kept)
    pastes = sum(1 for r in kept if r["is_paste"])
    with report_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Canon extraction report\n\n")
        handle.write(f"Generated by `tools/canon_extract.py` in {elapsed:.1f}s.\n\n")
        handle.write("## Sources\n\n")
        handle.write("| directory | conversation files | sessions "
                     "| max human turns/session | templated | verdict |\n")
        handle.write("| --- | ---: | ---: | ---: | ---: | --- |\n")
        for src in sources:
            pr = profiles[src]
            verdict = "headless harness" if pr["headless"] else "conversational"
            handle.write(
                f"| `{src.name}` | {len(files_by_source[src])} | {pr['sessions']} | "
                f"{pr['max_turns_per_session']} | {pr['template_rate']:.0%} "
                f"| {verdict} |\n"
            )
        handle.write(f"\nTotal conversation files scanned: "
                     f"**{sum(len(v) for v in files_by_source.values())}**\n\n")

        handle.write("## Files dropped whole at discovery\n\n")
        handle.write("| directory | subagent transcripts | workflow journals |\n")
        handle.write("| --- | ---: | ---: |\n")
        for src in sources:
            d = dropped_by_source[src]
            handle.write(f"| `{src.name}` | {d['subagent_transcript']} "
                         f"| {d['workflow_journal']} |\n")
        s = subagent_stats
        handle.write(
            f"\nThe {s['files']} subagent transcripts hold {s['records']:,} records, "
            f"{s['sidechain_records']:,} of them flagged `isSidechain`, including "
            f"**{s['user_turns']:,} turns in the `user` role**. Those are prompts an "
            f"orchestrator wrote to a subagent, not typed input. Run through the "
            f"human filter with the sidechain flag ignored, "
            f"**{s['would_have_been_kept']:,}** of them would have been kept - the "
            f"exact contamination the drop prevents.\n\n"
        )

        handle.write("## Counts\n\n")
        handle.write(f"- User-role turns seen: **{turns_seen}**\n")
        handle.write(f"- Kept as human-authored: **{len(kept)}**\n")
        handle.write(f"- Rejected: **{sum(rules.values())}**\n")
        handle.write(
            f"- Duplicates collapsed: **{sum(dupes.values())}** "
            f"(uuid {dupes['uuid']}, timestamp+text {dupes['timestamp_text']})\n"
        )
        handle.write(f"- Distinct sessions contributing kept turns: **{len(sessions)}**\n")
        handle.write(f"- Pastes / file drops flagged: **{pastes}**\n")
        handle.write(f"- Total kept characters: **{total_chars:,}**\n")
        if kept:
            handle.write(f"- Earliest kept turn: **{kept[0]['iso_timestamp']}**\n")
            handle.write(f"- Latest kept turn: **{kept[-1]['iso_timestamp']}**\n")
        handle.write("\n## Rejected per rule\n\n| rule | turns |\n| --- | ---: |\n")
        for rule, count in rules.most_common():
            handle.write(f"| `{rule}` | {count} |\n")
        if dupe_detail:
            handle.write("\n## Duplicates collapsed\n\n")
            for d in dupe_detail:
                handle.write(f"- `{d['key']}` {d['iso_timestamp']} "
                             f"{d['session_file']} - {d['text']!r}\n")
        handle.write("\n## Kept turns per month\n\n")
        month_table(handle, kept)
    return report_path


def merge(out: Path, name: str, corpora: list[str]):
    """Merge extracted corpora into one strictly chronological record.

    Each entry is `PATH` or `LABEL=PATH`; the label becomes the machine
    provenance for corpora extracted before the field existed.
    """
    rows: list[dict] = []
    per_source = Counter()
    for entry in corpora:
        label, _, raw_path = entry.rpartition("=")
        path = Path(raw_path)
        n = 0
        for line in path.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if label:
                row["machine"] = label
            row.setdefault("machine", path.stem)
            row["source_corpus"] = path.name
            rows.append(row)
            n += 1
        per_source[path.name] = n
        log(f"  {path.name} as `{row['machine']}`: {n} turns")

    rows.sort(key=lambda r: (r["iso_timestamp"] or "", r.get("machine") or "",
                             r["session_file"]))

    kept: list[dict] = []
    seen_uuid: set[str] = set()
    seen_text: set[tuple[str, str]] = set()
    collapsed: list[dict] = []
    for row in rows:
        uuid = row.get("uuid")
        key = (row["iso_timestamp"] or "", row["text"])
        if uuid and uuid in seen_uuid:
            collapsed.append({"key": "uuid", "uuid": uuid,
                              "iso_timestamp": row["iso_timestamp"],
                              "machine": row.get("machine"),
                              "session_file": row["session_file"],
                              "text": row["text"][:200]})
            continue
        if key in seen_text:
            collapsed.append({"key": "timestamp_text", "uuid": uuid,
                              "iso_timestamp": row["iso_timestamp"],
                              "machine": row.get("machine"),
                              "session_file": row["session_file"],
                              "text": row["text"][:200]})
            continue
        if uuid:
            seen_uuid.add(uuid)
        seen_text.add(key)
        kept.append(row)

    jsonl_path, md_path = write_corpus(out, name, kept)
    return kept, per_source, collapsed, jsonl_path, md_path


def append_merge_section(report: Path, kept, per_source, collapsed) -> None:
    machines = Counter(r.get("machine") for r in kept)
    sessions = {(r.get("machine"), r["session_id"]) for r in kept}
    with report.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n## Merged corpus (all machines)\n\n")
        handle.write("| source corpus | turns in | turns after merge |\n")
        handle.write("| --- | ---: | ---: |\n")
        for src, n in per_source.items():
            handle.write(f"| `{src}` | {n} | "
                         f"{sum(1 for r in kept if r['source_corpus'] == src)} |\n")
        handle.write(f"\n- Merged total: **{len(kept)}** turns\n")
        for machine, n in machines.most_common():
            handle.write(f"- `{machine}`: {n} turns\n")
        handle.write(f"- Distinct (machine, session) pairs: **{len(sessions)}**\n")
        handle.write(f"- Collapsed in the merge: **{len(collapsed)}**\n")
        if kept:
            handle.write(f"- Earliest: **{kept[0]['iso_timestamp']}** "
                         f"({kept[0].get('machine')})\n")
            handle.write(f"- Latest: **{kept[-1]['iso_timestamp']}** "
                         f"({kept[-1].get('machine')})\n")
        if collapsed:
            handle.write("\n### Collapsed entries\n\n")
            for c in collapsed:
                handle.write(f"- `{c['key']}` {c['iso_timestamp']} "
                             f"{c['machine']} {c['session_file']} - {c['text']!r}\n")
        handle.write("\n### Merged turns per month\n\n")
        month_table(handle, kept)


def verify(out: Path, name: str, sources: list[Path], count: int, floor: int) -> int:
    """Re-read random kept turns from their source file and compare byte-wise."""
    rows = [json.loads(l) for l in (out / f"{name}.jsonl").open(encoding="utf-8")]
    if not rows:
        log("nothing to verify")
        return 1
    random.seed(20260803)
    picks = random.sample(rows, min(count, len(rows)))
    chosen = {r["uuid"] for r in picks}
    if floor:
        by_month: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_month[(row["iso_timestamp"] or "")[:7]].append(row)
        for month in sorted(by_month):
            have = sum(1 for r in picks
                       if (r["iso_timestamp"] or "").startswith(month))
            pool = [r for r in by_month[month] if r["uuid"] not in chosen]
            random.shuffle(pool)
            while have < floor and pool:
                extra = pool.pop()
                picks.append(extra)
                chosen.add(extra["uuid"])
                have += 1
    picks.sort(key=lambda r: r["iso_timestamp"] or "")

    wanted_names = {r["session_file"] for r in picks}
    by_uuid = {r["uuid"]: r for r in picks}
    found: dict[str, dict] = {}
    for src in sources:
        if not src.is_dir():
            continue
        conversation, _, _ = collect_files(src)
        for path in conversation:
            if path.name not in wanted_names:
                continue
            for obj in iter_lines(path):
                uuid = obj.get("uuid")
                if uuid in by_uuid and uuid not in found:
                    _, text = classify(obj, False)
                    found[uuid] = {"text": text, "timestamp": obj.get("timestamp")}
    ok = 0
    for row in picks:
        src = found.get(row["uuid"])
        if not src:
            log(f"  MISSING  {row['uuid']}  {row['iso_timestamp']}")
            continue
        text_ok = src["text"] == row["text"]
        ts_ok = src["timestamp"] == row["iso_timestamp"]
        if text_ok and ts_ok:
            ok += 1
            log(f"  OK  {row['iso_timestamp']}  {row['char_len']:>6} chars  "
                f"{row['session_file'][:12]}")
        else:
            log(f"  FAIL text={text_ok} ts={ts_ok}  {row['uuid']}")
    per_month = Counter((r["iso_timestamp"] or "")[:7] for r in picks)
    log(f"\nverified {ok}/{len(picks)} byte-identical with matching timestamps")
    log("by month: " + ", ".join(f"{m}={n}" for m, n in sorted(per_month.items())))
    return 0 if ok == len(picks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--name", default="user_turns",
                        help="output corpus stem; report and sample names follow it")
    parser.add_argument("--machine", default=None,
                        help="provenance label written onto every kept turn")
    parser.add_argument("--no-sweep", action="store_true",
                        help="skip scanning other project dirs for this project's cwd")
    parser.add_argument("--reject-examples", type=int, default=12,
                        help="rejected turns retained per rule for the audit sample")
    parser.add_argument("--reject-quota", type=int, default=40,
                        help="rejected turns written to the audit sample")
    parser.add_argument("--merge", nargs="+", metavar="[LABEL=]JSONL",
                        help="merge extracted corpora into one chronological record")
    parser.add_argument("--append-report", type=Path, metavar="MD",
                        help="append the merge summary to this report")
    parser.add_argument("--verify", type=int, metavar="N",
                        help="re-read N random kept turns against source and exit")
    parser.add_argument("--verify-floor", type=int, default=0, metavar="K",
                        help="also verify at least K turns from every month present")
    args = parser.parse_args()

    suffix = (args.name[len("user_turns"):] if args.name.startswith("user_turns")
              else "_" + args.name)

    log("=" * 66)
    log("  canon_extract - human user turns from Claude Code transcripts")
    log("=" * 66)

    if args.verify:
        log(f"\nverifying {args.verify} random kept turns against source files")
        if args.verify_floor:
            log(f"  plus a floor of {args.verify_floor} per month present")
        log("")
        return verify(args.out, args.name, list(args.sources), args.verify,
                      args.verify_floor)

    if args.merge:
        started = time.time()
        log(f"\nmerging {len(args.merge)} corpora")
        kept, per_source, collapsed, jsonl_path, md_path = merge(
            args.out, args.name, list(args.merge))
        log(f"\n  merged {len(kept)} turns, collapsed {len(collapsed)}")
        for path in (jsonl_path, md_path):
            log(f"  {path.name}  {path.stat().st_size:,} bytes")
        if args.append_report:
            append_merge_section(args.append_report, kept, per_source, collapsed)
            log(f"  appended merge summary to {args.append_report.name}")
        log(f"done in {time.time() - started:.1f}s")
        return 0

    started = time.time()
    log("\nresolving sources...")
    sources = discover_sources(list(args.sources), sweep=not args.no_sweep)
    files_by_source: dict[Path, list[Path]] = {}
    dropped_by_source: dict[Path, Counter] = {}
    subagent_files: list[Path] = []
    files: list[Path] = []
    for src in sources:
        conversation, subs, dropped = collect_files(src)
        files_by_source[src] = conversation
        dropped_by_source[src] = dropped
        subagent_files.extend(subs)
        log(f"  {src.name}: {len(conversation)} conversation files, "
            f"{dropped['subagent_transcript']} subagent transcripts dropped, "
            f"{dropped['workflow_journal']} workflow journals dropped")
        files.extend(conversation)
    if not files:
        log("no transcripts found")
        return 1

    log(f"\nmeasuring the {len(subagent_files)} dropped subagent transcripts")
    subagent_stats = measure_subagent_turns(subagent_files)
    log(f"  {subagent_stats['user_turns']} user-role turns excluded, "
        f"{subagent_stats['would_have_been_kept']} of which would have passed "
        f"the human filter")

    log(f"\nprofiling {len(files)} transcript files")
    profiles = profile_sources(sources, files_by_source)
    kept, rules, examples, dupes, dupe_detail, turns_seen = extract(
        sources, files_by_source, profiles, args.machine, args.reject_examples)

    log(f"\nwriting outputs to {args.out}")
    jsonl_path, md_path = write_corpus(args.out, args.name, kept)
    sample_path = write_rejected_sample(args.out, suffix, rules, examples,
                                        args.reject_quota)
    report_path = write_report(args.out, suffix, kept, rules, dupes, dupe_detail,
                               turns_seen, files_by_source, sources, profiles,
                               dropped_by_source, subagent_stats,
                               time.time() - started)
    for path in (jsonl_path, md_path, sample_path, report_path):
        log(f"  {path.name}  {path.stat().st_size:,} bytes")

    log(f"\nkept {len(kept)} human turns "
        f"({sum(r['char_len'] for r in kept):,} chars) "
        f"from {len({r['session_id'] for r in kept})} sessions")
    log(f"rejected {sum(rules.values())}, collapsed {sum(dupes.values())} duplicates")
    log(f"done in {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
