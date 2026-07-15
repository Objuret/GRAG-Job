# herb-eval.dump

Neo4j dump of `herb-eval`, the superseded artefact graph (`artefact_v1`'s
forensic-contrast baseline — see root `CLAUDE.md`). Not the current native
pass-1 graph (`herb-v3`), which isn't built yet.

Restore on any machine with Neo4j installed:

```
neo4j-admin database load herb-eval --from-path=<dir containing this file>
```

Then start the database and set `NEO4J_URI` / `NEO4J_PASSWORD` for whichever
arm reads it (`pipelines/artefact_v1.py`).
