import neo4j from 'neo4j-driver';

export interface Neo4jConfig {
  uri: string;
  user: string;
  password: string;
  database: string;
}

function intVal(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (neo4j.isInt(v as Parameters<typeof neo4j.isInt>[0])) return (v as { toNumber(): number }).toNumber();
  if (typeof v === 'number') return v;
  return null;
}

async function withSession<T>(cfg: Neo4jConfig, fn: (s: ReturnType<ReturnType<typeof neo4j.driver>['session']>) => Promise<T>): Promise<T> {
  const driver = neo4j.driver(cfg.uri, neo4j.auth.basic(cfg.user, cfg.password));
  const session = driver.session({ database: cfg.database, defaultAccessMode: neo4j.session.READ });
  try {
    return await fn(session);
  } finally {
    await session.close();
    await driver.close();
  }
}

export async function testConnection(cfg: Neo4jConfig): Promise<string> {
  return withSession(cfg, async (s) => {
    const r = await s.run('RETURN 1 AS ok');
    return r.records[0]?.get('ok') === 1 ? 'ok' : 'unexpected result';
  });
}

export interface DatasetStat {
  sourceId: string;
  fileCount: number;
  chunkCount: number;
  tagCount: number;
}

export async function fetchDatasetStats(cfg: Neo4jConfig, runId: string | null = null): Promise<DatasetStat[]> {
  return withSession(cfg, async (s) => {
    const r = await s.run(`
      MATCH (src:Source)-[:CONTAINS]->(f:File)
      OPTIONAL MATCH (f)-[:HAS_CHUNK]->(c:Chunk)
      OPTIONAL MATCH (c)-[r:HAS_TAG]->(t:Tag)
      WHERE $runId IS NULL OR r.run_id = $runId
      WITH src, count(DISTINCT f) AS fileCount,
           count(DISTINCT c) AS chunkCount,
           count(DISTINCT t) AS tagCount
      WHERE src.source_id IS NOT NULL AND NOT src.source_id ENDS WITH '_demo'
      RETURN src.source_id AS sourceId,
             fileCount,
             chunkCount,
             tagCount
      ORDER BY sourceId
    `, { runId });
    return r.records.map(rec => ({
      sourceId: rec.get('sourceId') as string,
      fileCount: intVal(rec.get('fileCount')) ?? 0,
      chunkCount: intVal(rec.get('chunkCount')) ?? 0,
      tagCount: intVal(rec.get('tagCount')) ?? 0,
    }));
  });
}

export { withSession, intVal };
