"""PROBES, second round: what each documented switch does to the request the CLI sends.

Direct CLI calls with the lane's own argv, working directory and stdin handling, request logging on,
plus the ONE thing each probe names. Made-up question only. Nothing under prod/ is changed. The system
text used on judge-shaped probes is a placeholder marked as such, not a proposal.

    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/probes/probe2.py <name> [<name> ...]
    .venv/Scripts/python.exe output/research/2026-10-08-baseline-review/probes/probe2.py --show
"""
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe as P  # noqa: E402  (the first round's caller; it also sets stdout to UTF-8)

SONNET, HAIKU = P.orchestrator.GENERATOR_MODEL, "claude-haiku-4-5"
ANS = dict(model=SONNET, prompt=P.ANSWER_PROMPT, system=P.GENERATOR_SYSTEM, schema=P.orchestrator._ANSWER_SCHEMA)
JUD = dict(model=HAIKU, prompt=P.JUDGE_PROMPT)
PLACEHOLDER = "PROBE PLACEHOLDER SYSTEM TEXT."
TITLE_OFF = {"CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1"}

PROBES = {
    # answer-shaped, one switch each
    "a_attribution_off": dict(ANS, env_add={"CLAUDE_CODE_ATTRIBUTION_HEADER": "0"}),
    "a_attachments_off": dict(ANS, env_add={"CLAUDE_CODE_DISABLE_ATTACHMENTS": "1"}),
    "a_demo": dict(ANS, env_add={"IS_DEMO": "1"}),
    "a_thinking_off": dict(ANS, env_add={"MAX_THINKING_TOKENS": "0"}),
    "a_effort_flag_high": dict(ANS, extra=("--effort", "high")),
    "a_effort_env_auto": dict(ANS, env_add={"CLAUDE_CODE_EFFORT_LEVEL": "auto"}),
    "a_claude_mds_off": dict(ANS, env_add={"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"}),
    # judge-shaped, one switch each
    "j_system_placeholder": dict(JUD, system=PLACEHOLDER),
    "j_system_empty": dict(JUD, extra=("--system-prompt", "")),
    "j_thinking_off": dict(JUD, env_add={"MAX_THINKING_TOKENS": "0"}),
    "j_temp_with_thinking": dict(JUD, env_add={"CLAUDE_CODE_EXTRA_BODY": '{"temperature": 0.01}', **TITLE_OFF}),
    "j_temp_thinking_off": dict(JUD, env_add={"CLAUDE_CODE_EXTRA_BODY": '{"temperature": 0.01}',
                                              "MAX_THINKING_TOKENS": "0", **TITLE_OFF}),
    # RAGAS's own pass-through for an Anthropic judge: temperature 0.01 AND top_p 0.1, no thinking
    "j_ragas_defaults": dict(JUD, extra=("--system-prompt", ""), binary=True,
                             env_add={"CLAUDE_CODE_ATTRIBUTION_HEADER": "0", "MAX_THINKING_TOKENS": "0",
                                      "CLAUDE_CODE_EXTRA_BODY": '{"temperature": 0.01, "top_p": 0.1}',
                                      **TITLE_OFF}),
    # the harness's own intent for the generator (orchestrator.py: temperature 0, thinking off, 8192 out)
    "a_thinking_off_temp0": dict(ANS, binary=True,
                                 env_add={"MAX_THINKING_TOKENS": "0", "CLAUDE_CODE_EXTRA_BODY": '{"temperature": 0}',
                                          "CLAUDE_CODE_ATTRIBUTION_HEADER": "0", **TITLE_OFF}),
    "a_thinking_off_max8192": dict(ANS, binary=True,
                                   env_add={"MAX_THINKING_TOKENS": "0", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "8192",
                                            "CLAUDE_CODE_ATTRIBUTION_HEADER": "0", **TITLE_OFF}),
    # everything that worked, together
    # effort is pinned by the flag here only to show the pin; which level is his to say
    "a_all": dict(ANS, extra=("--effort", "high"), binary=True,
                  env_add={"CLAUDE_CODE_ATTRIBUTION_HEADER": "0", **TITLE_OFF}),
    # an empty system text, thinking off, and the temperature RAGAS itself passes (0.01)
    "j_all": dict(JUD, extra=("--system-prompt", ""), binary=True,
                  env_add={"CLAUDE_CODE_ATTRIBUTION_HEADER": "0", "MAX_THINKING_TOKENS": "0",
                           "CLAUDE_CODE_EXTRA_BODY": '{"temperature": 0.01}', **TITLE_OFF}),
}


def show():
    for name in ["answer_logged", "judge_logged"] + list(PROBES):
        d = HERE / name / "bodies"
        if not d.is_dir():
            continue
        reqs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.request.json"),
                                                                           key=lambda p: p.stat().st_mtime)]
        main = [b for b in reqs if "title" not in json.dumps(b.get("output_config") or {})]
        titles = len(reqs) - len(main)
        call = None
        for line in (HERE / "calls_made.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["probe"] == name:
                call = r
        rc = call["returncode"] if call else None
        if not main:
            err = (HERE / name / "stdout.txt").read_text(encoding="utf-8")[:300] if (HERE / name / "stdout.txt").is_file() else ""
            print(f"{name}: no main request logged | returncode {rc} | title requests {titles} | stdout {err!r}")
            continue
        for b in main:
            sysb = b.get("system") or []
            sys_desc = [f"{len(x.get('text', ''))}:{x.get('text', '')[:34]!r}" for x in sysb] if isinstance(sysb, list) else [f"str:{len(sysb)}"]
            msg = b["messages"][0]["content"]
            blocks = msg if isinstance(msg, list) else [{"text": msg}]
            usr_desc = [f"{len(x.get('text', ''))}:{x.get('text', '')[:24]!r}" for x in blocks]
            reminder = next((x.get("text", "") for x in blocks if "<system-reminder>" in x.get("text", "")), "")
            print(f"{name}: returncode {rc} | model {b['model']} | thinking {json.dumps(b.get('thinking'))} | "
                  f"output_config {json.dumps(b.get('output_config'))} | temperature {b.get('temperature', '(not sent)')} | "
                  f"max_tokens {b.get('max_tokens')} | tools {[t['name'] for t in b.get('tools') or []]} | title requests {titles}")
            print(f"      system blocks {sys_desc}")
            print(f"      user blocks {usr_desc} | reminder holds e-mail: {'userEmail' in reminder} date: {'currentDate' in reminder}")
        if call:
            print(f"      main call tokens in {call['usage']['input_tokens']} (+cache {call['usage']['cache_creation_input_tokens']}/{call['usage']['cache_read_input_tokens']}) out {call['usage']['output_tokens']} | result chars {call['result_chars']} | session {call['session_id']}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--show"]:
        show()
    else:
        print(f"CLI: {P.chat.cli_version()}")
        for n in sys.argv[1:]:
            kw = dict(PROBES[n])
            print(f"\n===== probe {n}: extra flags {kw.get('extra', ())} extra env {sorted((kw.get('env_add') or {}).items())}")
            try:
                P.call(n, kw.pop("model"), kw.pop("prompt"), logged=True, **kw)
            except Exception as e:  # a probe that the CLI refuses is a finding, not a crash
                print(f"   probe {n} raised {type(e).__name__}: {str(e)[:300]}")
