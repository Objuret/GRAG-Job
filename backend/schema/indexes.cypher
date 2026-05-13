// Standard (non-vector) indexes.

CREATE INDEX IF NOT EXISTS FOR (n:File)         ON (n.dataset_id);
CREATE INDEX IF NOT EXISTS FOR (n:File)         ON (n.format_family);
CREATE INDEX IF NOT EXISTS FOR (n:Chunk)        ON (n.file_id);
CREATE INDEX IF NOT EXISTS FOR (n:Chunk)        ON (n.empty);
CREATE INDEX IF NOT EXISTS FOR (n:CanonicalTag) ON (n.cluster);

CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.cluster);
CREATE INDEX IF NOT EXISTS FOR ()-[r:HAS_TAG]-() ON (r.canonical_id);
CREATE INDEX IF NOT EXISTS FOR ()-[r:TAGGED]-()  ON (r.cluster);
