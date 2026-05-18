// Standard (non-vector) indexes.

CREATE INDEX IF NOT EXISTS FOR (n:File)         ON (n.dataset_id);
CREATE INDEX IF NOT EXISTS FOR (n:File)         ON (n.format_family);
CREATE INDEX IF NOT EXISTS FOR (n:Chunk)        ON (n.file_id);
CREATE INDEX IF NOT EXISTS FOR (n:Chunk)        ON (n.empty);
CREATE INDEX IF NOT EXISTS FOR (n:CanonicalTag) ON (n.cluster);

CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.facet);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.run_id);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.cluster);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.canonical_id);
CREATE INDEX IF NOT EXISTS FOR ()-[r:TAGGED]-()  ON (r.cluster);

// HERB hard-field gate. Written by `python -m tagging materialize`. Only the
// fields retrieval.ts actually filters on are indexed (product/section/
// channel/employee_id + the pre-existing kind); the other materialized scalar
// props are queryable but deliberately not indexed (unused index surface was
// removed). `years` is a list projected from temporal tags — list membership
// is not range-indexable and the corpus is small, so it is scanned. Created
// idempotently here and by the materialize stage (ensure_hard_field_indexes).
CREATE INDEX chunk_product     IF NOT EXISTS FOR (c:Chunk) ON (c.product);
CREATE INDEX chunk_section     IF NOT EXISTS FOR (c:Chunk) ON (c.section);
CREATE INDEX chunk_channel     IF NOT EXISTS FOR (c:Chunk) ON (c.channel);
CREATE INDEX chunk_employee_id IF NOT EXISTS FOR (c:Chunk) ON (c.employee_id);
CREATE INDEX chunk_kind        IF NOT EXISTS FOR (c:Chunk) ON (c.kind);

// Lexical recall over the extracted text (the no-tags / literal-search path).
CREATE FULLTEXT INDEX chunk_fulltext IF NOT EXISTS
FOR (c:Chunk) ON EACH [c.content, c.description, c.question];
