import asyncio, sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from shared.config import Settings
from shared.neo4j_client import Neo4jClient

async def main():
    s = Settings()
    c = Neo4jClient(s)
    queries = [
        ("Source", "MATCH (n:Source) RETURN count(n) AS n"),
        ("File", "MATCH (n:File) RETURN count(n) AS n"),
        ("Chunk", "MATCH (n:Chunk) RETURN count(n) AS n"),
        ("WorkItem unrun chunk_extraction", "MATCH (n:WorkItem) WHERE n.kind='chunk_extraction' AND n.status='unrun' RETURN count(n) AS n"),
        ("WorkItem unrun file_orchestration", "MATCH (n:WorkItem) WHERE n.kind='file_orchestration' AND n.status='unrun' RETURN count(n) AS n"),
        ("CanonicalTag", "MATCH (n:CanonicalTag) RETURN count(n) AS n"),
        ("CanonicalTag by cluster", "MATCH (n:CanonicalTag) RETURN n.cluster AS cluster, count(n) AS n ORDER BY cluster"),
        ("File breakdown by format_family", "MATCH (n:File) RETURN n.format_family AS ff, count(n) AS n ORDER BY ff"),
        ("Chunk breakdown by kind", "MATCH (n:Chunk) RETURN n.kind AS kind, count(n) AS n ORDER BY kind"),
        ("Sample chunk content", "MATCH (n:Chunk) RETURN n.chunk_id AS id, n.kind AS kind, substring(n.content, 0, 120) AS preview LIMIT 3"),
    ]
    try:
        async with c.session() as s_:
            for label, q in queries:
                print(f"\n--- {label} ---")
                r = await s_.run(q)
                async for record in r:
                    print(dict(record))
    finally:
        await c.close()

if __name__ == "__main__":
    asyncio.run(main())
