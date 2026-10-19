"""artefact_v4: the question's tags, its description and the question itself order every chunk
of the pool; the chunks of the product the question points at go first.

Per question:
  1. One model call writes a description of the content the question is looking for and two
     tag lists, one from that content and one from the question's own words, each tag with
     five readings (`query_content.request`).
  2. A second call gets the graph's tree, the question, that description and those tags, and
     returns the places the question is about (`query_content.scope_request`). Both calls
     get their input as marked parts and their answer forced into a JSON schema.
  3. The tags and the description are embedded in the passage role, as the graph's tags and
     chunk descriptions are; the question in the query role.
  4. `v4_walk.chain` gives every chunk one strength and the order.
  5. The chunks under the products of the returned places go first, in that order.
The harness cuts at the character budget.

HERB_V4_OFFLINE=on reads both calls' answers from the cache and raises where one is missing.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import time

import numpy as np

from harness import chat
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from harness.progress import say
from artefact import query_content as Q
from artefact import landing as LAND
from artefact import graph_layer as GL
from artefact import v4_walk as WK
from arms.artefact_facet_joint import _cached_stage, _query_cosines, _sha, _unit
from arms.artefact_v2 import _budget_contexts, _resolve_chunk
from graph.db import _readable

ROOT = Path(__file__).resolve().parents[2]
DATABASE = 'herb-eval-volmax'
RUN_ID = 'pilot_full_herb'
# His 2026-10-06 "yes, sonnet on those". The model is part of the cache key.
INTERPRET_MODEL = 'claude-sonnet-5'
COS_NOISE = 0.002
TOPIC_TOLERANCE = 1e-6
KIND_LABELS = {'document': 'documents', 'document_part': 'document parts',
               'meeting_chat_batch': 'meeting chats', 'meeting_transcript': 'meeting transcripts',
               'meeting_transcript_part': 'meeting transcript parts',
               'pr_batch': 'pull requests', 'slack_thread_batch': 'slack threads',
               'url_batch': 'urls'}
STAGE_NAMES = {'querytag': 'querytagger', 'scope': 'scope'}
if GL.FACETS != WK.FACETS:
    raise RuntimeError('The graph layer and the chain name different facets')
TERMS = ('tags', 'description', 'product', 'near')

TAG_CYPHER = '''
MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS {
    MATCH (t)<-[r:HAS_TAG]-(c:Chunk)
    WHERE r.run_id = $run AND (c)-[:product]->() }
RETURN t.name AS id, t.emb AS vector ORDER BY id
'''

# The three metadata files' chunks carry no product edge and stay out of the pool.
CHUNK_CYPHER = '''
MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL AND EXISTS {
    MATCH (c)-[r:HAS_TAG]->() WHERE r.run_id = $run }
    AND (c)-[:product]->()
MATCH (f:File)-[:HAS_CHUNK]->(c)
RETURN c.chunk_id AS chunkId, c.desc_emb AS vector, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256, c.kind AS kind ORDER BY chunkId
'''

PRODUCT_CYPHER = 'MATCH (p:Product) RETURN p.name AS name ORDER BY name'

EDGE_CYPHER = '''
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $run AND c.desc_emb IS NOT NULL AND t.emb IS NOT NULL AND (c)-[:product]->()
RETURN t.name AS tag, c.chunk_id AS chunkId, r.facets AS facets, r.w_facets AS values
'''

LAYER_CYPHER = 'MATCH (l:FacetLayer {run_id: $run}) RETURN properties(l) AS properties'

SCOPE_CYPHER = '''
MATCH (c:Chunk)-[:product]->(p:Product)
OPTIONAL MATCH (c)-[:channel]->(ch:Channel)
RETURN c.chunk_id AS chunkId, p.name AS product, collect(ch.id) AS channels
'''

# The harness writes this into the run manifest.
RETRIEVAL_FLAGS = {
    'interpreter_model': INTERPRET_MODEL,
    'cos_noise': COS_NOISE,
    'offline': 'HERB_V4_OFFLINE=on reads both query-side answers from the cache and raises '
               'where one is missing; off asks the model on a miss.',
}


def _offline():
    value = os.environ.get('HERB_V4_OFFLINE', 'off')
    if value not in ('off', 'on'):
        raise ValueError(f'HERB_V4_OFFLINE must be off or on, got {value!r}')
    return value == 'on'


def cache_root():
    return Path(os.environ.get('HERB_V4_CACHE',
                               str(ROOT / 'output/private/artefact_v4_cache')))


def _add(a, b):
    return ModelUsage(**{name: getattr(a, name) + getattr(b, name)
                         for name in ModelUsage.__dataclass_fields__})


@dataclass(frozen=True)
class Prepared:
    chunk_rows: tuple
    chunk_ids: tuple
    graph_tags: tuple
    tag_vectors: np.ndarray
    chunk_vectors: np.ndarray
    layer: dict
    tree: dict
    cache_dir: Path
    provenance: dict
    build_stats: BuildStats


def scope_tree(rows, kinds, channel_names):
    """The graph's structure as the tree shown to the model, and each place's chunks.

    rows: per pool chunk its product and its channel ids, in the arm's chunk order; kinds:
    each chunk's record kind; channel_names: channel id -> name. A place is a path: the
    product; the product and a record kind (`KIND_LABELS`); the product, "slack threads" and
    a channel. Returns the text (products, kinds and channels each in sorted order, two
    spaces a level, no counts) and per path the set of chunk indices under it."""
    if len(rows) != len(kinds):
        raise ValueError('Expected one record kind per chunk')
    paths = {}
    for i, (row, kind) in enumerate(zip(rows, kinds)):
        product = str(row['product'])
        label = KIND_LABELS.get(kind, kind.replace('_', ' '))
        if '/' in product or '/' in label:
            raise ValueError('A product or record kind holds the path separator')
        paths.setdefault(product, set()).add(i)
        paths.setdefault(f'{product}/{label}', set()).add(i)
        for channel in row['channels'] or ():
            name = str(channel_names.get(channel, channel)).replace('/', '-')
            paths.setdefault(f'{product}/{label}/#{name}', set()).add(i)
    lines = []
    for path in sorted(paths):
        parts = path.split('/')
        lines.append('  ' * (len(parts) - 1) + parts[-1])
    return {'text': '\n'.join(lines), 'paths': {p: frozenset(c) for p, c in paths.items()},
            'products': sum(1 for p in paths if '/' not in p),
            'places': len(paths)}


def scope_first(places, tree, n_chunks):
    """Per chunk whether it sits under the product of a returned place, and what was returned.
    A returned path the tree does not hold names no chunk and is counted."""
    known = [p for p in places if p in tree['paths']]
    first = np.zeros(n_chunks, dtype=bool)
    for path in known:
        first[list(tree['paths'][path.split('/')[0]])] = True
    return first, {'places_returned': list(places), 'places_in_the_tree': known,
                   'places_not_in_the_tree': [p for p in places if p not in tree['paths']],
                   'chunks_under_the_products': int(first.sum())}


def prepare_over_corpus(corpus) -> Prepared:
    """Once per run, from the graph: the tag and chunk description vectors, the edges with their
    five facet values, each chunk's product and file neighbours, and the tree."""
    started = time.perf_counter()
    RETRIEVAL_FLAGS['offline_at_prepare'] = _offline()
    from graph.db import _driver
    from arms.artefact_v3 import file_adjacency, load_shape
    say(f'artefact_v4: reading {DATABASE} tag vectors')
    cache = cache_root()
    driver = _driver()
    try:
        with driver.session(database=DATABASE, default_access_mode='READ') as session:
            tag_rows = session.execute_read(lambda tx: list(tx.run(TAG_CYPHER, run=RUN_ID)))
            say(f'artefact_v4: {len(tag_rows)} tag vectors read, reading chunk descriptions')
            chunk_rows = session.execute_read(lambda tx: list(tx.run(CHUNK_CYPHER, run=RUN_ID)))
            say(f'artefact_v4: {len(chunk_rows)} chunk vectors read, reading product names')
            product_names = session.execute_read(
                lambda tx: [r['name'] for r in tx.run(PRODUCT_CYPHER)])
            say(f'artefact_v4: {len(product_names)} products, reading the tag-to-chunk edges '
                'and the facet layer they carry')
            edge_rows = session.execute_read(lambda tx: list(tx.run(EDGE_CYPHER, run=RUN_ID)))
            layer_rows = session.execute_read(lambda tx: list(tx.run(LAYER_CYPHER, run=RUN_ID)))
            say(f'artefact_v4: {len(edge_rows)} edges read, reading the tree')
            scope_rows = session.execute_read(lambda tx: list(tx.run(SCOPE_CYPHER)))
            # landing.resolve_names keys its cache on NEO4J_DATABASE; this arm pins the
            # database, so the key names the database actually read.
            held = os.environ.get('NEO4J_DATABASE')
            os.environ['NEO4J_DATABASE'] = DATABASE
            try:
                names = LAND.resolve_names(session, cache=cache / 'landing_names.json')
            finally:
                if held is None:
                    os.environ.pop('NEO4J_DATABASE', None)
                else:
                    os.environ['NEO4J_DATABASE'] = held
        graph_tags = tuple(r['id'] for r in tag_rows)
        chunk_ids = tuple(r['chunkId'] for r in chunk_rows)
        if len(set(graph_tags)) != len(graph_tags) or len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError('Duplicate graph tag or chunk identity')
        tag_vectors = _unit(np.asarray([r['vector'] for r in tag_rows], dtype=np.float32))
        chunk_vectors = _unit(np.asarray([r['vector'] for r in chunk_rows], dtype=np.float32))
        at = {name: i for i, name in enumerate(graph_tags)}
        ci = {name: i for i, name in enumerate(chunk_ids)}
        graph_layer = GL.read([dict(r) for r in edge_rows], [dict(r) for r in layer_rows])
        endpoints, node = graph_layer.endpoints, graph_layer.node
        missing = [e for e in endpoints if e[0] not in at or e[1] not in ci]
        if missing:
            raise ValueError(f'{len(missing)} edges join a tag or a chunk the pool does not hold')
        edge_tag = np.array([at[t] for t, _ in endpoints], dtype=np.int64)
        edge_chunk = np.array([ci[c] for _, c in endpoints], dtype=np.int64)
        edge_topic = np.einsum('ij,ij->i', tag_vectors[edge_tag], chunk_vectors[edge_chunk])
        topic_apart = float(np.abs(np.asarray(edge_topic, dtype=np.float64)
                                   - graph_layer.values[:, 0]).max())
        if topic_apart > TOPIC_TOLERANCE:
            raise ValueError('The topic value on an edge differs from the cosine of its vectors '
                             f'by {topic_apart:.2g}: the layer was written from other vectors')
        chunk_kinds = tuple(str(r['kind'] or '') for r in chunk_rows)
        edgeless = int((np.bincount(edge_chunk, minlength=len(chunk_ids)) == 0).sum())
        tagless = int((np.bincount(edge_tag, minlength=len(graph_tags)) == 0).sum())
        if tagless:
            raise ValueError(f'{tagless} graph tags carry no edge into the product-linked pool')
        # A graph tag that is a product's name is structure, not a tag to match.
        folded = {name.casefold() for name in product_names}
        eligible = np.array([name.casefold() not in folded for name in graph_tags], dtype=bool)
        say(f'artefact_v4: {edgeless} chunks carry no edge; {int((~eligible).sum())} graph tags '
            'equal a product name and are left out')
        say('artefact_v4: reading each chunk\'s product and its neighbours in its file')
        with driver.session(database=DATABASE, default_access_mode='READ') as session:
            shape = session.execute_read(lambda tx: load_shape(
                tx, list(chunk_ids), ci, edge_tag, edge_chunk, list(graph_tags)))
        if (shape['product'] < 0).any():
            raise ValueError(f'{int((shape["product"] < 0).sum())} pool chunks have no product '
                             'in the structure read')
        adjacency = file_adjacency([dict(r) for r in chunk_rows])
        same_thing = WK.same_thing_level([_readable(t) for t in graph_tags], tag_vectors,
                                         eligible)
        if same_thing is None:
            raise ValueError('No two eligible graph tags are the same thing in another spelling')
        say(f'artefact_v4: the graph\'s same-thing tag pairs ({same_thing["pairs"]}) score '
            f'{same_thing["median"]:.3f} at the median; {same_thing["point"]}% lie under '
            f'{same_thing["level"]:.4f}')
        layer = WK.build_layer(chunk_ids, chunk_kinds, eligible, edge_tag, edge_chunk,
                               edge_topic, graph_layer.values[:, 1:], graph_layer.gaps,
                               same_thing['level'], shape['product'], adjacency['ptr'],
                               adjacency['members'])
        for value in (tag_vectors, chunk_vectors, *layer.values(),
                      *(a for pair in layer['groups'].values() for a in pair)):
            if isinstance(value, np.ndarray):
                value.setflags(write=False)
        found = {r['chunkId']: dict(r) for r in scope_rows}
        unplaced = [c for c in chunk_ids if c not in found]
        if unplaced:
            raise ValueError(f'{len(unplaced)} pool chunks have no product in the scope read')
        tree = scope_tree([found[c] for c in chunk_ids], chunk_kinds,
                          {l.node_id: l.name for l in names if l.kind == LAND.CHANNEL})
        say(f'artefact_v4: the tree: {tree["products"]} products, {tree["places"]} places, '
            f'{len(tree["text"])} characters')
        paths = [Path(__file__), ROOT / 'test/artefact/v4_walk.py',
                 ROOT / 'test/artefact/query_content.py', ROOT / 'test/artefact/querytagger.py',
                 ROOT / 'test/artefact/graph_layer.py', ROOT / 'test/artefact/landing.py',
                 ROOT / 'test/arms/artefact_facet_joint.py', ROOT / 'test/arms/artefact_v2.py',
                 ROOT / 'test/arms/artefact_v3.py', ROOT / 'prod/harness/chat.py',
                 ROOT / 'prod/harness/embed.py', ROOT / 'prod/harness/char_budget.py']
        near = layer['near']
        provenance = {
            'database': DATABASE, 'run_id': RUN_ID, 'corpus_argument': str(corpus),
            'interpreter_model': INTERPRET_MODEL,
            'facet_layer': dict(node),
            'topic_on_the_edge_against_the_vectors_max_abs': topic_apart,
            'same_thing_pairs': same_thing,
            'counts': {'chunks': len(chunk_ids), 'graph_tags': len(graph_tags),
                       'edges': len(endpoints), 'products': len(product_names),
                       'eligible_graph_tags': int(eligible.sum()),
                       'eligible_edges': int(layer['edges'].size),
                       'chunks_without_an_edge': edgeless,
                       'near_groups': int(near.max()) + 1,
                       'chunks_in_a_near_group': int((near >= 0).sum()),
                       'places': tree['places']},
            'source_sha256': {str(p.relative_to(ROOT)): _sha(p.read_bytes()) for p in paths},
        }
    finally:
        driver.close()
    elapsed = time.perf_counter() - started
    say(f'artefact_v4: prepared {len(chunk_ids)} chunks, {len(graph_tags)} tags, '
        f'{len(endpoints)} edges in {elapsed:.1f}s')
    return Prepared(tuple(dict(r) for r in chunk_rows), chunk_ids, graph_tags, tag_vectors,
                    chunk_vectors, layer, tree, cache, provenance,
                    BuildStats(elapsed, ModelUsage(), [INTERPRET_MODEL]))


def _collapse_duplicate_tags(raw):
    """The model sometimes writes one tag twice in a list; the first stays, the rest are
    dropped and counted, so a repeated phrase does not fail the question for good in the cache.
    Each list (tags, query_tags) is collapsed on its own."""
    if not isinstance(raw, dict) or not isinstance(raw.get('tags'), list):
        return raw, 0
    out, dropped = dict(raw), 0
    for field in ('tags', 'query_tags'):
        if not isinstance(raw.get(field), list):
            continue
        kept, seen = [], set()
        for row in raw[field]:
            name = row.get('t') if isinstance(row, dict) else None
            key = name.strip().casefold() if isinstance(name, str) else None
            if key is not None and key in seen:
                dropped += 1
                continue
            if key is not None:
                seen.add(key)
            kept.append(row)
        out[field] = kept
    return out, dropped


def _require_cached_answer(stage, system, user, schema, cache_dir):
    """The stage's answer must already sit in the cache as a good answer under the key
    `_cached_stage` reads; anything else raises before any model call."""
    signature = {'cache_version': 1, 'stage': stage, 'model': INTERPRET_MODEL,
                 'system': system, 'user': user, 'max_tries': 1, 'schema': schema}
    key = _sha(json.dumps(signature, sort_keys=True, ensure_ascii=False))
    path = Path(cache_dir) / stage / (key + '.json')
    if not path.is_file():
        raise RuntimeError(f'artefact_v4: HERB_V4_OFFLINE=on and no cached {STAGE_NAMES[stage]} '
                           f'answer (key {key}); no model call made')
    saved = json.loads(path.read_text(encoding='utf-8'))
    if not saved.get('ok') or saved.get('signature') != signature:
        raise RuntimeError(f'artefact_v4: HERB_V4_OFFLINE=on and the cached {STAGE_NAMES[stage]} '
                           f'answer is not a good answer (key {key}); no model call made')
    return key


def _ask(stage, request, validate, cache_dir, offline):
    """One cached model call under `stage` — the request is the instruction, the message and
    the answer's schema — asked once more when its own attempt came back unusable. Offline,
    only a good cached answer is read."""
    system, user, schema = request
    offline_key = (_require_cached_answer(stage, system, user, schema, cache_dir)
                   if offline else None)
    tries = 0
    while True:
        tries += 1
        try:
            value, used, cache = _cached_stage(stage, system, user, validate, cache_dir,
                                               INTERPRET_MODEL, schema)
            break
        except RuntimeError as failure:
            # The transport caches a failed answer (no JSON, a refusal) for good. One
            # re-ask: the cached failure is removed and the question asked again once.
            if offline or tries >= 2:
                raise
            key = str(failure).split('key=')[-1].split(';')[0].strip()
            path = Path(cache_dir) / stage / (key + '.json')
            marker = path.with_suffix('.started.json')
            own_attempt = 'no retry' in str(failure)
            if not own_attempt or not path.exists():
                raise  # a marker or a failure this process did not write is left as it is
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved.get('ok'):
                raise  # a good answer the arm's own validation rejected: not a re-ask case
            path.unlink()
            if marker.exists():
                marker.unlink()
            say(f'artefact_v4: {STAGE_NAMES[stage]} answer unusable ({failure}); asking once '
                'more')
    if offline and (not cache['cache_hit'] or cache['key'] != offline_key or used.calls):
        raise RuntimeError(f'artefact_v4: HERB_V4_OFFLINE=on and the {STAGE_NAMES[stage]} '
                           'answer was not the cached one')
    return value, used, {'stage': stage, 'cache_hit': cache['cache_hit'], 'key': cache['key'],
                         'asks': tries, 'offline': offline}


def _interpret(text, prepared):
    """The two query-side calls: the description and the tags, then the places. Returns the
    parsed content with its places, the model usage and one record a call."""
    offline = _offline()
    dropped = []

    def validate(raw):
        cleaned, n = _collapse_duplicate_tags(raw)
        dropped.append(n)
        return Q.parse(text, cleaned)

    content, usage, first = _ask('querytag', Q.request(text), validate, prepared.cache_dir,
                                 offline)
    first['duplicate_tags_dropped'] = dropped[-1] if dropped else None
    places, used, second = _ask('scope', Q.scope_request(content, prepared.tree['text']),
                                Q.parse_places, prepared.cache_dir, offline)
    return replace(content, places=places), _add(usage, used), [first, second]


@dataclass(frozen=True)
class _QueryAxes:
    tag_vectors: np.ndarray
    chunk_vectors: np.ndarray


def _tag_cosines(description, tags, prepared):
    """The tags and the description embedded together in the passage role: each tag's cosine to
    every graph tag and to the description, and the description's cosine to every chunk
    description. `_query_cosines` multiplies its unit vectors with the chunk matrix it is
    handed; handed the identity it returns the vectors themselves."""
    dim = prepared.chunk_vectors.shape[1]
    matrices, used, recipe = _query_cosines(
        description, tags, _QueryAxes(prepared.tag_vectors, np.eye(dim)), 'passage')
    tag_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
    description_vector = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
    if tag_vectors.shape != (len(tags), dim) or description_vector.shape != (dim,):
        raise ValueError('Expected one query vector per tag and one for the description')
    return ({'tags': np.asarray(matrices['query_tag_cosines'], dtype=np.float64),
             'description': description_vector @ prepared.chunk_vectors.T,
             'tags_to_description': tag_vectors @ description_vector}, used, recipe)


def answer_one_question(question, prepared: Prepared, generate, k: int = 50,
                        char_budget: int | None = None) -> ArmOutput:
    if not isinstance(question, (tuple, list)) or len(question) != 2:
        raise ValueError('Expected (question_id, raw_question)')
    qid, text = question
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Raw question must be nonempty text')
    if type(k) is not int or k < 1:
        raise ValueError('k must be a positive integer')
    if char_budget is not None and (type(char_budget) is not int or char_budget < 1):
        raise ValueError('char_budget must be a positive integer or None')
    started = time.perf_counter()
    chat.reset_timing()
    query, interp_usage, stages = _interpret(text, prepared)
    for stage in stages:
        say(f'artefact_v4: {qid} {stage["stage"]} cache_hit={stage["cache_hit"]} '
            f'asks={stage["asks"]} offline={stage["offline"]}')
    # The description-side tags are embedded with the description, then the question alone in
    # the query role, then the question-side tags with the description.
    tags = [t.text for t in query.tags]
    question_side = [t.text for t in query.query_tags]
    embeddings = {}
    got, embed_usage, recipe = _tag_cosines(query.description, tags, prepared)
    rows, to_description = list(got['tags']), got['tags_to_description'].tolist()
    d_description = got['description']
    embeddings['description_side_tags'] = {'tags': len(tags),
                                           'text_chars': len(query.description),
                                           'embedding': recipe['vector_sha256']}
    matrices, used, recipe = _query_cosines(query.question, [], prepared)
    embed_usage = _add(embed_usage, used)
    d_question = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
    embeddings['question'] = {'text_chars': len(query.question),
                              'embedding': recipe['vector_sha256']}
    if question_side:
        got, used, recipe = _tag_cosines(query.description, question_side, prepared)
        embed_usage = _add(embed_usage, used)
        rows += list(got['tags'])
        to_description += got['tags_to_description'].tolist()
        embeddings['question_side_tags'] = {'tags': len(question_side),
                                            'embedding': recipe['vector_sha256']}
    layer = prepared.layer
    walked = WK.chain(layer, {
        'cosines': np.array(rows, dtype=np.float64),
        'readings': np.array([t.readings for t in (*query.tags, *query.query_tags)],
                             dtype=np.float64),
        'description_cosines': np.array(to_description, dtype=np.float64),
        'd_description': d_description, 'd_question': d_question}, COS_NOISE)
    first, scope = scope_first(query.places, prepared.tree, len(prepared.chunk_ids))
    order = sorted(walked['order'], key=lambda i: not first[i])
    ordered_rows = [prepared.chunk_rows[i] for i in order]
    doc_cache = {}
    if char_budget is not None:
        contexts, id_lists, context_ids, budget = _budget_contexts(ordered_rows, char_budget,
                                                                   doc_cache)
        credited = int(budget['kept'])
        boundary = budget['boundary']['id'] if budget['boundary'] else None
    else:
        contexts, id_lists, context_ids, budget = [], [], [], None
        for row in ordered_rows[:k]:
            content, ids = _resolve_chunk(row, doc_cache)
            contexts.append(content)
            id_lists.append(ids)
            for aid in ids:
                if aid not in context_ids:
                    context_ids.append(aid)
        credited, boundary = len(contexts), None
    delivered = order[:credited]
    terms = {'tags': walked['tags'], 'description': walked['text'], **walked['lift']}
    sums = {name: float(terms[name][delivered].sum()) for name in TERMS}
    total = float(walked['strength'][delivered].sum())
    shares = {name: (sums[name] / total if total != 0. else None) for name in TERMS}
    levels = walked['level'][delivered]
    won = [bool(walked['has_edge'][i] and walked['tags'][i] != 0.) for i in delivered]
    scope['delivered_under_the_products'] = int(first[delivered].sum())
    diagnostics = {
        'credited_delivered_rows': len(delivered),
        'boundary_chunk_id_not_credited': boundary,
        'chunks_with_an_eligible_edge': int((layer['n_c'] > 0).sum()),
        'chunks_with_a_positive_tag_strength': int((walked['tags'] > 0).sum()),
        'product_named_tags_left_out': int((~layer['eligible']).sum()),
        'query_tags': len(rows),
        'phrases_standing_in_both_tag_lists': len({t.strip().casefold() for t in tags}
                                                  & {t.strip().casefold() for t in question_side}),
        'query_tag_bulk': walked['bulk'].tolist(),
        'query_tag_spread': walked['spread'].tolist(),
        'query_tag_centrality': walked['centrality'].tolist(),
        'query_tag_description_cosine': to_description,
        'same_thing_level': layer['same_level'],
        'same_thing_edges_per_query_tag': walked['same_edge'].sum(axis=1).tolist(),
        'delivered_winning_edge_is_a_same_thing_edge': [
            bool(walked['same_edge'][walked['winner'][i], walked['win_edge'][i]]) if w else None
            for i, w in zip(delivered, won)],
        'text_bulk': walked['text_bulk'], 'text_spread': walked['text_spread'],
        'delivered_rows_with_question_above_description': int(
            (walked['Qs'][delivered] > walked['D'][delivered]).sum()),
        'chunks_with_a_lift': {kind: int((walked['lift'][kind] > 0).sum())
                               for kind in WK.GROUPINGS},
        'largest_lift': {kind: float(walked['lift'][kind].max()) for kind in WK.GROUPINGS},
        'delivered_term_sums': sums, 'delivered_strength_total': total,
        'delivered_term_shares': shares,
        'level_step': float(walked['step']),
        'levels_among_delivered_rows': int(np.unique(levels).size),
    }
    say(f'artefact_v4 {qid}: {len(delivered)} delivered, '
        f'{scope["delivered_under_the_products"]} under the products of '
        f'{scope["places_in_the_tree"]}; shares '
        + ', '.join(f'{name} ' + ('none' if shares[name] is None else f'{shares[name]:.3f}')
                    for name in TERMS))
    ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
               'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
               'delivered_strength': [float(walked['strength'][i]) for i in delivered],
               'delivered_levels': [int(walked['level'][i]) for i in delivered],
               'delivered_terms': {name: [float(terms[name][i]) for i in delivered]
                                   for name in TERMS},
               'delivered_query_tags': [int(walked['winner'][i]) if w else -1
                                        for i, w in zip(delivered, won)]}
    retrieval = _add(interp_usage, embed_usage)
    for name, value in chat.take_timing().items():
        setattr(retrieval, name, value)
    meta = {'provenance': prepared.provenance,
            'interpreter': {'model': INTERPRET_MODEL, 'stages': stages,
                            'description_side_tags': len(tags),
                            'question_side_tags': len(question_side),
                            'embeddings': embeddings},
            'scope': scope, 'ranking': ranking, 'diagnostics': diagnostics,
            'chunk_ids': id_lists, 'returned': len(contexts), 'char_budget': budget}
    search_time = max(0., time.perf_counter() - started - interp_usage.time_s)
    if generate is None:
        answer, gen_usage = '', ModelUsage()
    else:
        gen_started = time.perf_counter()
        answer, gen_usage = unpack_generation(generate(text, contexts),
                                              time.perf_counter() - gen_started)
    return ArmOutput(answer=answer, contexts=contexts, context_ids=context_ids,
                     search_time_s=search_time, generator=gen_usage, retrieval=retrieval,
                     meta=meta)
