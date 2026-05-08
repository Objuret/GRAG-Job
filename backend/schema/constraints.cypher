// Neo4j constraints for the artefact graph.

CREATE CONSTRAINT IF NOT EXISTS FOR (n:Source)                REQUIRE n.source_id   IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:File)                  REQUIRE n.file_id     IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Chunk)                 REQUIRE n.chunk_id    IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Run)                   REQUIRE n.run_id      IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:WorkItem)              REQUIRE n.work_item_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:CanonicalTagProposal)  REQUIRE n.proposal_id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS FOR (n:Tag)                   REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:CanonicalTag)          REQUIRE (n.label, n.cluster) IS NODE KEY;
