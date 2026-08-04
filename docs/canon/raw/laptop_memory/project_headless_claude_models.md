---
name: headless-claude-models
description: "Verified headless claude CLI models on the laptop (2026-07-17) — path, aliases, resolved IDs, gotchas"
metadata: 
  node_type: memory
  type: project
  originSessionId: fe03b6a9-1a33-4d9b-a32a-449696ebd9f1
---

Headless Claude Code CLI on this laptop (verified 2026-07-17, CLI v2.1.212):

- **Binary:** `C:\Users\jocke\.local\bin\claude.exe` — NOT on PATH in agent tool
  shells (bash/PowerShell); call by full path. `v3/eval/ragas.py` already handles
  this: `shutil.which("claude") or ~/.local/bin/claude.exe`.
- **Invocation:** `claude.exe -p "<prompt>" --model <alias> --output-format json`
  (subscription-billed; the RAGAS `claude-*` judge path in `v3/eval/ragas.py`).
- **Structured output IS supported:** `--json-schema '<schema>'` enforces a JSON
  Schema on the response (verified in `--help`, CLI 2.1.212). The generator's
  `{"answer": str}` contract and the judge verdict can both be schema-enforced —
  fence-stripping is a workaround, not a necessity. No temperature flag exists;
  reproducibility is the CLI's one real gap vs NIM.
- **All four aliases verified working:**
  - `haiku` → claude-haiku-4-5-20251001 (200k ctx, 32k out)
  - `sonnet` → claude-sonnet-5 (1M ctx, 64k out)
  - `opus` → claude-opus-4-8 (1M ctx, 64k out)
  - `fable` → claude-fable-5 (1M ctx, 64k out)
- **Gotcha:** `--bare` skips keychain reads → "Not logged in" error. Never combine
  `--bare` with a real model call here.
- **Gotcha:** headless reads stdin; redirect (`< /dev/null` or pass text on stdin)
  to avoid a 3s stall.

Related: [[laptop-env-limits]]
