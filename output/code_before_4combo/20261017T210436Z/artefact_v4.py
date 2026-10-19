"""artefact_v4: the artefact. Inside the border the question's name sets, the chunk cloud and the
tags' cloud together order the chunks, and the product's own work is handed over.

Per question:
  1. One model call writes a description of the content the question is looking for and two
     tag lists, one from that content and one from the question's own words, each tag with the
     one facet that matters most for it (`query_content.request`). Its input goes as marked
     parts and its answer is forced into a JSON schema.
  2. The border (his 2026-10-11 "if we take our latest best run, and do that part for scope
     instead"): every branch of the tree whose name stands in the question word for word
     (`scope_by_name`); the chunks outside it are out of the pool. No model call.
  3. The tags side: each chunk's closest tag to a query tag (`v4_walk.tags_nearness`). The
     query tags are embedded in the query role, as the graph's tags are.
  4. The facets (2026-10-15/16, `v4_walk.facet_influenced_nearness`): the facet instrument (the
     round-1 head that scored the graph's edges) reads the query tags against the question and
     the description; the middle reading per facet, its
     level among that facet's levels over the graph's edges, is the facet's weight for the whole
     question; an edge's weight is the tag's closeness plus, per facet, that weight times where
     the edge stands in the facet's ranking. Nothing forces the order.
  5. The chunk side: the chunk descriptions' closeness to the question with the border's names
     taken out (`_without_names`: inside the border the name tells nothing), embedded in the
     query role as the chunk descriptions are.
  6. The order (his 2026-10-12 "the combo should fucking work", `v4_walk.cloud_combo`): each
     side cut into HERB_V4_K clusters over the border; a chunk's step is its two levels added;
     the parents holding the majority of the first two steps' chunks are the scope, whose chunks
     come first inside a step.
  7. What is handed over (2026-10-13, the agent's find, `_hand_over`): in that order, each chunk
     without the records that are not the product's own work, and a conversation whole where it
     first shows. Whose work a record is comes from the graph's people (`product_persons`, read
     through the person-to-chunk edges): a channel none of whose employees is tied to another
     channel or to a meeting of the product is apart; a pull request is the product's own when
     its author is one of the product's people. The author, a message's links and its time are
     fields of the records, read through the chunk's pointer.
  8. The harness's cut at the character budget is applied to what is handed over.
Each delivered chunk keeps, as pointers, the query tag and graph tag that found it, its nearness
on each side and the records behind it.

HERB_V4_OFFLINE=on reads the first call's answer from the cache and raises where it is missing.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import time

import numpy as np

from harness import chat
from harness.char_budget import FIELDS as BUDGET_FIELDS, cut_at_budget
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from harness.fields import sub, whole
from harness.progress import say
from artefact import query_content as Q
from artefact import graph_layer as GL
from artefact import v4_walk as WK
from arms.artefact_facet_joint import _cached_stage, _query_cosines, _sha, _unit
from arms.artefact_v2 import _load_verified_doc, _resolve_chunk

ROOT = Path(__file__).resolve().parents[2]
DATABASE = 'herb-eval-volmax'
RUN_ID = 'pilot_full_herb'
# His 2026-10-06 "yes, sonnet on those". The model is part of the cache key.
INTERPRET_MODEL = 'claude-sonnet-5'
TOPIC_TOLERANCE = 1e-6
KIND_LABELS = {'document': 'documents', 'document_part': 'document parts',
               'meeting_chat_batch': 'meeting chats', 'meeting_transcript': 'meeting transcripts',
               'meeting_transcript_part': 'meeting transcript parts',
               'pr_batch': 'pull requests', 'slack_thread_batch': 'slack threads',
               'url_batch': 'urls'}
LEVELS = ('product', 'kind of record', 'channel')
STAGE_NAMES = {'querytag': 'querytagger'}
if GL.FACETS != WK.FACETS:
    raise RuntimeError('The graph layer and the arithmetic name different facets')

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
       f.rel_path AS relpath, f.sha256 AS sha256, c.kind AS kind,
       c.parent_ref AS parent, c.ordinal AS ordinal ORDER BY chunkId
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

# The graph's people: which employees post in which channel of a product, and which sit in its
# meetings, read through the chunks they are tied to (`test/graph/build_person_edges.py`; his
# 2026-10-17 "persons edges shouldnt go to scope directly, but to chunks instead"). What is made
# of them is `product_persons`.
CHANNEL_PEOPLE_CYPHER = '''
MATCH (p:Product)-[:slack]->(ch:Channel)
OPTIONAL MATCH (e:Employee)-[:chunk]->(:Chunk)-[:channel]->(ch)
RETURN p.name AS product, ch.id AS channel, collect(DISTINCT e.eid) AS people
'''

MEETING_PEOPLE_CYPHER = '''
MATCH (e:Employee)-[:chunk]->(c:Chunk)-[:product]->(p:Product)
WHERE c.kind IN ['meeting_transcript', 'meeting_transcript_part']
RETURN p.name AS product, collect(DISTINCT e.eid) AS people
'''
LINK = re.compile(r'https?://[^\s"\'<>\)\]|]+')

# The harness writes this into the run manifest.
RETRIEVAL_FLAGS = {
    'interpreter_model': INTERPRET_MODEL,
    'k_nearest': 'HERB_V4_K, 5 unless named: the number of clusters each side\'s nearness is cut '
                 'into over the border (`v4_walk.levels`).',
    'offline': 'HERB_V4_OFFLINE=on reads the first call\'s answer from the cache and raises where '
               'it is missing; off asks the model on a miss.',
    'retrieval': (
        'The border is every branch of the tree whose name stands in the question word for word '
        '(`scope_by_name`), the chunks outside it out of the pool. Inside it (`v4_walk.cloud_combo`): '
        'each chunk\'s closest eligible tag to a query tag, with the query\'s facets as an influence '
        'on the tag relationship (`v4_walk.facet_influenced_nearness`: the facet instrument reads the query '
        'tags against the question and the description, the middle reading per facet; its level '
        'among that facet\'s levels over the graph\'s edges is the facet\'s weight; an edge\'s weight '
        'is the tag\'s closeness plus, per facet, that weight times where the edge stands in the '
        'facet\'s ranking), and the chunk descriptions\' closeness to the question with the border\'s '
        'names taken out, each cut into HERB_V4_K clusters; a chunk\'s step is its two levels added; '
        'the parents holding the majority of the chunks on the first two steps are the scope, whose '
        'chunks come first inside a step, then the two standings added. What is handed over, in that '
        'order (`_hand_over`): no message of a channel apart; of a batch of pull requests only the '
        'product\'s own; of a batch of Slack messages only the conversations that are not about '
        'another project\'s pull request, each conversation whole where it first shows; any other '
        'chunk as it is. From the graph (`product_persons`, through the person-to-chunk edges): a '
        'channel is apart when it has employees and none of them is tied to another channel or to a '
        'meeting of the product; the product\'s people are the employees of its other channels and '
        'of its meetings. From the records, through the chunk\'s pointer: a pull request is the '
        'product\'s own when its author is one of the product\'s people; a conversation is a '
        'channel\'s messages between its long gaps (`v4_walk.conversations`, no length given); it '
        'is about another project\'s when a message of it links to a pull request that is not the '
        'product\'s own and none links to an own pull request or to a document of the product. The '
        'handing over is the agent\'s find, read off the benchmark\'s own account of the distraction '
        'it holds (arXiv 2506.23139), not his concept; it never reads the question.'),
}
# The words for what only this arm writes into a run folder (harness.fields, FIELDS.md).
FIELDS = {
    'meta': sub("What the arm recorded about this question's retrieval.", {
        'provenance': sub('What the retrieval was made from, read once when the run started.', {
            'database': 'The graph database that was read.',
            'run_id': 'The run of tag-to-chunk edges read from it.',
            'corpus_argument': 'The corpus the harness named when it started the arm. The arm '
                               'reads the graph, not that corpus.',
            'interpreter_model': 'The model of the first call.',
            'facet_layer': whole("The graph's FacetLayer node as it stood: what the facet values "
                                 'on the tag-to-chunk edges were made from.'),
            'topic_on_the_edge_against_the_vectors_max_abs':
                "The largest difference, over the edges, between the topic value on the edge "
                "and the cosine of the tag's vector and the chunk description's vector.",
            'counts': sub('What was read from the graph.', {
                'chunks': 'Chunks in the pool.',
                'graph_tags': 'Tags that sit on a chunk of the pool.',
                'edges': 'Tag-to-chunk edges read.',
                'products': 'Products.',
                'eligible_graph_tags': "Tags that are not a product's name; only those are "
                                       'compared with the query tags.',
                'eligible_edges': 'Edges that carry such a tag.',
                'chunks_without_an_edge': 'Chunks that carry no such edge.',
                'places': 'Places in the tree: products, kinds of record under them, channels '
                          'under those.',
                'channels_apart': "Channels the graph's people set apart: a channel with "
                                  'employees none of whom is tied to another channel or to a '
                                  'meeting of its product.',
                'people': "Employees tied to a product's channel that is not apart or to its "
                          'meetings, counted once a product.',
            }),
            'source_sha256': whole('The sha256 of each code file the retrieval ran from, by '
                                   'path.'),
        }),
        'interpreter': sub("The first call and what was embedded for the query side.", {
            'model': 'The model of the first call.',
            'stages': sub('One entry a model call of the query side.', {
                'stage': 'Which call: querytag is the first call.',
                'cache_hit': 'Whether its answer was read from the cache instead of asked.',
                'key': "The cache key: the sha256 of the call's instruction, message, schema "
                       'and model.',
                'asks': 'How many times the call was made for this question.',
                'offline': 'Whether the run refused to ask the model.',
                'duplicate_tags_dropped': 'How many tags of the answer were left out because '
                                          'the same phrase stood there twice.',
            }),
            'description_side_tags': 'How many query tags the first call wrote from the '
                                     'content it described.',
            'question_side_tags': "How many it wrote from the question's own words.",
            'embeddings': sub('What was embedded, each in the query role.', {
                'description_side_tags': sub('The description and the tags written from it.', {
                    'tags': 'How many tags.',
                    'text_chars': "The description's length in characters.",
                    'embedding': 'The sha256 of the vectors.',
                }),
                'question': sub('The question as asked.', {
                    'text_chars': 'Its length in characters.',
                    'embedding': 'The sha256 of its vector.',
                }),
                'question_side_tags': sub("The tags written from the question's own words.", {
                    'tags': 'How many tags.',
                    'embedding': 'The sha256 of the vectors.',
                }),
                'question_without_the_names': sub(
                    "The question with the border's names taken out, each replaced by \"the\" "
                    "and the tree's word for that level. The chunk side is compared with this.", {
                        'text_chars': 'Its length in characters.',
                        'embedding': 'The sha256 of its vector.',
                    }),
            }),
        }),
        'scope': sub('The border, and the scope inside it.', {
            'names_in_the_question': 'The branches of the tree whose name stands in the '
                                     'question word for word. They are the border.',
            'nothing_cut': 'Whether no such name stood there, so every chunk stayed in the pool.',
            'chunks_under_the_products': 'Chunks under the named branches.',
            'chunks_kept': 'Chunks the order was made of.',
            'chunks_cut': 'Chunks left out of the pool by the border.',
            'delivered_under_the_products': 'How many of the delivered chunks sit under the '
                                            'named branches.',
            'combo': sub("The two clouds and the scope gauged from them.", {
                'k': 'The number of clusters each side was cut into.',
                'chunks': 'Chunks of the border.',
                'clouds': sub('Chunks in the first cluster of each side.', {
                    'tags': "Of the chunks' closest tag to a query tag.",
                    'description': "Of the chunk descriptions' closeness to the question "
                                   "without the names.",
                }),
                'chunks_on_each_step': whole('How many chunks stand on each step; a step is the '
                                             "chunk's two levels added, 2 the first."),
                'scope_gauged_from_chunks': 'How many chunks the scope was gauged from: those '
                                            'on the first two steps.',
                'scopes_taken': 'The parents that hold the majority of those chunks. A parent '
                                "is a channel, or a product's documents, transcripts, pull "
                                'requests, links or chats.',
                'chunks_in_scope': 'Chunks of the border under those parents.',
            }),
            'facets': sub("The query's facets as an influence on the tag relationship: the "
                          "facet instrument reads each query tag against the question and the "
                          "description; the middle reading per facet, its level among that "
                          "facet's levels over the graph's edges, is the facet's weight (0 to 1) "
                          "for the whole question; an edge's weight for a query tag is the tag's "
                          "closeness plus, per facet, that weight times where the edge stands in "
                          "the facet's ranking, in the query tag's own spread of closeness.", {
                'readings': whole("Per query tag as written, the facet instrument's four scores: "
                                  'temporal, why, activity, concreteness.'),
                'weights': whole("For the question, the four facets' weights from 0 to 1, in "
                                 'that order.'),
                'chunks_whose_nearness_changed': "Chunks of the border whose nearness through "
                                                 'their tags the facets changed.',
            }),
        }),
        'ranking': sub('The order, and what lies behind each delivered chunk. The lists that '
                       'start with delivered_ have one entry a delivered chunk, in delivered '
                       'order.', {
            'ordered_chunk_ids': "Every chunk of the border in the arm's order, by chunk id.",
            'delivered_chunk_ids': 'The chunks whose text, what was handed over of them, went '
                                   'in whole before the budget ended, by chunk id.',
            'delivered_step': "The chunk's step: its two levels added, 2 the first.",
            'delivered_tags_level': "The cluster of its closest tag's closeness, 1 the nearest.",
            'delivered_description_level': "The cluster of its description's closeness to the "
                                           'question without the names, 1 the nearest.',
            'delivered_in_scope': 'Whether it sits under a parent of the scope.',
            'delivered_value': "The two sides' standings added: each nearness less its middle "
                               "over its spread, over the border's chunks.",
            'delivered_tags_nearness': 'The cosine of its closest tag to a query tag.',
            'delivered_description_nearness': "The cosine of its description to the question "
                                              'without the names.',
            'delivered_query_description_nearness': "The cosine of its description to the "
                                                    "first call's description. It does not "
                                                    'enter the order.',
            'delivered_question_nearness': 'The cosine of its description to the question as '
                                           'asked. It does not enter the order.',
            'delivered_query_tags': 'Which query tag its closest tag is closest to, counted '
                                    'from 0 over the two tag lists; -1 for a chunk with no '
                                    'eligible tag.',
            'delivered_graph_tags': 'That closest tag, by name; empty for such a chunk.',
            'delivered_query_tag_phrases': 'That query tag as the first call wrote it; empty '
                                           'for such a chunk.',
            'delivered_tags_nearness_as_found': "The cosine of its closest tag to a query tag "
                                                "before the facets' influence; "
                                                "delivered_tags_nearness is the one after it.",
            'delivered_records': 'How many records were handed over with the chunk.',
            'delivered_records_of_other_chunks': 'How many of those lie in another chunk: the '
                                                 'rest of a conversation this chunk holds a '
                                                 'part of.',
            'delivered_records_not_handed_over': "How many of the chunk's own records were not "
                                                 "handed over with it: not the product's own "
                                                 'work, or handed over before with another '
                                                 'chunk.',
        }),
        'handed_over': sub("What of the ordered chunks was handed over and what was left out. "
                           "The counts are over the chunks gone through until the budget was "
                           "full.", {
            'products': whole("Per product of the border, what the graph's people say: the ids "
                              'of its channels apart, and how many people the product has.'),
            'chunks_gone_through': 'How many chunks of the order were gone through.',
            'chunks_with_nothing_handed_over': sub('Of those, the chunks nothing was handed '
                                                   'over of.', {
                'in_a_channel_apart': 'All its messages lie in a channel apart.',
                'no_own_pull_request': "A batch of pull requests none of which is the "
                                       "product's own.",
                'no_conversation_left': "A batch of messages whose conversations are about "
                                        "another project's pull request or were handed over "
                                        'before with another chunk.',
            }),
            'records_left_out': sub("Records of those chunks that are not the product's own "
                                    'work.', {
                'messages_of_a_channel_apart': 'Messages of a channel apart.',
                'pull_requests_of_other_projects': "Pull requests whose author is not one of "
                                                   "the product's people.",
                'messages_about_another_projects_pull_request':
                    "Messages of a conversation that links to another project's pull request "
                    'and to no own pull request or document.',
            }),
            'conversations_handed_over': 'Conversations handed over whole.',
            'conversations_reaching_into_another_chunk': 'Of those, the conversations with '
                                                         'messages in another chunk than the '
                                                         'one they first showed in.',
        }),
        'diagnostics': sub('Counts that say how the order came about.', {
            'credited_delivered_rows': 'How many texts went in whole before the budget ended.',
            'boundary_chunk_id_not_credited': 'The record id of the chunk that was cut where '
                                              'the budget ended; empty when none was.',
            'chunks_with_an_eligible_edge': 'Chunks of the pool that carry a tag which is not '
                                            "a product's name.",
            'product_named_tags_left_out': "Tags that are a product's name and are not "
                                           'compared.',
            'query_tags': 'Query tags in the two lists together.',
            'phrases_standing_in_both_tag_lists': 'Phrases the first call wrote in both lists.',
            'named_facets': 'The facet the first call named for each query tag. The arm does '
                            'not read it.',
            'query_tag_closest_graph_tag': "Per query tag, the cosine of its closest graph tag.",
            'delivered_on_each_step': whole('How many of the delivered chunks stand on each '
                                            'step.'),
            'delivered_in_scope': 'How many of the delivered chunks are in scope.',
            'delivered_dealt_another_closeness': "How many of the delivered chunks the facets' "
                                                 'influence gave another nearness.',
        }),
        'chunk_ids': 'The record ids behind each delivered text, one list a text.',
        'returned': 'How many texts were handed over, the one cut at the budget counted.',
        'char_budget': BUDGET_FIELDS,
    }),
    'index': 'Empty: this arm builds no index of its own. It reads the graph (graph in this '
             'file, provenance in each row).',
    'retrieval_flags': whole("The arm's switches in the arm's own words, by name: what each one "
                             'does, not what it was set to. What was set on the command line is '
                             'in flags; the entries that end in _at_prepare say what the run '
                             'started with.'),
}


def _k_nearest():
    """HERB_V4_K, 5 unless named (his 2026-10-09 "what if we force the n of k in the kNN
    instead?", "5 for the total amount of k?"): the number of clusters a list of nearness values
    is cut into."""
    value = os.environ.get('HERB_V4_K', '5')
    if not value.isdigit() or int(value) < 1:
        raise ValueError(f'HERB_V4_K must be a count, got {value!r}')
    return int(value)


def _offline():
    value = os.environ.get('HERB_V4_OFFLINE', 'off')
    if value not in ('off', 'on'):
        raise ValueError(f'HERB_V4_OFFLINE must be off or on, got {value!r}')
    return value == 'on'


def _query_facet_readings(query, phrases):
    """Per query tag the facet instrument's four scores (temporal, why, activity, concreteness), the
    instrument that scored the graph's edges (his 2026-10-09 "we DID build that neural net for judging the
    facets, why the fuck is the model doing that work then?", "what we need to carefully make, is
    the chunk text equivalent from the query"): each query tag read against the question and the
    first call's description. No model call."""
    from artefact import query_facets as QF
    return QF.head_scores(list(phrases), f'{query.question}\n\n{query.description}')[:, 1:]


_FLOORS = {}


def _facet_floors(layer):
    """The levels of each facet over the graph's edges (`v4_walk.facet_levels`), read once."""
    key = id(layer)
    if key not in _FLOORS:
        _FLOORS[key] = WK.facet_levels(layer['raw'][:, 1:])
    return _FLOORS[key]


def _facet_weights(readings, floors):
    """How much each facet matters (his 2026-10-16 "how important the facet conecpt is for the
    question/tag", "a yeah, pretty important to, nope, not at all", "what if it's still quite
    fucking unimportant"): a reading's level among its facet's levels over the graph's edges
    (`v4_walk.facet_levels`, the knees deciding how many), as a weight: the highest level 1, the
    levels stepping evenly down, a reading in no level 0 (`v4_walk.level_relevancy`)."""
    return [float(WK.level_relevancy(np.array([WK.facet_level(float(r), floors[f])]),
                                     len(floors[f]))[0]) for f, r in enumerate(readings)]


def tree_level(tree, level):
    """The scopes at one level of the tree, as (path, chunk indices): `product` the products
    with everything under them (a branch; his 2026-10-09 "if majority of something, BRANCH is
    chosen"), `kind` the product/kind places."""
    depth = {'product': 1, 'kind': 2}[level]
    return [(path, np.array(sorted(tree['paths'][path]), dtype=np.int64))
            for path in sorted(tree['paths']) if path.count('/') == depth - 1]


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
    persons: dict | None = None


def product_persons(channel_rows, meeting_rows):
    """What the graph's people say about each product (his 2026-10-11 "things related to
    persons ... nothing at all is actually using the graph").

    channel_rows: per channel of a product the employees that post in it; meeting_rows: per
    product the employees that sit in its meetings. A channel is apart when it has employees
    and none of them posts in another channel of the product or sits in one of its meetings (a
    team that works on nothing else of the product). The product's people are the employees of
    its other channels and of its meetings. Returns product -> the ids of its channels apart
    and its people. No name of a channel or a person is read and no number is given."""
    channels, meetings = {}, {}
    for row in channel_rows:
        channels.setdefault(str(row['product']), {})[str(row['channel'])] = frozenset(
            str(e) for e in row['people'] if e is not None)
    for row in meeting_rows:
        meetings[str(row['product'])] = frozenset(str(e) for e in row['people'] if e is not None)
    out = {}
    for product in sorted(set(channels) | set(meetings)):
        held, met = channels.get(product, {}), meetings.get(product, frozenset())
        apart = frozenset(
            channel for channel, who in held.items()
            if who and not who & met.union(*(w for other, w in held.items() if other != channel)))
        out[product] = {'apart': apart,
                        'people': met.union(*(w for channel, w in held.items()
                                              if channel not in apart))}
    return out


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


def _plain(text):
    """The text in lower case, everything but letters and digits as one space, a space at each end."""
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', str(text).lower()).strip() + ' '


def scope_by_name(question, tree, n_chunks):
    """Per chunk whether it sits under a branch of the tree whose name stands in the question
    word for word (letters and digits compared, case left aside), and which names stand there.
    With no such name no chunk is marked."""
    words = _plain(question)
    named = [path for path, _ in tree_level(tree, 'product')
             if _plain(path).strip() and _plain(path) in words]
    first = np.zeros(n_chunks, dtype=bool)
    for path in named:
        first[list(tree['paths'][path])] = True
    return first, {'names_in_the_question': named, 'nothing_cut': not named,
                   'chunks_under_the_products': int(first.sum())}


def _without_names(question, names):
    """The question with each of the names taken out: wherever a name stands word for word
    (letters and digits compared, case left aside, as `scope_by_name` finds it), "the" and the
    tree's word for that level stand in its place, so the sentence stays whole."""
    out = question
    for name in names:
        parts = re.findall(r'[a-z0-9]+', name.lower())
        if not parts:
            continue
        found = re.compile(r'(?<![A-Za-z0-9])' + r'[^A-Za-z0-9]*'.join(map(re.escape, parts))
                           + r'(?![A-Za-z0-9])', re.IGNORECASE)
        out = found.sub('the ' + LEVELS[name.count('/')], out)
    return ' '.join(out.split())


def _pointed_records(row, cache):
    """The records a chunk's pointer leads to, as they stand in the product's file."""
    loc = json.loads(row['locator'])
    held = _load_verified_doc(row['relpath'], row['sha256'], cache)[loc['section']]
    return [held[i] for i in (loc['indices'] if 'indices' in loc else [loc['index']])]


def _seconds(stamp):
    """A record's time in seconds on one clock; a time with no zone is read as it stands."""
    when = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    return (when.replace(tzinfo=None) - datetime(1970, 1, 1)).total_seconds()


def _links(text):
    """The links a text holds, as they are compared: lower case, no closing mark or slash."""
    return {found.rstrip('.,;:!?').rstrip('/').lower() for found in LINK.findall(str(text))}


def own_work(inside, prepared, doc_cache):
    """Which records behind the border's chunks are the product's own work, and the
    conversations its messages form. The graph's people say whose a thing is (`product_persons`);
    the author of a pull request, a message's links and its time are fields of the records,
    read through each chunk's pointer.

    apart     the messages in a channel apart (a message's channel is its record's; the graph
              ties a chunk to that channel, and to two where two channels bear one name)
    own       per pull request id whether its author is one of the product's people
    talk      per message id its conversation: a channel's messages between its long gaps
              (`v4_walk.conversations`)
    messages  per conversation its messages, in the order written
    other     the conversations about another project's pull request: a message links to a
              pull request that is not the product's own, and none links to an own pull request
              or to a document of the product
    """
    if prepared.persons is None:
        raise ValueError("The graph's people were not read: the run did not start with this step")
    rows = prepared.chunk_rows
    apart, own, talk, messages, other = set(), {}, {}, {}, set()
    channels, things = {}, {}
    for i in inside:
        row = rows[i]
        product, kind = row['product'], row['kind']
        who = prepared.persons[product]
        if kind == 'slack_thread_batch':
            for record in _pointed_records(row, doc_cache):
                channel = str(record['Channel']['channelID'])
                if channel not in row['channels']:
                    raise ValueError(f'A message of the Slack chunk {row["chunkId"]} lies in a '
                                     'channel the graph does not tie the chunk to')
                if channel in who['apart']:
                    apart.add(str(record['id']))
                else:
                    channels.setdefault((product, channel), {})[str(record['id'])] = record
        elif kind == 'pr_batch':
            for record in _pointed_records(row, doc_cache):
                mine = str(record['user']['login']) in who['people']
                own[str(record['id'])] = mine
                things.setdefault(product, {}).update(dict.fromkeys(_links(record['link']), mine))
        elif kind in ('document', 'document_part'):
            for record in _pointed_records(row, doc_cache):
                things.setdefault(product, {}).update(
                    dict.fromkeys(_links(record['document_link']), True))
    for (product, channel), held in channels.items():
        line = sorted(held.values(),
                      key=lambda r: (_seconds(r['Message']['User']['timestamp']), str(r['id'])))
        numbers = WK.conversations([_seconds(r['Message']['User']['timestamp']) for r in line])
        for record, number in zip(line, numbers.tolist()):
            key = (product, channel, number)
            talk[str(record['id'])] = key
            messages.setdefault(key, []).append(record)
        known = things.get(product, {})
        for number in sorted(set(numbers.tolist())):
            key = (product, channel, number)
            linked = {known[link] for record in messages[key]
                      for link in _links(record['Message']['User']['text']) if link in known}
            if linked == {False}:
                other.add(key)
    return {'apart': apart, 'own': own, 'talk': talk, 'messages': messages, 'other': other}


def _hand_over(order, prepared, char_budget, k, doc_cache):
    """What is handed over of the ordered chunks, and the record of it (the step as it stands).

    In the order: no message of a channel apart; of a batch of pull requests only the
    product's own; of a batch of Slack messages the conversations that are not about another
    project's pull request, each whole where it first shows (its messages in other chunks come
    with it and are not handed over again); any other chunk as it is. The harness's cut is
    applied to these texts (`cut_at_budget`); with no budget the first k are handed over.

    Returns the texts, the record ids behind each text, the record ids handed over whole, the
    cut's block, the chunks handed over whole, and what a row keeps of it."""
    rows = prepared.chunk_rows
    book = own_work(order, prepared, doc_cache)
    units, seen = [], set()
    nothing, left, whole_talks = Counter(), Counter(), [0, 0]
    gone = [0]

    def stream():
        for i in order:
            row, kind = rows[i], rows[i]['kind']
            gone[0] += 1
            if kind == 'slack_thread_batch':
                held = [str(record['id']) for record in _pointed_records(row, doc_cache)]
                mine = [m for m in held if m not in book['apart']]
                left['messages_of_a_channel_apart'] += len(held) - len(mine)
                if not mine:
                    nothing['in_a_channel_apart'] += 1
                    continue
                here = list(dict.fromkeys(book['talk'][m] for m in mine))
                left['messages_about_another_projects_pull_request'] += sum(
                    1 for m in mine if book['talk'][m] in book['other'])
                new = [t for t in here if t not in book['other'] and t not in seen]
                if not new:
                    nothing['no_conversation_left'] += 1
                    continue
                seen.update(new)
                records = [record for t in new for record in book['messages'][t]]
                ids = [str(record['id']) for record in records]
                whole_talks[0] += len(new)
                whole_talks[1] += sum(1 for t in new if any(
                    str(record['id']) not in mine for record in book['messages'][t]))
                unit = {'chunk': i, 'ids': ids, 'of_other_chunks': len(set(ids) - set(mine)),
                        'not_handed_over': len(set(held) - set(ids))}
            elif kind == 'pr_batch':
                held = _pointed_records(row, doc_cache)
                records = [record for record in held if book['own'][str(record['id'])]]
                left['pull_requests_of_other_projects'] += len(held) - len(records)
                if not records:
                    nothing['no_own_pull_request'] += 1
                    continue
                unit = {'chunk': i, 'ids': [str(record['id']) for record in records],
                        'of_other_chunks': 0, 'not_handed_over': len(held) - len(records)}
            else:
                text, ids = _resolve_chunk(row, doc_cache)
                units.append({'chunk': i, 'ids': [str(x) for x in ids], 'of_other_chunks': 0,
                              'not_handed_over': 0})
                yield row['chunkId'], text
                continue
            units.append(unit)
            # a chunk's text as `_resolve_chunk` writes it: its records as JSON, one a line
            yield row['chunkId'], '\n'.join(json.dumps(record, ensure_ascii=False)
                                            for record in records)

    if char_budget is not None:
        cut = cut_at_budget(stream(), char_budget)
        contexts, kept = cut.contexts, cut.kept
        budget = {'budget': char_budget, 'chars': cut.chars, 'kept': cut.kept,
                  'boundary': cut.boundary, 'exhausted': cut.exhausted}
    else:
        contexts = [text for _, (_, text) in zip(range(k), stream())]
        kept, budget = len(contexts), None
    context_ids = list(dict.fromkeys(aid for unit in units[:kept] for aid in unit['ids']))
    delivered = [unit['chunk'] for unit in units[:kept]]
    products = sorted({rows[i]['product'] for i in order})
    record = {
        'products': {name: {'channels_apart': sorted(prepared.persons[name]['apart']),
                            'people': len(prepared.persons[name]['people'])} for name in products},
        'chunks_gone_through': gone[0],
        'chunks_with_nothing_handed_over': {name: nothing[name] for name in (
            'in_a_channel_apart', 'no_own_pull_request', 'no_conversation_left')},
        'records_left_out': {name: left[name] for name in (
            'messages_of_a_channel_apart', 'pull_requests_of_other_projects',
            'messages_about_another_projects_pull_request')},
        'conversations_handed_over': whole_talks[0],
        'conversations_reaching_into_another_chunk': whole_talks[1],
    }
    per_chunk = {'delivered_records': [len(unit['ids']) for unit in units[:kept]],
                 'delivered_records_of_other_chunks': [unit['of_other_chunks']
                                                       for unit in units[:kept]],
                 'delivered_records_not_handed_over': [unit['not_handed_over']
                                                       for unit in units[:kept]]}
    return (contexts, [unit['ids'] for unit in units], context_ids, budget, delivered,
            {'record': record, 'per_chunk': per_chunk})


def prepare_over_corpus(corpus) -> Prepared:
    """Once per run, from the graph: the tag and chunk description vectors, the edges with their
    five facet values, each chunk's product and channels, the tree, and the people of each
    product's channels and meetings."""
    started = time.perf_counter()
    RETRIEVAL_FLAGS['offline_at_prepare'] = _offline()
    RETRIEVAL_FLAGS['k_at_prepare'] = _k_nearest()
    from graph.db import _driver
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
            say('artefact_v4: reading the people of each product\'s channels and meetings')
            persons = product_persons(
                session.execute_read(lambda tx: [dict(r) for r in tx.run(CHANNEL_PEOPLE_CYPHER)]),
                session.execute_read(lambda tx: [dict(r) for r in tx.run(MEETING_PEOPLE_CYPHER)]))
    finally:
        driver.close()
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
    layer = WK.build_layer(chunk_ids, chunk_kinds, eligible, edge_tag, edge_chunk, edge_topic,
                           graph_layer.values[:, 1:])
    for value in (tag_vectors, chunk_vectors, *layer.values()):
        if isinstance(value, np.ndarray):
            value.setflags(write=False)
    found = {r['chunkId']: dict(r) for r in scope_rows}
    unplaced = [c for c in chunk_ids if c not in found]
    if unplaced:
        raise ValueError(f'{len(unplaced)} pool chunks have no product in the scope read')
    tree = scope_tree([found[c] for c in chunk_ids], chunk_kinds, {})
    say(f'artefact_v4: the tree: {tree["products"]} products, {tree["places"]} places')
    missing = sorted({found[c]['product'] for c in chunk_ids} - set(persons))
    if missing:
        raise ValueError(f'The graph names no channel and no meeting for {missing}')
    paths = [Path(__file__), ROOT / 'test/artefact/v4_walk.py',
             ROOT / 'test/artefact/query_content.py', ROOT / 'test/artefact/query_facets.py',
             ROOT / 'test/artefact/graph_layer.py', ROOT / 'test/arms/artefact_facet_joint.py',
             ROOT / 'test/arms/artefact_v2.py', ROOT / 'prod/harness/chat.py',
             ROOT / 'prod/harness/embed.py', ROOT / 'prod/harness/char_budget.py']
    provenance = {
        'database': DATABASE, 'run_id': RUN_ID, 'corpus_argument': str(corpus),
        'interpreter_model': INTERPRET_MODEL,
        'facet_layer': dict(node),
        'topic_on_the_edge_against_the_vectors_max_abs': topic_apart,
        'counts': {'chunks': len(chunk_ids), 'graph_tags': len(graph_tags),
                   'edges': len(endpoints), 'products': len(product_names),
                   'eligible_graph_tags': int(eligible.sum()),
                   'eligible_edges': int(layer['edges'].size),
                   'chunks_without_an_edge': edgeless,
                   'places': tree['places'],
                   'channels_apart': sum(len(p['apart']) for p in persons.values()),
                   'people': sum(len(p['people']) for p in persons.values())},
        'source_sha256': {str(p.relative_to(ROOT)): _sha(p.read_bytes()) for p in paths},
    }
    say(f'artefact_v4: {provenance["counts"]["channels_apart"]} channels apart over '
        f'{len(persons)} products')
    elapsed = time.perf_counter() - started
    say(f'artefact_v4: prepared {len(chunk_ids)} chunks, {len(graph_tags)} tags, '
        f'{len(endpoints)} edges in {elapsed:.1f}s')
    # each chunk row with its product and its channel as the graph ties them
    rows = tuple({**dict(r), 'product': str(found[r['chunkId']]['product']),
                  'channels': [str(ch) for ch in found[r['chunkId']]['channels']]}
                 for r in chunk_rows)
    return Prepared(chunk_rows=rows, chunk_ids=chunk_ids, graph_tags=graph_tags,
                    tag_vectors=tag_vectors, chunk_vectors=chunk_vectors, layer=layer, tree=tree,
                    cache_dir=cache, provenance=provenance,
                    build_stats=BuildStats(elapsed, ModelUsage(), [INTERPRET_MODEL]),
                    persons=persons)


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
    """The first call: the description and the tags. Returns the parsed content, the model
    usage and one record of the call."""
    offline = _offline()
    dropped = []

    def validate(raw):
        cleaned, n = _collapse_duplicate_tags(raw)
        dropped.append(n)
        return Q.parse(text, cleaned)

    content, usage, first = _ask('querytag', Q.request(text), validate, prepared.cache_dir,
                                 offline)
    first['duplicate_tags_dropped'] = dropped[-1] if dropped else None
    return content, usage, [first]


@dataclass(frozen=True)
class _QueryAxes:
    tag_vectors: np.ndarray
    chunk_vectors: np.ndarray


def _tag_cosines(description, tags, prepared):
    """The tags and the description embedded together in the query role, as the graph's tags
    and chunk descriptions are since 2026-10-08 (his "i guess we need query on both query and
    retrieval"): each tag's cosine to every graph tag and to the description, and the
    description's cosine to every chunk description. `_query_cosines` multiplies its unit
    vectors with the chunk matrix it is handed; handed the identity it returns the vectors
    themselves."""
    dim = prepared.chunk_vectors.shape[1]
    matrices, used, recipe = _query_cosines(
        description, tags, _QueryAxes(prepared.tag_vectors, np.eye(dim)), 'query')
    tag_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
    description_vector = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
    if tag_vectors.shape != (len(tags), dim) or description_vector.shape != (dim,):
        raise ValueError('Expected one query vector per tag and one for the description')
    return ({'tags': np.asarray(matrices['query_tag_cosines'], dtype=np.float64),
             'description': description_vector @ prepared.chunk_vectors.T,
             'tags_to_description': tag_vectors @ description_vector,
             'tags_to_chunks': tag_vectors @ prepared.chunk_vectors.T}, used, recipe)


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
    rows = list(got['tags'])
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
        embeddings['question_side_tags'] = {'tags': len(question_side),
                                            'embedding': recipe['vector_sha256']}
    layer = prepared.layer
    doc_cache = {}
    # The border, and the question with its names taken out for the chunk side.
    first, scope = scope_by_name(text, prepared.tree, len(prepared.chunk_ids))
    inside = np.flatnonzero(first) if first.any() else np.arange(len(prepared.chunk_ids))
    bare = _without_names(text, scope['names_in_the_question'])
    matrices, used, recipe = _query_cosines(bare, [], prepared)
    embed_usage = _add(embed_usage, used)
    d_bare = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
    embeddings['question_without_the_names'] = {'text_chars': len(bare),
                                                'embedding': recipe['vector_sha256']}
    parents = sorted({str(row['parent']) for row in prepared.chunk_rows})
    at = {name: i for i, name in enumerate(parents)}
    parent_of = np.array([at[str(row['parent'])] for row in prepared.chunk_rows],
                         dtype=np.int64)
    query_rows = np.array(rows, dtype=np.float64)
    # The query's facets weigh the tag relationship: one reading per facet for the whole
    # question, the middle one of its query tags'.
    found_near, _ = WK.tags_nearness(layer, query_rows)
    phrases = [t.text for t in (*query.tags, *query.query_tags)]
    readings = _query_facet_readings(query, phrases)
    weights = [_facet_weights(np.median(readings, axis=0), _facet_floors(layer))] * len(phrases)
    dealt, _, _ = WK.facet_influenced_nearness(layer, query_rows, np.array(weights))
    facets_said = {
        'readings': {phrase: [float(r) for r in row] for phrase, row in zip(phrases, readings)},
        'weights': {'the question': weights[0]},
        'chunks_whose_nearness_changed': int(sum(1 for i in inside if dealt[i] != found_near[i]))}
    combo = WK.cloud_combo(layer, query_rows, d_bare, inside, parent_of, _k_nearest(),
                           tags_near=dealt)
    order, gauged = combo['order'], combo['record']
    gauged['scopes_taken'] = [parents[s] for s in gauged['scopes_taken']]
    scope = {**scope, 'combo': gauged, 'chunks_kept': len(order),
             'chunks_cut': len(prepared.chunk_ids) - len(order), 'facets': facets_said}
    said = ('under ' + (', '.join(scope['names_in_the_question'])
                        or 'no name of the tree, nothing cut')
            + f'; {gauged["chunks_on_each_step"].get(2, 0)} chunks in both first clusters, '
              f'the scope {len(gauged["scopes_taken"])} parents')
    contexts, id_lists, context_ids, budget, delivered, handed = _hand_over(
        order, prepared, char_budget, k, doc_cache)
    boundary = budget['boundary']['id'] if budget and budget['boundary'] else None
    scope['delivered_under_the_products'] = int(first[delivered].sum())
    diagnostics, ranking = _combo_record(qid, combo, layer, prepared, query, order, delivered,
                                         scope, said, boundary, rows, tags, question_side,
                                         d_description, d_question, found_near)
    ranking.update(handed['per_chunk'])
    gone = handed['record']
    say(f'artefact_v4 {qid}: {gone["chunks_gone_through"]} chunks gone through, nothing '
        f'handed over of {sum(gone["chunks_with_nothing_handed_over"].values())}; '
        f'{sum(gone["records_left_out"].values())} records left out; '
        f'{gone["conversations_handed_over"]} conversations whole')
    retrieval = _add(interp_usage, embed_usage)
    for name, value in chat.take_timing().items():
        setattr(retrieval, name, value)
    meta = {'provenance': prepared.provenance,
            'interpreter': {'model': INTERPRET_MODEL, 'stages': stages,
                            'description_side_tags': len(tags),
                            'question_side_tags': len(question_side),
                            'embeddings': embeddings},
            'scope': scope, 'ranking': ranking, 'diagnostics': diagnostics,
            'chunk_ids': id_lists, 'returned': len(contexts), 'char_budget': budget,
            'handed_over': handed['record']}
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


def _combo_record(qid, combo, layer, prepared, query, order, delivered, scope, said, boundary,
                  rows, tags, question_side, d_description, d_question, found_near=None):
    """What a row keeps of the step as it stands (`v4_walk.cloud_combo`,
    `facet_influenced_nearness`): per delivered chunk its step, its level and nearness on each
    side, whether it is in scope, the query tag (as written) and graph tag its nearness through
    the tags comes from, and, where the query's facets dealt the tags side, its closeness as
    found beside the one dealt. The first call's description and the question as asked do not
    enter the order; their nearness is kept beside it."""
    steps = [int(combo['step'][i]) for i in delivered]
    edges = [int(combo['edge'][i]) for i in delivered]
    diagnostics = {
        'credited_delivered_rows': len(delivered),
        'boundary_chunk_id_not_credited': boundary,
        'chunks_with_an_eligible_edge': int((layer['n_c'] > 0).sum()),
        'product_named_tags_left_out': int((~layer['eligible']).sum()),
        'query_tags': len(rows),
        'phrases_standing_in_both_tag_lists': len({t.strip().casefold() for t in tags}
                                                  & {t.strip().casefold() for t in question_side}),
        'named_facets': [t.facet for t in (*query.tags, *query.query_tags)],
        'query_tag_closest_graph_tag': [float(np.asarray(row)[layer['eligible']].max())
                                        for row in rows],
        'delivered_on_each_step': {str(s): steps.count(s) for s in sorted(set(steps))},
        'delivered_in_scope': int(combo['in_scope'][delivered].sum()) if len(delivered) else 0,
    }
    say(f'artefact_v4 {qid}: {len(delivered)} delivered, '
        f'{scope["delivered_under_the_products"]} {said}; delivered on step '
        + ', '.join(f'{s}: {count}' for s, count in diagnostics['delivered_on_each_step'].items())
        + f'; {diagnostics["delivered_in_scope"]} in scope')
    ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
               'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
               'delivered_step': steps,
               'delivered_tags_level': [int(combo['level']['tags'][i]) for i in delivered],
               'delivered_description_level': [int(combo['level']['description'][i])
                                               for i in delivered],
               'delivered_in_scope': [bool(combo['in_scope'][i]) for i in delivered],
               'delivered_value': [float(combo['value'][i]) for i in delivered],
               'delivered_tags_nearness': [float(combo['tags_nearness'][i]) for i in delivered],
               'delivered_description_nearness': [float(combo['description_nearness'][i])
                                                  for i in delivered],
               'delivered_query_description_nearness': [float(d_description[i])
                                                        for i in delivered],
               'delivered_question_nearness': [float(d_question[i]) for i in delivered],
               'delivered_query_tags': [int(combo['query_tag'][i]) for i in delivered],
               'delivered_graph_tags': [prepared.graph_tags[int(layer['edge_tag'][e])]
                                        if e >= 0 else None for e in edges]}
    phrases = [t.text for t in (*query.tags, *query.query_tags)]
    ranking['delivered_query_tag_phrases'] = [phrases[int(combo['query_tag'][i])]
                                              if int(combo['query_tag'][i]) >= 0 else None
                                              for i in delivered]
    if found_near is not None:
        ranking['delivered_tags_nearness_as_found'] = [float(found_near[i]) for i in delivered]
        diagnostics['delivered_dealt_another_closeness'] = sum(
            1 for i in delivered if combo['tags_nearness'][i] != found_near[i])
    return diagnostics, ranking
