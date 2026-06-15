import asyncio
import os
from pathlib import Path

from neo4j import AsyncGraphDatabase


def load_env() -> None:
    p = Path(__file__).resolve().parents[1] / "backend" / ".env"
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def mb(n: int | float) -> float:
    return n / 1024 / 1024


async def analyze(db: str) -> None:
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    async with driver.session(database=db) as session:
        chunk = dict(
            await (await session.run(
                """
                MATCH (c:Chunk)
                RETURN count(c) AS n,
                  sum(size(coalesce(c.chunk_id,''))) AS chunk_id,
                  sum(size(coalesce(c.file_id,''))) AS file_id,
                  sum(size(coalesce(c.locator_json,''))) AS locator_json,
                  sum(size(coalesce(c.parent_ref,''))) AS parent_ref,
                  sum(size(coalesce(c.chunk_ref,''))) AS chunk_ref,
                  sum(size(coalesce(c.kind,''))) AS kind,
                  sum(size(coalesce(c.section,''))) AS section,
                  sum(size(coalesce(c.product,''))) AS product,
                  sum(size(coalesce(c.channel,''))) AS channel,
                  sum(size(coalesce(c.employee_id,''))) AS employee_id,
                  sum(size(coalesce(c.metadata_section,''))) AS metadata_section,
                  sum(size(coalesce(c.subsection,''))) AS subsection,
                  sum(size(coalesce(c.doc_field,''))) AS doc_field,
                  sum(size(coalesce(c.question,''))) AS question,
                  sum(size(coalesce(c.created_at,''))) AS created_at,
                  sum(size(coalesce(c.content,''))) AS content,
                  sum(size(coalesce(c.description,''))) AS description
                """
            )).single()
        )

        file_node = dict(
            await (await session.run(
                """
                MATCH (f:File)
                RETURN count(f) AS n,
                  sum(size(coalesce(f.file_id,''))) AS file_id,
                  sum(size(coalesce(f.sha256,''))) AS sha256,
                  sum(size(coalesce(f.dataset_id,''))) AS dataset_id,
                  sum(size(coalesce(f.rel_path,''))) AS rel_path,
                  sum(size(coalesce(f.file_path,''))) AS file_path,
                  sum(size(coalesce(f.format_family,''))) AS format_family,
                  sum(size(coalesce(f.dispatch_mode,''))) AS dispatch_mode,
                  sum(size(coalesce(f.created_at,''))) AS created_at,
                  sum(size(coalesce(f.description,''))) AS description
                """
            )).single()
        )

        source_ptr = dict(
            await (await session.run(
                """
                MATCH (s:Source)
                RETURN sum(size(coalesce(s.source_id,'')))
                     + sum(size(coalesce(s.dataset_id,'')))
                     + sum(size(coalesce(s.created_at,''))) AS bytes
                """
            )).single()
        )["bytes"] or 0

        tag = dict(
            await (await session.run(
                """
                MATCH (t:Tag)
                RETURN count(t) AS n,
                  sum(size(coalesce(t.name,''))) AS tag_names,
                  sum(CASE WHEN t.embedding IS NOT NULL THEN 384 ELSE 0 END +
                      CASE WHEN t.emb_all IS NOT NULL THEN 384 ELSE 0 END +
                      CASE WHEN t.emb_topic IS NOT NULL THEN 384 ELSE 0 END +
                      CASE WHEN t.emb_entities IS NOT NULL THEN 384 ELSE 0 END +
                      CASE WHEN t.emb_activity IS NOT NULL THEN 384 ELSE 0 END +
                      CASE WHEN t.emb_temporal IS NOT NULL THEN 384 ELSE 0 END +
                      CASE WHEN t.emb_evidence IS NOT NULL THEN 384 ELSE 0 END) AS emb_floats,
                  sum(size(coalesce(t.embedding_model,''))) AS embedding_model
                """
            )).single()
        )

        edge = dict(
            await (await session.run(
                """
                MATCH ()-[r:HAS_TAG]->()
                RETURN count(r) AS n,
                  sum(size(coalesce(r.facet,''))) AS facet,
                  sum(size(coalesce(r.run_id,''))) AS run_id
                """
            )).single()
        )

    await driver.close()

    pointer_keys = ["chunk_id", "file_id", "locator_json", "parent_ref", "chunk_ref"]
    gate_keys = [
        "kind",
        "section",
        "product",
        "channel",
        "employee_id",
        "metadata_section",
        "subsection",
        "doc_field",
        "question",
    ]

    ptr = sum(chunk[k] for k in pointer_keys)
    gate = sum(chunk[k] for k in gate_keys)
    meta = chunk["created_at"]
    text = chunk["content"] + chunk["description"]

    file_ptr = (
        file_node["file_id"]
        + file_node["sha256"]
        + file_node["dataset_id"]
        + file_node["rel_path"]
        + file_node["file_path"]
        + file_node["format_family"]
        + file_node["dispatch_mode"]
        + file_node["created_at"]
    )
    file_desc = file_node["description"] or 0

    emb_bytes = (tag["emb_floats"] or 0) * 4
    edge_num_bytes = edge["n"] * 8 * 2

    total_logical = (
        ptr
        + gate
        + meta
        + text
        + file_ptr
        + file_desc
        + source_ptr
        + tag["tag_names"]
        + emb_bytes
        + tag["embedding_model"]
        + edge["facet"]
        + edge["run_id"]
        + edge_num_bytes
    )

    pure_ptr = ptr + file_ptr + source_ptr
    ptr_plus_gate = pure_ptr + gate

    print(f"\n=== {db} logical payload ===")
    print(f"Chunks: {chunk['n']:,}")
    print(f"  pure pointers (ids/refs/paths):     {mb(pure_ptr):.2f} MB")
    print(f"    chunk_id+file_id:                   {mb(chunk['chunk_id']+chunk['file_id']):.2f} MB")
    print(f"    locator_json:                       {mb(chunk['locator_json']):.2f} MB")
    print(f"    parent_ref+chunk_ref:               {mb(chunk['parent_ref']+chunk['chunk_ref']):.2f} MB")
    print(f"  gate scalars (product/section/...): {mb(gate):.2f} MB")
    print(f"  chunk text (content+description):   {mb(text):.2f} MB")
    print(f"Files: {file_node['n']:,} -> file pointers {mb(file_ptr):.4f} MB")
    print(f"Tags: {tag['n']:,} -> names {mb(tag['tag_names']):.2f} MB, embeddings {mb(emb_bytes):.2f} MB")
    print(f"HAS_TAG: {edge['n']:,} -> edge props {mb(edge['facet']+edge['run_id']+edge_num_bytes):.2f} MB")
    print("---")
    print(f"TOTAL logical payload:                {mb(total_logical):.2f} MB")
    print(f"Pure pointers:                        {mb(pure_ptr):.2f} MB ({100*pure_ptr/total_logical:.1f}%)")
    print(f"Pointers + gate scalars:              {mb(ptr_plus_gate):.2f} MB ({100*ptr_plus_gate/total_logical:.1f}%)")
    print(f"Chunk text:                           {mb(text):.2f} MB ({100*text/total_logical:.1f}%)")
    print(f"Embeddings:                           {mb(emb_bytes):.2f} MB ({100*emb_bytes/total_logical:.1f}%)")


async def main() -> None:
    load_env()
    for db in ("herb-eval", "herb"):
        await analyze(db)


if __name__ == "__main__":
    asyncio.run(main())
