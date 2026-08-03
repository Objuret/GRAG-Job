---
name: neo4j-data-location
description: "Neo4j data lives on A:\\Coding\\neo4j\\, not the default C:\\.Neo4jDesktop2 location; herb-eval-backup sibling DB and herb-eval.dump recovery artifact both exist"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4f97e452-4e72-42d8-8205-39b98fa75d71
---

Neo4j Desktop 2 instance `dbms-06f669f3-a00f-4170-9cad-ffb65fb1c612` has its data dir relocated to `A:\Coding\neo4j\data\` via `server.directories.data` in `neo4j.conf`. Conf/binaries/logs still live in the default `C:\Users\Djuret\.Neo4jDesktop2\Data\dbmss\dbms-06f669f3-…\`. The subdir settings (transactions, dumps, cluster-state, scripts) default to subdirs of `data`, so they follow automatically.

**Why:** The user explicitly does not want graph data on C:. Don't assume defaults; don't suggest moves to default paths.

**Sibling DBs and backup state** (as of 2026-05-25):
- `herb-eval` — canonical artefact (per [[herb-eval-is-the-artefact]])
- `herb-eval-backup` — queryable sibling, byte-identical clone of herb-eval pre any tag-cleanup work
- `A:\Coding\neo4j\backups\herb-eval.dump` — portable recovery artifact (528 MB compressed). Loadable into any database name via `neo4j-admin database load --database=<target> --from-path=A:\Coding\neo4j\backups`. Load requires `<target>.dump` filename, so rename/copy the dump to `<target>.dump` before loading into a non-`herb-eval` target.
- Other DBs in the instance: `bonnier`, `lab4`, `herb` (contaminated — do not query), `neo4j` (default, empty/unused), `system`.

**How to apply:**
- For any `SHOW SETTINGS` / data-path question, the answer involves A:\, not C:\.
- For comparisons between "before tag cleanup" and "after," query `herb-eval-backup` for the before state.
- For full disaster recovery, use the dump file with `neo4j-admin database load`.
- The `neo4j-admin.bat` is at `C:\Users\Djuret\.Neo4jDesktop2\Data\dbmss\dbms-06f669f3-…\bin\neo4j-admin.bat`.
