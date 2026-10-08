# The model calls: what was found, what was fixed (2026-10-08)

His words that set this: *"We agreed to use the headless mode, constructed, all of that garbage
off"* · *"obviously we need to make sure that shit is also done correctly then"* (on the judge
calls, after RAGAS's own docs were read) · *"well, document, fix what can be fixed, document,
push"* (2026-10-08).

Every statement below was seen in a request the CLI sent, logged with the CLI's own request
logging (`OTEL_LOG_RAW_API_BODIES=file:<dir>`), on the made-up question of
`output/walkthrough/20261005T040000Z/walkthrough.json`. No test question was used. The scripts
and prints are on the laptop under `output/research/2026-10-08-baseline-review/` (`probes/`,
`proof_now/`); that folder is not in git, and the logged requests in it hold account ids.

CLI: `claude` 2.1.212, called as `claude -p --model <id> --output-format json --tools ""
--safe-mode [--system-prompt <text>] [--json-schema <schema>]`, prompt on stdin.

## 1. Found

What a call carried that the harness had not written, and what the harness asked for that was
not applied. "Answer call" is the generator's call (the artefact's query-side calls go the same
way); "judge call" is a call RAGAS makes through `prod/eval/ragas.py`.

| # | Found | Calls |
|---|---|---|
| 1 | The whole prompt was sent a second time, to Haiku, for a session title. | all |
| 2 | A billing line stood first in the system prompt. | all |
| 3 | Every line end reached the CLI as CR LF (Python text mode on Windows), so the prompt kept in a row was not the bytes sent. | all |
| 4 | The line "You are a Claude agent, built on Anthropic's Claude Agent SDK." stood in front of the system text. | all |
| 5 | A `<system-reminder>` block with the account's e-mail address and the day's date stood in front of the prompt in the user message. | all |
| 6 | Thinking was on (the model decides), though the harness asks for it off. | answer |
| 7 | Up to 64,000 output tokens were allowed, though the harness asks for 8,192. | answer |
| 8 | Effort was `medium`, taken from the user's own `~/.claude/settings.json`; the model's default is `high`; the harness passed none and recorded none. | answer |
| 9 | Temperature 0, which the harness asks for, was never sent. | answer |
| 10 | The run manifest listed temperature 0, 8,192 tokens and thinking off as what every answer call is given. | answer |
| 11 | Claude Code's own default system prompt went along, about 15,400 characters, with a per-call scratchpad path and the machine's environment in it, because the harness passed no system text. | judge |
| 12 | Thinking was on with a budget of 31,999 tokens, and no temperature was sent (so 1), where RAGAS hands its judge 0.01. | judge |
| 13 | The alias `claude-haiku-4-5` was passed, not the dated id it resolves to. | judge |

Where the numbers come from: a 33-character judge prompt cost 3,649 input tokens (item 11); the
answer call for a 72,500-character prompt was 25,508 Sonnet tokens beside 17,541 Haiku tokens
for the title (item 1); the CLI's own transcripts of the two baseline runs of 10-07 show effort
`medium` on all 200 answer calls and a thinking block in 72 and 77 of the 100 (items 6, 8).

What RAGAS itself sets for a judge it builds (read in RAGAS 0.4.3, `ragas/llms/base.py` and its
docs): temperature 0.01 for a score that asks for one reply, top_p 0.1, 1,024 output tokens, no
system prompt, and it tells the user to pin the exact model snapshot. Our three judged scores
each ask for one reply.

## 2. Fixed

The lane is `prod/harness/chat.py`: `call_settings(payload)` builds the argv and the environment
variables of one call and says which of the caller's settings they carry (`applied`) and which
they cannot (`not_applied`, with the reason). Both are kept in every call's record and, once per
run, in the manifest (`generator`, and `judge_call` in the evaluation's settings).

| # | What the lane does now | Seen |
|---|---|---|
| 1 | `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` on every call. | One request per call in the log; the CLI's envelope names one model. |
| 2 | `CLAUDE_CODE_ATTRIBUTION_HEADER=0` on every call. | The system prompt holds the identity line and the harness's text, nothing else. |
| 3 | The prompt is handed to the CLI as UTF-8 bytes. | The prompt in the request equals the prompt kept in the record, byte for byte, no CR. |
| 4 | Not fixed. The CLI has no switch for it. | Still first in the system prompt. |
| 5 | The e-mail line is gone since 2026-10-09; the date line cannot be removed. See "The block in front of the prompt" below. | The block holds the date alone: 306 characters (was 365). |
| 6 | `MAX_THINKING_TOKENS=0` on a call that asks for thinking off. | `thinking: disabled` in the request; the CLI's transcript of the call holds the answer block and no thinking block. |
| 7 | `CLAUDE_CODE_MAX_OUTPUT_TOKENS=<the cap>` on a call that asks for thinking off. | `max_tokens: 8192` in the request. |
| 8 | `--effort <level>` when the caller names one; otherwise `CLAUDE_CODE_EFFORT_LEVEL=auto`, so none is sent and the user's settings file is not read for it. | `output_config: null` in the request. |
| 9 | Cannot be fixed. `claude-sonnet-5` answers 400 "`temperature` is deprecated for this model" to any temperature, thinking on or off. | Each answer call's record: `not_applied.temperature`. |
| 10 | The manifest's `generator` holds what is asked (`payload`), `applied`, `not_applied` and the variables set. | `applied`: effort none sent, thinking off, 8,192; `not_applied`: temperature, min_tokens. |
| 11 | `--system-prompt` is always passed, empty when the call has no system text. | The judge's system prompt is the identity line alone; a 33-character prompt costs 128 input tokens (was 3,649). |
| 12 | The judge call asks for thinking off and passes the temperature RAGAS hands its judge for that call, through `CLAUDE_CODE_EXTRA_BODY`. | `thinking: disabled`, `temperature: 0.01` in the request. |
| 13 | The default judge is `claude-haiku-4-5-20251001`. | Accepted. In the CLI's transcripts every Haiku call of every day since 2026-09-08 was answered by this snapshot, so the id names the model the alias already gave. |

A switch of the four per-call ones (`CLAUDE_CODE_EFFORT_LEVEL`, `MAX_THINKING_TOKENS`,
`CLAUDE_CODE_MAX_OUTPUT_TOKENS`, `CLAUDE_CODE_EXTRA_BODY`) that a call does not set is taken out
of the CLI's environment, so a value left in the shell that starts a run does not reach a call.
The request came out the same, apart from its `metadata`, when the call was started from an
agent's shell and from a shell with every `CLAUDE*` variable taken away.

The cap and the temperature go along only on a call that asks for thinking off: with thinking on
the API takes no temperature but 1, and a cap would count the thinking. On such a call they are
recorded as not applied.

### The judge against what RAGAS sets

RAGAS hands a custom judge one setting per call, the temperature (0.01 for one reply, 0.1 from
its three NV scores, 0.3 when it asks for several replies). That is passed on. `top_p` 0.1 and
the 1,024-token cap are defaults of a judge RAGAS builds itself, which ours is not: `top_p` is
not sent because `claude-haiku-4-5` answers 400 to a temperature together with a `top_p`; the
cap stays the CLI's own for this model, 32,000, and a judge reply of 1,078 tokens was seen in the
proof below. One try per judge call, as before; the number stored and printed is now that one
(it said 2). A reply with no text in it is asked for again, up to three times in all, as before;
that number is now stored too.

RAGAS reports a usage event to its makers for every score it computes (the score's name, the
row count, the language, the RAGAS version and a random id kept on this machine; no text). The
evaluation now sets `RAGAS_DO_NOT_TRACK=true` unless the variable is already set.

### The block in front of the prompt

Read in the CLI's own code (2.1.212): the block is built from the user's CLAUDE.md (off under
`--safe-mode`), the e-mail address of the login stored in `~/.claude.json`, and the day's date.
The date is added without condition, so no switch removes the block. The e-mail address is left
out when the CLI has no stored login to read: tried with the CLI given its own empty config
folder (`CLAUDE_CONFIG_DIR`) and the login token that `.env` holds (`CLAUDE_CODE_OAUTH_TOKEN`);
the request was the same apart from the missing e-mail section.

Built into the lane on 2026-10-09 (his *"yeah, thats fine, go ahead then"*, on the login change):
every call runs with `CLAUDE_CONFIG_DIR` set to `~/.claude-herb-lane` and logs in with the
`CLAUDE_CODE_OAUTH_TOKEN` of the environment, which `.env` supplies. A call without the token is
refused; there is no second way in. The token's value is never written anywhere by the harness:
the manifest's `env` shows it as `<set>`. The folder gets a `settings.json` with
`cleanupPeriodDays` 36500, so the CLI keeps its own transcripts of the calls; those now land
under `~/.claude-herb-lane/projects/` and hold gold like the earlier ones. No settings file of
the user's is read any more. Seen in a logged request made through the lane: the block in front
of the prompt holds the date alone.

`lane_info()` (in every manifest) names the two things the CLI still adds by itself, the
identity line and the date, with the CLI version they were seen with. The date makes a call's
input differ from one day to the next.

### The run's record

- An evaluation start keeps the rows of scores it does not compute. Before, a `--retrieval-only`
  start on a judged folder rewrote `eval_results.jsonl` without its judged rows.
- The code version and the code state are read before a start answers anything, and the same
  values go into the start's entry and the manifest. The diff is saved as git's own bytes: the
  file's sha256 is the recorded one.
- The evaluation's manifest keeps the judge's name when a later start makes no judge call.
- The manifest's `env` lists every variable the CLI can read (`CLAUDE*`, `ANTHROPIC_*`,
  `MAX_THINKING*`, `DISABLE_*`, `OTEL_*`), a secret as `<set>`; `environment.packages_all` lists
  every installed package with its version.

### Proof

`pytest prod/tests`: 142 passed, none skipped (`prod/tests/test_lane_settings.py` is new).

Fourteen model calls, all on the made-up question, 2026-10-08 21:41–21:48Z: five to
`claude-sonnet-5` (56,808 tokens in, 1,907 out) and nine to `claude-haiku-4-5-20251001`
(46,316 in, 2,577 out).

- Six with the CLI's request logging on, argv and environment taken from `call_settings`: an
  answer call and a judge call from an agent's shell, from a shell without the `CLAUDE*`
  variables, and with the CLI's own config folder and the token (`probes/probe3.py`).
- The harness itself, `orchestrator.run`, twice into each folder (`proof_now/proof_now.py`):
  lucene with the answer call (25,508 tokens in, 378 out, one request); vector with the answer
  call (28,368 in, 355 out) and the whole evaluation (6 judge calls, 45,951 in, 2,565 out, 14 of
  14 scores ok). The second start of each folder added its entry and changed nothing else.

### What changes for calls made from now on

- Every call through the lane, the artefact's too: no title request, no billing line, line ends
  as written, and effort is no longer `medium` from the settings file (none is sent unless the
  caller names one; the CLI itself sends `high` for `claude-sonnet-5` when no setting names one).
- The answer call: thinking off and at most 8,192 tokens out. In the stored baseline runs of
  2026-10-07 thinking was on, with a thinking block in 72 and 77 of the 100 answers.
- The judge call: no system prompt of Claude Code's, thinking off, temperature 0.01. The stored
  evaluations of 2026-10-07 were judged with that system prompt and thinking on, and no
  temperature was sent.

### Left

- The identity line (4), the date line (5), the generator's temperature (9).
- `top_k` in the manifest is the k handed to the arm. Under a character budget lucene and vector
  rank every unit and do not read it; whether each older artefact arm reads it was not checked.
- Answers are written in question order: a finished answer waits for the ones before it and is
  lost if the process dies first (the CLI's transcript of its call remains). Writing each as it
  finishes changes the order of the rows in `arm_outputs.jsonl`.
- Nine tools under `tools/` (`facet_*`, the facet measurements of September) start the CLI
  themselves, not through the lane, and get none of the above. No run path uses them.
- Nothing stops a start under another Python; the manifest now names the interpreter and every
  package.
- The order among equal BM25 scores is the library's own. What a baseline unit's text holds
  was settled on 2026-10-09: `docs/2026-10-09-baseline-unit-text.md`.
