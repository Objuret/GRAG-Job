"""Original learned edge evidence. No ranking formula or corpus access.

Retain all five neural outputs separately from the original topic cosine.
Do not turn ranks into magnitudes, normalize across facets, or gate by topic.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import numpy as np

from artefact.query_content import FACETS, QueryContent


@dataclass(frozen=True)
class LearnedEdges:
    endpoints: tuple
    raw_scores: np.ndarray
    source_sha256: str
    overlay_sha256: str


def load(directory):
    directory = Path(directory)
    data = (directory / 'scores.jsonl').read_bytes()
    overlay_data = (directory / 'overlay.json').read_bytes()
    overlay = json.loads(overlay_data)
    digest = hashlib.sha256(data).hexdigest()
    if overlay['source_sha256'] != digest or overlay['facets'] != list(FACETS):
        raise ValueError('Learned score provenance mismatch')
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    endpoints = tuple((r['tag'], r['chunk_id']) for r in rows)
    values = np.asarray([[r[f] for f in FACETS] for r in rows], dtype=np.float64)
    if len(set(endpoints)) != len(endpoints) or not np.isfinite(values).all():
        raise ValueError('Invalid learned edge data')
    lookup = {(r['tag'], r['chunkId']): r['weights'] for r in overlay['edges']}
    if len(lookup) != len(overlay['edges']) or set(lookup) != set(endpoints):
        raise ValueError('Overlay endpoints differ from learned scores')
    for endpoint, scores in zip(endpoints, values):
        if lookup[endpoint] != [None, *scores[1:]]:
            raise ValueError('Overlay changed a learned auxiliary value')
    # Immutable storage; a caller cannot switch WRITEABLE back on.
    values = np.frombuffer(values.tobytes(), dtype=values.dtype).reshape(values.shape)
    return LearnedEdges(endpoints, values, digest, hashlib.sha256(overlay_data).hexdigest())


def connect(query, learned, *, query_tag_cosines, query_chunk_cosines,
            description_chunk_cosines, graph_tag_names, chunk_ids, topic_cosines):
    """Retain the query/edge relationship, without collapsing tags or facets.

    This is evidence assembly, not a selected chunk order. Matrices factorize
    every query-tag -> graph-tag -> chunk path without materializing copies of
    the learned layer or introducing a candidate cutoff.
    """
    if type(query) is not QueryContent or type(learned) is not LearnedEdges:
        raise TypeError('Query content and source-free learned edges required')
    tags = {name: i for i, name in enumerate(graph_tag_names)}
    chunks = {name: i for i, name in enumerate(chunk_ids)}
    if len(tags) != len(graph_tag_names) or len(chunks) != len(chunk_ids):
        raise ValueError('Duplicate graph identities')
    endpoints = [(i, tags[t], chunks[c]) for i, (t, c) in enumerate(learned.endpoints)
                 if t in tags and c in chunks]
    qn = len(query.tags)
    arrays = {
        'tag_match': (query_tag_cosines, (qn, len(tags))),
        'tag_description_match': (query_chunk_cosines, (qn, len(chunks))),
        'description_match': (description_chunk_cosines, (len(chunks),)),
        'topic_cosine': (topic_cosines, (len(learned.endpoints),)),
    }
    result = {}
    for name, (value, shape) in arrays.items():
        a = np.asarray(value, dtype=np.float64)
        if a.shape != shape or not np.isfinite(a).all():
            raise ValueError('Invalid evidence alignment: ' + name)
        result[name] = np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)
    result.update(query=query, learned=learned, edge_indices=tuple(endpoints),
                  omitted_endpoints=len(learned.endpoints)-len(endpoints),
                  graph_tag_names=tuple(graph_tag_names), chunk_ids=tuple(chunk_ids))
    return result
