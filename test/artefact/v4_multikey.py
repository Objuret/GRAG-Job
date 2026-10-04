"""artefact_v4's multi-key sort over every (query tag, graph tag, chunk) edge of a question.

Every edge (q, t, c) - q a query tag, t an eligible graph tag, c a chunk on t's HAS_TAG edge -
carries one key, compared part by part, the smaller first:

  fit          floor((best cos(q', t') over every edge of the question - cos(q, t)) / fit_step)
  facet 1..4   temporal, why, activity, concreteness in the order of q's own readings for them,
               largest first, equal readings in that listed order; per facet
               floor((best value of the column over the question's edges - the edge's value) /
               the column's gap). The value is the edge's mean score over the round-1 bootstrap
               refits, the quantity the flip gap was measured on: the gap is the smallest
               |difference of two edges' refit means| whose sign survives the refits. Two edges
               of different query tags meet in one slot on the facet each one's own query tag
               put there.
  landed       0 if the chunk sits in the question's landed area, else 1 (per chunk)
  seed         the chunk's distance to the seeds, the chunks an edge at fit level 0 reaches:
               0 a seed, 1 sharing a [:channel] node with a seed or file-adjacent to one, 2 under
               the same product as a seed, 3 otherwise (per chunk)
  topic        floor((best cos(t, chunk description) over the question's edges - cosine) / COS_NOISE)
  description  floor((best cos(query description, chunk description) over the chunks - cosine)
               / COS_NOISE)
  question     the same for cos(raw question, chunk description)
  id           the chunk id

landed and seed stand after the four facet slots (after_facets) or right after fit
(after_fit), or are absent. The edges are sorted on that key; a chunk takes the place of its
first edge in the sorted list, its best edge. Chunks no eligible edge reaches follow every
reached chunk, by the chunk's own keys in the same order. The stored files are read as they
are; nothing is written.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np

from artefact.v4_rank import ADJUST_FACETS, ALL_FACETS, COS_NOISE, _check_rows, _check_text, levels

FACET_SLOTS = ('facet1', 'facet2', 'facet3', 'facet4')
STRUCTURE_KEYS = ('landed', 'seed')
STRUCT_PLACES = ('after_facets', 'after_fit')
GAP_TABLE = '## per column'
# Inside one fit level the key compares edges of different chunks and different tags: the
# uniform edge-pair sample, "gap (any)".
GAP_COLUMN = 'gap (any)'


@dataclass(frozen=True)
class MultikeyLayer:
    values: np.ndarray   # (edges, 4) each edge's mean score over the refits, ADJUST_FACETS order
    gaps: np.ndarray     # (4,) each column's retrain flip gap, in the same units
    gap_source: dict
    value_source: dict


def read_refit_means(path, endpoints):
    """Each edge's mean score over the bootstrap refits, per facet, in the order of `endpoints`
    ((tag, chunk id) pairs), matched by the archive's edge id "chunk id::tag"."""
    path = Path(path)
    data = path.read_bytes()
    with np.load(path, allow_pickle=False) as archive:
        edge_ids = archive['edge_ids'].tolist()
        facets = archive['facets'].tolist()
        scores = archive['scores']
        seeds = archive['seeds'].tolist()
    if scores.ndim != 3 or scores.shape[:2] != (len(edge_ids), len(facets)):
        raise ValueError(f'Expected scores [edges, facets, draws] in {path}')
    if set(ADJUST_FACETS) - set(facets):
        raise ValueError(f'{path} lacks a facet of {ADJUST_FACETS}')
    at = {edge: i for i, edge in enumerate(edge_ids)}
    if len(at) != len(edge_ids):
        raise ValueError(f'Duplicate edge id in {path}')
    wanted = [f'{chunk}::{tag}' for tag, chunk in endpoints]
    missing = [edge for edge in wanted if edge not in at]
    if missing:
        raise ValueError(f'{len(missing)} edges have no refit scores in {path}')
    rows = np.array([at[edge] for edge in wanted], dtype=np.int64)
    columns = [facets.index(f) for f in ADJUST_FACETS]
    values = scores[rows][:, columns, :].astype(np.float64).mean(axis=2)
    if not np.isfinite(values).all():
        raise ValueError(f'A refit mean in {path} is not finite')
    return values, {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
                    'draws': int(scores.shape[2]), 'seeds': seeds,
                    'value': 'per-edge mean over the draws of each facet column'}


def read_facet_gaps(path, column=GAP_COLUMN):
    """Each facet's own retrain flip gap from BANDS.md's per-column table, read by column name,
    with the line each value was read from."""
    path = Path(path)
    lines = path.read_text(encoding='utf-8').splitlines()
    if GAP_TABLE not in lines:
        raise ValueError(f'No per-column table in {path}')
    header, found = None, {}
    for number in range(lines.index(GAP_TABLE) + 1, len(lines)):
        line = lines[number].strip()
        if line.startswith('## '):
            break
        if not line.startswith('|'):
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if header is None:
            if column not in cells:
                raise ValueError(f'No column {column!r} in the per-column table of {path}')
            header = cells
        elif cells[0] in ADJUST_FACETS:
            found[cells[0]] = (float(cells[header.index(column)]), number + 1)
    missing = [f for f in ADJUST_FACETS if f not in found]
    if missing:
        raise ValueError(f'No {column!r} gap for {missing} in {path}')
    gaps = tuple(found[f][0] for f in ADJUST_FACETS)
    if not all(np.isfinite(g) and g > 0 for g in gaps):
        raise ValueError('A facet gap must be a positive number')
    return gaps, {'path': str(path), 'table': 'per column', 'column': column,
                  'lines': {f: found[f][1] for f in ADJUST_FACETS}}


def build_layer(values, gaps, gap_source, value_source):
    """values: (edges, 4) per-edge facet values in ADJUST_FACETS order, in the gaps' units."""
    values = np.array(values, dtype=np.float64)
    if (values.ndim != 2 or values.shape[1] != len(ADJUST_FACETS)
            or not np.isfinite(values).all()):
        raise ValueError('Expected four finite facet values per edge')
    gaps = np.array(gaps, dtype=np.float64)
    if gaps.shape != (len(ADJUST_FACETS),) or not np.isfinite(gaps).all() or not (gaps > 0).all():
        raise ValueError('Expected one positive gap per facet')
    values.setflags(write=False)
    gaps.setflags(write=False)
    return MultikeyLayer(values, gaps, dict(gap_source), dict(value_source))


def facet_order(readings):
    """The four facets as indices into ADJUST_FACETS, the largest reading first; equal readings
    keep ADJUST_FACETS order. The topic reading is not read."""
    readings = np.asarray(readings, dtype=np.float64)
    if readings.shape != (len(ALL_FACETS),):
        raise ValueError('Expected five readings in ALL_FACETS order')
    values = [readings[ALL_FACETS.index(f)] for f in ADJUST_FACETS]
    return tuple(sorted(range(len(ADJUST_FACETS)), key=lambda j: (-values[j], j)))


def key_names(struct_at=None):
    """The per-chunk key in comparison order. Without the structure: reached, fit, the four
    facet slots, topic, description, question, id. after_facets puts landed and seed after
    the four facet slots, after_fit right after fit."""
    head, tail = ('reached', 'fit'), ('topic', 'description', 'question', 'id')
    if struct_at is None:
        return head + FACET_SLOTS + tail
    if struct_at == 'after_facets':
        return head + FACET_SLOTS + STRUCTURE_KEYS + tail
    if struct_at == 'after_fit':
        return head + STRUCTURE_KEYS + FACET_SLOTS + tail
    raise ValueError(f'struct_at must be one of {STRUCT_PLACES}, got {struct_at!r}')


@dataclass(frozen=True)
class Structure:
    adjacency_ptr: np.ndarray   # CSR: each chunk's file-adjacent chunks
    adjacency: np.ndarray
    channel_ptr: np.ndarray     # CSR: each chunk's [:channel] nodes
    channels: np.ndarray
    product: np.ndarray         # (chunks,) the chunk's product, -1 for none
    source: dict


def build_structure(adjacency, shape, source=None):
    """From artefact_v3's file_adjacency (ptr, members) and load_shape (chunk_group_ptr,
    chunk_groups, product), over one chunk order."""
    product = np.array(shape['product'], dtype=np.int64)
    n = product.size
    adjacency_ptr, adjacent, channel_ptr, channels = (
        np.array(a, dtype=np.int64) for a in (adjacency['ptr'], adjacency['members'],
                                              shape['chunk_group_ptr'], shape['chunk_groups']))
    for ptr, members in ((adjacency_ptr, adjacent), (channel_ptr, channels)):
        if (ptr.shape != (n + 1,) or ptr[0] != 0 or ptr[-1] != members.size
                or (np.diff(ptr) < 0).any() or (members.size and members.min() < 0)):
            raise ValueError('Expected one CSR row per chunk')
    if adjacent.size and adjacent.max() >= n:
        raise ValueError('A file-adjacent chunk is out of range')
    for array in (adjacency_ptr, adjacent, channel_ptr, channels, product):
        array.setflags(write=False)
    return Structure(adjacency_ptr, adjacent, channel_ptr, channels, product, dict(source or {}))


def seed_distance(is_seed, structure):
    """Per chunk: 0 a seed; 1 sharing a [:channel] node with a seed or file-adjacent to one;
    2 under the same product as a seed; 3 otherwise."""
    is_seed = np.asarray(is_seed, dtype=bool)
    n = is_seed.size
    if structure.product.shape != (n,):
        raise ValueError('Expected the structure over the same chunks')
    distance = np.full(n, 3, dtype=np.int64)
    if not is_seed.any():
        return distance
    product = structure.product
    seed_products = np.unique(product[is_seed & (product >= 0)])
    distance[(product >= 0) & np.isin(product, seed_products)] = 2
    near = np.zeros(n, dtype=bool)
    owner = np.repeat(np.arange(n, dtype=np.int64), np.diff(structure.channel_ptr))
    seed_channels = np.unique(structure.channels[is_seed[owner]])
    near[owner[np.isin(structure.channels, seed_channels)]] = True
    owner = np.repeat(np.arange(n, dtype=np.int64), np.diff(structure.adjacency_ptr))
    near[owner[is_seed[structure.adjacency]]] = True
    distance[near] = 1
    distance[is_seed] = 0
    return distance


def multikey_order(chunk_ids, edge_tag, edge_chunk, edge_topic, layer, eligible, query_tags,
                   d_description, d_question, *, fit_step, landed=None, structure=None,
                   struct_at='after_facets'):
    """The full order, and per chunk the key of the edge that placed it (`key_names`; -1 in the
    edge parts of a chunk no eligible edge reaches).

    query_tags: (fit row over graph tags, five readings) per query tag, both lists.
    landed and structure come together or not at all: landed is 0 for a chunk under the
    question's landed area and 1 otherwise, per chunk; the seeds are the chunks an edge at fit
    level 0 reaches, and `seed_distance` over the structure gives every chunk its distance.
    An exact tie between two edges of one chunk goes to the earlier query tag in the list.
    """
    if not (np.isfinite(fit_step) and fit_step > 0):
        raise ValueError('The fit equal width must be a positive number')
    if (landed is None) != (structure is None):
        raise ValueError('landed and structure come together')
    names = key_names(struct_at if structure is not None else None)
    n = len(chunk_ids)
    eligible = np.asarray(eligible, dtype=bool)
    edge_tag = np.asarray(edge_tag, dtype=np.int64)
    edge_chunk = np.asarray(edge_chunk, dtype=np.int64)
    edge_topic = np.asarray(edge_topic, dtype=np.float64)
    if not edge_tag.shape == edge_chunk.shape == edge_topic.shape == (layer.values.shape[0],):
        raise ValueError('Expected one tag, chunk, topic and facet value row per edge')
    rows = _check_rows(query_tags, eligible.size)
    chunk_level = {'description': levels(_check_text(d_description, n), COS_NOISE),
                   'question': levels(_check_text(d_question, n), COS_NOISE),
                   'id': np.empty(n, dtype=np.int64)}
    chunk_level['id'][sorted(range(n), key=lambda i: chunk_ids[i])] = np.arange(n)
    if structure is not None:
        landed = np.asarray(landed, dtype=np.int64)
        if landed.shape != (n,) or (landed < 0).any():
            raise ValueError('Expected one non-negative landed value per chunk')
        chunk_level['landed'] = landed
    orders = np.array([facet_order(readings) for _, readings in rows],
                      dtype=np.int64).reshape(len(rows), len(ADJUST_FACETS))
    column = {name: j for j, name in enumerate(names)}
    keys = np.full((n, len(names)), -1, dtype=np.int64)
    keys[:, column['reached']] = 1
    best_edge = np.full(n, -1, dtype=np.int64)
    best_query_tag = np.full(n, -1, dtype=np.int64)
    is_seed = np.zeros(n, dtype=bool)
    head = np.zeros(0, dtype=np.int64)
    fit_best = topic_best = column_best = None
    sel = np.flatnonzero(eligible[edge_tag])
    if rows and sel.size:
        m = sel.size
        tags_sel, chunks_sel = edge_tag[sel], edge_chunk[sel]
        values = layer.values[sel]
        column_best = values.max(axis=0)
        facet_level = np.floor((column_best - values) / layer.gaps).astype(np.int64)
        topic = edge_topic[sel]
        topic_best = float(topic.max())
        topic_level = np.floor((topic_best - topic) / COS_NOISE).astype(np.int64)
        fits = np.stack([fit[tags_sel] for fit, _ in rows])
        fit_best = float(fits.max())
        fit_level = np.floor((fit_best - fits) / fit_step).astype(np.int64)
        is_seed[chunks_sel[(fit_level == 0).any(axis=0)]] = True
    if structure is not None:
        chunk_level['seed'] = seed_distance(is_seed, structure)
    for name, per_chunk in chunk_level.items():
        keys[:, column[name]] = per_chunk
    if rows and sel.size:
        def spread(per_edge):
            return np.broadcast_to(per_edge, fits.shape).ravel()

        per_edge = {'fit': fit_level.ravel(), 'topic': spread(topic_level)}
        for k, slot in enumerate(FACET_SLOTS):
            per_edge[slot] = facet_level[:, orders[:, k]].T.ravel()
        for name, per_chunk in chunk_level.items():
            per_edge[name] = spread(per_chunk[chunks_sel])
        edge_keys = [per_edge[name] for name in names[1:]]
        ranked = np.lexsort(edge_keys[::-1])
        flat_chunk = np.tile(chunks_sel, len(rows))
        _, first = np.unique(flat_chunk[ranked], return_index=True)
        winner = ranked[np.sort(first)]
        q_of, e_of = np.divmod(winner, m)
        head = flat_chunk[winner]
        keys[head, column['reached']] = 0
        keys[head, column['fit']] = fit_level[q_of, e_of]
        for k, slot in enumerate(FACET_SLOTS):
            keys[head, column[slot]] = facet_level[e_of, orders[q_of, k]]
        keys[head, column['topic']] = topic_level[e_of]
        best_edge[head] = sel[e_of]
        best_query_tag[head] = q_of
    reached = keys[:, column['reached']] == 0
    tail = sorted(np.flatnonzero(~reached).tolist(), key=lambda i: tuple(keys[i].tolist()))
    result = {'order': head.tolist() + tail, 'reached': reached, 'keys': keys,
              'key_names': names, 'best_edge': best_edge, 'best_query_tag': best_query_tag,
              'facet_orders': [tuple(ADJUST_FACETS[j] for j in o) for o in orders.tolist()],
              'fit_best': fit_best, 'topic_best': topic_best,
              'facet_column_best': (None if column_best is None
                                    else dict(zip(ADJUST_FACETS, column_best.tolist()))),
              'edges_sorted': len(rows) * int(sel.size), 'seeds': int(is_seed.sum())}
    if structure is not None:
        result['landed_chunks'] = int((chunk_level['landed'] == 0).sum())
        result['seed_distance_histogram'] = {
            str(d): int((chunk_level['seed'] == d).sum()) for d in range(4)}
    return result
