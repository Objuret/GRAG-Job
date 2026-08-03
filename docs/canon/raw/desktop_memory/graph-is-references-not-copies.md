---
name: graph-is-references-not-copies
description: Core design — the graph indexes references into sacred untouched raw source; it does not store mutated copies of content
metadata: 
  node_type: memory
  type: project
  originSessionId: 9a32f7a1-4794-4c83-a79e-bacf02c56af1
---

**The graph is an index of references over the raw source. It does NOT hold copies of the data, and especially not mutated/rendered copies.**

The user stated this directly (2026-05-30) as the reason they never wanted content loaded into the graph in the first place: "thats the fucking reason i dont even want the data loaded into the goddamn graph, thats why i just want the fucking references."

## The model

- **Raw source files are authoritative and untouched.** They are the single source of truth.
- **The graph stores references** — `file_id` + a real, resolvable location into the raw file (byte span, or a structural path like a JSONPath) — plus the derived semantic layer (tags, weights, grounding vectors).
- **Content is resolved on demand** by reading the referenced span from the untouched source. The graph never becomes a second copy that silently replaces the original.
- Tags / weights / vectors attach to the *reference*. Nothing the pipeline does can mutate or lose the original, because the pipeline only ever points at it.

## Why this matters / the root failure it fixes

The current chunker does the opposite: it consumes the source, renders it into a prose string, stores the string as `c.content`, and that lossy derivative becomes the only surviving copy. The source structure is gone; the data was used as raw material for a fabrication.

**Concrete proof the current code violates the reference model:** chunks are supposed to carry `start_offset`/`end_offset` as a reference into the source. The JSONL path uses real byte offsets into the file. But the HERB path writes every chunk with `start_offset=0, end_offset=len(content)` ([backend/indexing/chunker.py](../../../../../exjobbet/repo/backend/indexing/chunker.py) `_chunk_herb_json`, ~line 274-284), where `content` is the rendered prose the chunker fabricated. The offsets locate a position inside the fabrication, not inside the raw file. There is no path back to source.

This is the deeper layer under the truncation/clamp problem ([[no-silent-fallbacks]]) and the hard-fields problem ([[design-hard-fields-before-tagging]]): the pipeline never adopted "preserve the source, derive everything else." It mutates the only copy. Truncation (generic JSON path caps arrays at 50, truncates strings — silent, lossy) is just the loudest symptom.

## The reference triple (decided 2026-05-30)

A reference is `{file_id, scheme, address}`. The resolver turns it into exact source content on demand. `scheme` is chosen by data shape (the shape probe picks it):
- nested JSON → `json_pointer` (RFC 6901), e.g. `/slack/42/Message/User/text` — stable against reformatting, unlike byte offsets
- long text leaf → `json_pointer` to the field + `char_span` [start,end] within the resolved value
- flat text / markdown → `char_span` (or byte span) into the file
- tabular (parquet/csv) → `row` index (+ column)
- binary/image → reference only, no content resolution

**Rendering moves, it doesn't disappear.** The LLM tagger still needs text, but the rendered prose is a TRANSIENT view computed on demand by resolving the reference, used as tagger input, and discarded. It is never stored as the authoritative record. `c.content` as a stored mutated blob stops existing.

## Resolution model — read from disk in place (decided 2026-05-30, option 1)

- Raw files stay on disk under a configurable `data_root`; graph references them by relative path.
- **Identity is the content hash, not the path** — preflight already computes `sha256` per file and `file_id = sha256[:24]`.
- **Verify the hash on resolve; fail loud on mismatch** ([[no-silent-fallbacks]]). If the on-disk file no longer matches the hash the graph was built against, resolution stops — it does not serve drifted content.
- No content-addressed store. Rejected as operational machinery for a problem we don't have: raw is static benchmark data, single machine, re-downloadable from HuggingFace (repo IDs in the dataset registry). A CAS would duplicate large datasets for no gain. The integrity guarantee a CAS gives is covered by hash-on-resolve; resilience-to-deletion is covered by the source being public + re-fetchable and the graph itself being snapshotted ([[artefact-v1-snapshot]]).

## How to apply

- v2 chunk = `{file_id, scheme, address}` reference (possibly composite) into raw; content is a *view*, resolved from the untouched source, not a stored mutated blob.
- Structural entities (`:Message`, `:PR`, `:Employee`, …) are also reference-carrying nodes: a reference into raw + hard fields lifted from it + semantics derived from it.
- Any design that stores transformed content as the authoritative record is wrong by this principle. Flag it.
- This is dataset-agnostic and is the foundation for ingesting the next dataset (Bonnier) correctly.

## Related

- [[design-hard-fields-before-tagging]] — structured facts materialized as queryable props; same "don't launder data through prose" spirit
- [[no-silent-fallbacks]] — the truncation clamp is a silent lossy fallback; symptom of the copy-not-reference stance
- [[artefact-v1-snapshot]] — v1 is the copy-based artefact this supersedes
