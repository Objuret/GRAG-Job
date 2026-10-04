# Original question and interpretation are complementary

User decision in this conversation: perform the same operations on both the original question and the interpreted description; they complement each other. Giving one interpreter access to both texts is not equivalent to this.

Implemented in `test/artefact/complementary_query.py`:

- Analyse the original question directly for semantic tags and relational facet readings.
- Generate the sought-content description from the question.
- Analyse that description with exactly the same tag/facet prompt and parser.
- Pass each representation's entire text and own tags through the same embedding and graph-matching procedure.
- Keep both sets of query readings, tag matches, tag-to-chunk-description matches and whole-text-to-chunk-description matches attached to their origin. The learned graph layer is shared and unchanged. Equal tag text across branches is not silently collapsed.

The direct branch receives no generated description. The description branch receives no tags or scores from the direct branch. Both evaluate the information need expressed by their supplied text; the direct question is not reduced to surface-word classification.

`tools/complementary_query_trace.py` is the integration runner; `tools/complementary_query_verify.py` checks its saved requests and evidence without further calls. Results live separately under `output/research/2026-09-25-complementary-query/`; earlier single-representation results remain preserved.

This implements both branches through the currently built HAS_TAG evidence/matching stage. Structural traversal, scope formation and final chunk ranking are still unfinished in the restarted artefact. No average, maximum, topic gate or invented fusion coefficient has been inserted to pretend that retaining both branches settles those later operations. Both branches must continue through the same later processing as those steps are built.

Verification completed: 12 tests passed; the fixed existing case executed with three fresh model calls and the pinned embedder. The original branch produced 6 tags and the interpreted branch 14. Both retained all 61,018 learned edges. Saved requests, responses, numerical readings and every edge identity passed `complementary_query_verify.py`. These establish executed symmetry and data integrity, not retrieval quality.
