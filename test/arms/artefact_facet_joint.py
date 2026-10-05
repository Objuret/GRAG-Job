"""Frozen-Volmax joint-facet arm with raw-query split interpretation.

The graph and facet layer are pinned research inputs, not a live database view.
All retrieval operators are the existing experimental modules. Only delivery
uses the actual harness resolver/budget instead of saved-source frontier costs.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time

import numpy as np
from threadpoolctl import threadpool_limits

from harness import chat
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from artefact import querytagger as Q
from artefact import querytagger_split_check as S
from artefact.facet_joint_candidate import FACETS, freeze_reference
from artefact.facet_retrieval_pipeline import retrieve_prepared_query
from artefact.facet_scope_recruitment import recruit_with_verified_area
from artefact.facet_structural_landing import StructuralIndex, load_structural_index, resolve_structural_area
from arms.artefact_v2 import _budget_contexts, _resolve_chunk

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'output/research/2026-09-21-facet-validity/route_snapshot'
STRUCTURAL_SNAPSHOT = ROOT / 'output/research/2026-09-22-structural-landings/structural_snapshot.json'
STRUCTURAL_SHA256 = '9c9e9ff8415002cdc6203ecfdc29ef6a933d9eaf8859e3d1cf8d6678037f33ce'
DATABASE = 'herb-eval-volmax'
INTERPRET_MODEL = 'claude-haiku-4-5'
COEFFICIENTS = (1., .25, .25, .25, .25)
# Literal declarations allow the blind run wrapper to freeze dependencies without imports.
SMOKE_PROVENANCE_PATHS = (
    'test/arms/artefact_facet_joint.py', 'test/arms/artefact_v2.py', 'test/arms/artefact_v3.py',
    'test/artefact/querytagger.py', 'test/artefact/querytagger_split_check.py',
    'test/artefact/facet_joint_candidate.py', 'test/artefact/facet_stream_envelope.py',
    'test/artefact/facet_retrieval_pipeline.py', 'test/artefact/facet_scope_recruitment.py',
    'test/artefact/facet_structural_landing.py',
    'test/artefact/facet_recruitment_candidate.py', 'test/artefact/facet_need_frontier.py',
    'prod/harness/chat.py', 'prod/harness/embed.py', 'prod/harness/contract.py',
    'prod/harness/char_budget.py',
    'output/research/2026-09-21-facet-validity/route_snapshot/graph.json',
    'output/research/2026-09-21-facet-validity/route_snapshot/arrays.npz',
    'output/research/2026-09-21-facet-validity/route_snapshot/graph_vectors.npz',
    'output/research/2026-09-21-facet-validity/route_snapshot/manifest.json',
    'output/research/2026-09-22-structural-landings/structural_snapshot.json',
)
SMOKE_MODEL_CONFIG = {
    'interpreter_model': 'claude-haiku-4-5',
    'embedding_model': 'nvidia/llama-nemotron-embed-1b-v2',
    'embedding_revision': '113abe4acafa848e77ead9c0623205e511932348',
    'embedding_device': 'cpu', 'embedding_dtype': 'float32',
    'query_prefix': 'query: ', 'cpu_threads': 4, 'embedding_batch_size': 1,
    'coefficients': [1., .25, .25, .25, .25],
    'interpreter_calls_per_uncached_question': 2, 'transport_max_tries': 1,
}
PINNED_FILES = {
    'graph.json': '03befcae02198fff2dff184773aa87a6b46ac6d46ced72ab05f7b05ac118af00',
    'arrays.npz': 'bdb8abcf2d49f612e4dbad194520e4c0c3997eb4fae63c16d896ff2755fe1239',
    'graph_vectors.npz': 'fe927816b6ea2fab419b2fb1575efcded5b42554c2d607544f80564f480fac67',
}
RETRIEVAL_FLAGS = {
    'snapshot': str(SNAPSHOT), 'snapshot_sha256': PINNED_FILES,
    'coefficients': list(COEFFICIENTS), 'facets': list(FACETS),
    'scope': 'Exact structural name landings, union of nodes per name, intersection across names; unresolved areas preserve global access.',
    'structural_snapshot_sha256': STRUCTURAL_SHA256,
    'scope_scheduling': 'Existing equal-depth global/area nomination; remains an unvalidated scheduling convention.',
    'graph_relations': 'Shared Product+Channel groups and original locator adjacency.',
    'facet_reference': 'Fixed empirical midrank CDF over all 57204 semantic edges, all five facets.',
    'query_weights': 'Per-tag relevance through each facet to generated description; unchanged split prompts.',
    'budget': 'Shared _budget_contexts on full recovered order; serialized contexts, partial boundary.',
    'transport': 'One GENERATE and one SCORE, separate private caches; chat.post max_tries=1.',
    'status': 'Frozen snapshot experimental policy; no live graph or broad validation claim.',
}
EMBED_KEEP = ROOT / 'output/query_embed_cache'
_NUMERIC_LOCK = threading.RLock()
_CACHE_LOCK = threading.Lock()
_KEY_LOCKS = {}


def _sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _key_lock(key):
    with _CACHE_LOCK:
        return _KEY_LOCKS.setdefault(key, threading.Lock())


def _unit(value):
    value = np.asarray(value, dtype=np.float64)
    norms = np.linalg.norm(value, axis=1, keepdims=True)
    if value.ndim != 2 or not np.isfinite(value).all() or (norms == 0).any():
        raise ValueError('Expected finite nonzero embedding rows')
    return value / norms


def _query_embedding_texts(description, tags):
    # Matches the exact _readable helper frozen by independent_snapshot.py.
    return list(dict.fromkeys([tag.strip() for tag in tags] + [description]))


def _source_adjacency(chunks):
    path = ROOT / 'test/arms/artefact_v3.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'_csr', 'file_adjacency'}]
    if len(functions) != 2:
        raise ValueError('Original adjacency helpers missing')
    namespace = {'np': np, 'json': json}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    csr = namespace['file_adjacency'](chunks)
    return tuple((i, int(j)) for i in range(len(chunks))
                 for j in csr['members'][csr['ptr'][i]:csr['ptr'][i + 1]] if i < j)


@dataclass(frozen=True)
class Prepared:
    chunks: tuple
    edge_ids: tuple
    edge_tag: np.ndarray
    edge_chunk: np.ndarray
    edge_facets: np.ndarray
    tag_vectors: np.ndarray
    chunk_vectors: np.ndarray
    reference: object
    groups: dict
    adjacency_pairs: tuple
    structural_index: StructuralIndex
    provenance: dict
    cache_dir: Path
    build_stats: BuildStats
    scope_scheduling: str = 'equal_depth'


def prepare_over_corpus(corpus, *, scope_scheduling='equal_depth') -> Prepared:
    """Load pinned graph data only; corpus contents are resolved lazily at delivery."""
    started = time.perf_counter()
    if scope_scheduling not in ('equal_depth', 'area_first'):
        raise ValueError('scope_scheduling must be equal_depth or area_first')
    manifest = _read(SNAPSHOT / 'manifest.json')
    for name, expected in PINNED_FILES.items():
        if manifest['output_sha256'][name] != expected or _sha((SNAPSHOT / name).read_bytes()) != expected:
            raise ValueError('Pinned facet snapshot hash mismatch: ' + name)
    graph = _read(SNAPSHOT / 'graph.json')
    chunks = tuple(graph['chunks'])
    if (tuple(graph['facets']) != FACETS or len(chunks) != 4808
            or [c['chunkId'] for c in chunks] != graph['chunk_ids']
            or len(graph['edge_ids']) != 57204):
        raise ValueError('Frozen graph population/alignment mismatch')
    for chunk in chunks:
        if any(key not in chunk for key in ('locator', 'relpath', 'sha256', 'source_text', 'scope')):
            raise ValueError('Missing source pointer in snapshot')
    with np.load(SNAPSHOT / 'arrays.npz', allow_pickle=False) as arrays:
        edge_tag = arrays['edge_tag'].copy()
        edge_chunk = arrays['edge_chunk'].copy()
        edge_facets = arrays['edge_facets'].copy()
    for edge, ti, ci in zip(graph['edge_ids'], edge_tag, edge_chunk):
        if edge != graph['chunk_ids'][ci] + '::' + graph['graph_tags'][ti]:
            raise ValueError('Frozen edge endpoint mismatch')
    with np.load(SNAPSHOT / 'graph_vectors.npz', allow_pickle=False) as vectors:
        tag_at = {name: i for i, name in enumerate(graph['all_graph_vector_tag_names'])}
        tag_vectors = _unit(vectors['tag_raw_float32'][[tag_at[t] for t in graph['graph_tags']]])
        chunk_vectors = _unit(vectors['chunk_raw_float32'])
    for array in (edge_tag, edge_chunk, edge_facets, tag_vectors, chunk_vectors):
        array.setflags(write=False)
    groups = defaultdict(list)
    for i, chunk in enumerate(chunks):
        for product in chunk['scope'].get('product', []):
            for channel in chunk['scope'].get('channel', []):
                groups[product['node_id'], channel['node_id']].append(i)
    structural = load_structural_index(STRUCTURAL_SNAPSHOT,sha256=STRUCTURAL_SHA256,
        graph_sha256=PINNED_FILES['graph.json'],eligible_chunk_ids=graph['chunk_ids'])
    paths = [Path(__file__), ROOT / 'test/arms/artefact_v2.py', ROOT / 'test/arms/artefact_v3.py',
             ROOT / 'prod/harness/char_budget.py', ROOT / 'prod/harness/embed.py', ROOT / 'prod/harness/chat.py']
    paths += [ROOT / 'test/artefact' / name for name in (
        'querytagger.py', 'querytagger_split_check.py', 'facet_joint_candidate.py',
        'facet_stream_envelope.py', 'facet_retrieval_pipeline.py', 'facet_scope_recruitment.py',
        'facet_recruitment_candidate.py', 'facet_need_frontier.py', 'facet_structural_landing.py')]
    provenance = {
        'database': manifest['database'], 'run_id': manifest['run_id'],
        'dataset_id': manifest['dataset_id'], 'snapshot_created_utc': manifest['created_utc'],
        'snapshot_manifest_sha256': _sha((SNAPSHOT / 'manifest.json').read_bytes()),
        'snapshot_sha256': dict(PINNED_FILES), 'counts': manifest['counts'],
        'graph_facet_source': manifest['graph_facet_source'],
        'description_source': manifest['description_source'],
        'source_sha256': {str(p.relative_to(ROOT)): _sha(p.read_bytes()) for p in paths},
        'corpus_argument': str(corpus), 'live_database_reads': 0,
        'structural_snapshot': structural.provenance,
        'scope_scheduling': scope_scheduling,
        'prompt_sha256': {name: _sha(getattr(Q, name)) for name in (
            'GENERATE_SYSTEM', 'GENERATE_USER_TEMPLATE', 'SCORE_SYSTEM', 'SCORE_USER_TEMPLATE')},
    }
    cache = Path(os.environ.get('HERB_FACET_JOINT_CACHE', str(ROOT / 'output/private/facet_joint_cache')))
    return Prepared(chunks, tuple(graph['edge_ids']), edge_tag, edge_chunk, edge_facets,
                    tag_vectors, chunk_vectors, freeze_reference(edge_facets),
                    {'shared_product_channel': tuple(tuple(v) for v in groups.values())},
                    _source_adjacency(chunks), structural,
                    provenance, cache, BuildStats(time.perf_counter() - started, ModelUsage(), []),
                    scope_scheduling=scope_scheduling)


def _cached_stage(stage, system, user, validate, cache_dir):
    """One transport attempt; failures and uncertain attempts cannot auto-retry."""
    signature = {'cache_version': 1, 'stage': stage, 'model': INTERPRET_MODEL,
                 'system': system, 'user': user, 'max_tries': 1}
    key = _sha(json.dumps(signature, sort_keys=True, ensure_ascii=False))
    path = cache_dir / stage / (key + '.json')
    marker = path.with_suffix('.started.json')
    with _key_lock(str(path)):
        if path.exists():
            saved = _read(path)
            if saved['signature'] != signature or not saved['ok']:
                raise RuntimeError(f'Facet interpreter cached {stage} failed; key={key}')
            try:
                parsed = validate(saved['raw'])
            except Exception:
                raise RuntimeError(f'Facet interpreter invalid cached {stage}; key={key}') from None
            return parsed, ModelUsage(), {'stage': stage, 'key': key, 'cache_hit': True,
                                          'saved_usage': saved['usage'], 'path': str(path)}
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with marker.open('x', encoding='utf-8') as stream:
                json.dump(signature, stream, ensure_ascii=False)
        except FileExistsError:
            raise RuntimeError(f'Facet interpreter uncertain {stage} attempt; key={key}') from None
        started = time.perf_counter()
        response = None
        try:
            response = chat.post('/chat/completions', {
                'model': INTERPRET_MODEL, 'temperature': 0,
                'max_tokens': S.MAX_TOKENS_G if stage == 'generate' else S.MAX_TOKENS_S,
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            }, timeout=480.0, max_tries=1)
            raw = Q.extract_json(response['choices'][0]['message']['content'])
            parsed = validate(raw)
            usage = response.get('usage') or {}
            elapsed = time.perf_counter() - started
            _atomic_json(path, {'signature': signature, 'ok': True, 'raw': raw,
                                'response': response, 'usage': usage, 'elapsed_s': elapsed})
        except Exception as exc:
            _atomic_json(path, {'signature': signature, 'ok': False, 'response': response,
                                'error': f'{type(exc).__name__}: {exc}',
                                'elapsed_s': time.perf_counter() - started})
            raise RuntimeError(f'Facet interpreter {stage} failed; key={key}; no retry') from None
        used = ModelUsage(calls=1, tokens_in=int(usage.get('prompt_tokens', 0)),
                          tokens_out=int(usage.get('completion_tokens', 0)),
                          cached_input_tokens=int(usage.get('cached_input_tokens', 0)), time_s=elapsed)
        return parsed, used, {'stage': stage, 'key': key, 'cache_hit': False, 'path': str(path)}


def _interpret(text, prepared):
    system, user = S.generate_prompt(text)
    generation, gen_usage, gen_meta = _cached_stage('generate', system, user, S.parse_generate, prepared.cache_dir)
    system, user = S.score_prompt(generation['description'], generation['tags'])
    scores, score_usage, score_meta = _cached_stage('score', system, user,
        lambda raw: S.parse_score(raw, generation['tags']), prepared.cache_dir)
    usage = ModelUsage(**{name: getattr(gen_usage, name) + getattr(score_usage, name)
                          for name in ModelUsage.__dataclass_fields__})
    weights = np.array([[row['facets'][f] for f in FACETS] for row in scores['tags']])
    return generation, weights, usage, {'model': INTERPRET_MODEL, 'stages': [gen_meta, score_meta],
                                       'description': generation['description'], 'tags': scores['tags']}


def _kept_row(path):
    try:
        row = np.load(path, allow_pickle=False)
    except (OSError, ValueError, EOFError):
        return None
    if (row.ndim != 1 or row.dtype != np.float32 or not row.size or not np.isfinite(row).all()
            or abs(float(np.linalg.norm(row.astype(np.float64))) - 1.) > 1e-4):
        return None
    return row


def _keep_row(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            np.save(stream, row, allow_pickle=False)
        try:
            os.replace(name, path)
        except OSError:
            # the row is in hand either way: one that cannot be put in place (another process
            # holds the file) is embedded again the next time
            pass
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _embed_kept(embed, texts, role):
    """`embed._embed(texts, role)` with every row kept on the side and read from there the
    next time (his 2026-10-05 "just run the fucking correct embedder on the correct things,
    save that on the side and then fucking use THAT instead"): one float32 row a file under
    EMBED_KEEP/<model>@<revision>__<dtype>__<device>/, named by the sha256 of the role's prefix
    and the text, no text in it. The harness embeds one text a batch, so a text's row does not
    depend on what it is embedded beside. Only the harness's own `_embed` is kept; a stand-in
    is called as it is, nothing read and nothing written. Returns `_embed`'s five values, the
    usage counting the texts embedded now, and how many rows were served and embedded (None
    where nothing is kept)."""
    if (getattr(embed._embed, '__module__', None) != 'harness.embed' or embed.EMBED_BATCH != 1
            or role not in embed.EMBED_PREFIX):
        return (*embed._embed(texts, role, bar=False), None)
    folder = EMBED_KEEP / (f'{embed.EMBED_MODEL.replace("/", "__")}@{embed.EMBED_REVISION[:12]}'
                           f'__{embed.EMBED_DTYPE}__{embed.EMBED_DEVICE}')
    paths = [folder / (_sha(embed.EMBED_PREFIX[role] + (text or ' ')) + '.npy') for text in texts]
    rows = [_kept_row(path) for path in paths]
    misses = [i for i, row in enumerate(rows) if row is None]
    calls, ti, to, seconds = 0, 0, 0, 0.
    if misses:
        fresh, calls, ti, to, seconds = embed._embed([texts[i] for i in misses], role, bar=False)
        for i, row in zip(misses, np.asarray(fresh, dtype=np.float32)):
            rows[i] = row
            _keep_row(paths[i], row)
    return (np.array(rows, dtype=np.float32), calls, ti, to, seconds,
            {'served': len(texts) - len(misses), 'embedded': len(misses)})


def _query_cosines(description, tags, prepared, role='query'):
    """Serial pinned embedding in the role given, the query role unless another is named;
    normalize frozen float32 inputs in float64. Each text's row is kept on the side
    (`_embed_kept`)."""
    with _NUMERIC_LOCK, threadpool_limits(limits=4):
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
            os.environ[name] = '4'
        import torch
        from harness import embed
        torch.set_num_threads(4)
        if (embed.EMBED_MODEL != 'nvidia/llama-nemotron-embed-1b-v2'
                or embed.EMBED_REVISION != '113abe4acafa848e77ead9c0623205e511932348'
                or embed.EMBED_DEVICE != 'cpu' or embed.EMBED_DTYPE != 'float32'
                or embed.EMBED_PREFIX != {'query': 'query: ', 'passage': 'passage: '}):
            raise ValueError('Pinned embedding recipe differs')
        texts = _query_embedding_texts(description, tags)
        vectors, calls, ti, to, seconds, kept = _embed_kept(embed, texts, role)
        vectors = _unit(vectors)
        at = {text: i for i, text in enumerate(texts)}
        tag_vectors = vectors[[at[tag.strip()] for tag in tags]]
        description_vector = vectors[at[description]]
        recipe = {'model': embed.EMBED_MODEL, 'revision': embed.EMBED_REVISION,
                  'dtype': embed.EMBED_DTYPE, 'device': embed.EMBED_DEVICE, 'input_type': role,
                  'prefix': embed.EMBED_PREFIX[role], 'cpu_threads': 4,
                  'unique_texts': len(texts), 'vector_sha256': _sha(vectors.tobytes()),
                  'kept_on_the_side': kept,
                  'query_vector_normalization': 'float64 unit norm after serving float32 normalization'}
        matrices = {'query_tag_cosines': tag_vectors @ prepared.tag_vectors.T,
                    'query_chunk_cosines': tag_vectors @ prepared.chunk_vectors.T,
                    'query_description_cosines': description_vector @ prepared.chunk_vectors.T}
    return matrices, ModelUsage(calls=calls, tokens_in=ti, tokens_out=to, time_s=seconds), recipe


def _rank(prepared, text, generation, weights, matrices):
    result = retrieve_prepared_query(
        chunk_rows=prepared.chunks, coefficients=COEFFICIENTS, source_character_budget=None,
        query_tag_ids=generation['tags'], edge_ids=prepared.edge_ids,
        edge_tag_indices=prepared.edge_tag, edge_chunk_indices=prepared.edge_chunk,
        edge_facets=prepared.edge_facets, query_facet_weights=weights,
        reference=prepared.reference, groups=prepared.groups,
        adjacency_pairs=prepared.adjacency_pairs, **matrices)
    area_ids, provenance = resolve_structural_area(text, prepared.structural_index)
    scoped = recruit_with_verified_area(chunk_rows=prepared.chunks,
        joint_scores=result['ranking']['scores'], area_chunk_ids=area_ids,
        area_provenance=provenance, source_character_budget=None,
        scheduling=prepared.scope_scheduling)
    result['recruitment'] = scoped['recruitment']
    result['area'] = {'area': scoped['area'], 'stream_ids': scoped['stream_ids'], 'policy': scoped['policy']}
    return result


def answer_one_question(question, prepared: Prepared, generate, k: int = 50,
                        char_budget: int | None = None) -> ArmOutput:
    """Harness entry point; query/facet content stays in private cache/run metadata."""
    if not isinstance(question, (tuple, list)) or len(question) != 2:
        raise ValueError('Expected (question_id, raw_question)')
    _, text = question
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Raw question must be nonempty text')
    if char_budget is not None and (type(char_budget) is not int or char_budget < 1):
        raise ValueError('char_budget must be a positive integer or None')
    if type(k) is not int or k < 1:
        raise ValueError('k must be a positive integer')
    started = time.perf_counter()
    chat.reset_timing()
    generation, weights, interp_usage, interp_meta = _interpret(text, prepared)
    matrices, embed_usage, embed_meta = _query_cosines(generation['description'], generation['tags'], prepared)
    with _NUMERIC_LOCK, threadpool_limits(limits=4):
        result = _rank(prepared, text, generation, weights, matrices)
    ordered_ids = result['recruitment']['selected_chunk_ids']
    by_id = {chunk['chunkId']: chunk for chunk in prepared.chunks}
    ordered_rows = [by_id[cid] for cid in ordered_ids]
    doc_cache = {}
    if char_budget is not None:
        contexts, id_lists, context_ids, budget = _budget_contexts(ordered_rows, char_budget, doc_cache)
    else:
        contexts, id_lists, context_ids = [], [], []
        for row in ordered_rows[:k]:
            content, ids = _resolve_chunk(row, doc_cache)
            contexts.append(content)
            id_lists.append(ids)
            for aid in ids:
                if aid not in context_ids:
                    context_ids.append(aid)
        budget = None
    retrieval = ModelUsage(**{name: getattr(interp_usage, name) + getattr(embed_usage, name)
                              for name in ModelUsage.__dataclass_fields__})
    for name, value in chat.take_timing().items():
        setattr(retrieval, name, value)
    meta = {'policy': {**RETRIEVAL_FLAGS, 'scope_scheduling': prepared.scope_scheduling}, 'snapshot': prepared.provenance,
            'interpreter': interp_meta, 'embedding': embed_meta, 'area': result['area'],
            'ranking': {'rows': result['ranking']['rows'], 'coefficients': list(COEFFICIENTS),
                        'ranked_chunk_ids': result['ranking']['ranked_chunk_ids']},
            'recruitment': result['recruitment'], 'full_recovered_order': ordered_ids,
            'delivered_chunk_ids': ordered_ids[:len(contexts)], 'chunk_ids': id_lists,
            'returned': len(contexts), 'char_budget': budget,
            'delivery_note': 'Source-artifact IDs from shared resolver; a partial boundary text is delivered but its IDs are not credited by shared budget contract.'}
    search_time = max(0., time.perf_counter() - started - interp_usage.time_s)
    if generate is None:
        answer, gen_usage = '', ModelUsage()
    else:
        gen_start = time.perf_counter()
        answer, gen_usage = unpack_generation(generate(text, contexts), time.perf_counter() - gen_start)
    return ArmOutput(answer=answer, contexts=contexts, context_ids=context_ids,
                     search_time_s=search_time, generator=gen_usage, retrieval=retrieval, meta=meta)
