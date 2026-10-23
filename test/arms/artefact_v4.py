"""artefact_v4: the artefact. Inside the border the question's name sets, the chunk cloud and the
tags' cloud together order the chunks, and the product's own work is handed over.

Per question:
  1. One model call writes a description of the content the question is looking for and two
     tag lists, one from that content and one from the question's own words, each tag with the
     one facet that matters most for it and whether that facet matters for it at all
     (`query_content.request`). Its input goes as marked
     parts and its answer is forced into a JSON schema.
  2. The border (his 2026-10-19 "if it's "easy" to find when creating the graph from the dataset,
     then its reasonable to use, like the "filestructure" etc"; 2026-09-14 "a name and OR a
     product or whatever, should still be a "limited area". the combination i mean"): the
     products, channels, people, customers and companies whose name (a person's or a customer's id
     too) stands in the question word for word, asked of the graph per question (`name_border`).
     A name picks a scope, never a chunk: a product's or a channel's chunks, for a person, a
     customer or a company every chunk under the parents of the chunks it is tied to. Names of
     one kind add up, names of different
     kinds narrow each other from the widest down, and a name that would leave nothing is set
     aside (`border_of`). The chunks outside the border are out of the pool. No model call.
  3. The tags side: each chunk's closest tag to a query tag (`v4_walk.tags_nearness`). The
     query tags are embedded in the query role, as the graph's tags are.
  4. The facets, read relative to the tag (his 2026-10-19 "ok, but can we make them adaptive
     easily deterministically?", "well do that then", "ok, do that and run a smoke?";
     `v4_walk.closest_edge_standing`): a chunk's edge to its closest tag gets a standing in the
     facet the first call named for the query tag that gives that closeness, read only against
     the same graph tag's other edges on chunks of the same kind inside the border: above when it
     beats more of them than it loses to, below when it loses more, the same otherwise (one edge
     beats another when its value is higher by more than the facet's range on the FacetLayer
     node, the net's 24 refits). An edge whose graph tag is the query tag's own phrase never stands
     below. Where the first call said the facet does not matter, no standing. The standing acts in
     the tags' cloud (step 6). The tags side's places are by closeness alone
     (`v4_walk.closeness_places`: per query tag the border's chunks by closeness, each chunk at the
     best place any query tag gives it, the agent's choice).
  5. The chunk side: the chunk descriptions' closeness to the question with the border's names
     taken out (`_without_names`: inside the border the name tells nothing), embedded in the
     query role as the chunk descriptions are.
  6. The clouds (`v4_walk.cloud_combo`; his 2026-10-18 "ok, build the thing" for the clouds read
     off the data): each side's cloud is its near group over the border, the chunks before the
     knee of its closeness sorted from the nearest (`v4_walk.levels_of`), the knee looked for
     among the values above the median (the agent's choice), so a cloud holds at most half the
     border; a chunk's step is 2 in both clouds, 3 in one, 4 in neither; the parents holding the
     majority of the chunks in a cloud are the scope, whose chunks come first inside a step of the
     clouds' order; then the two sides' ranks counted equally (the tags side's place from step 4,
     the description side's closeness; the agent's choice, ranks against ranks). The tags' cloud
     keeps the size its knee gives and takes the chunks first by their level of closeness moved
     one nearer by a standing above and one farther by a standing below, then by closeness: the
     facets decide who is in it at its edge. The chunks in both clouds (with none, those of the
     lowest step) are the chosen chunks.
  7. The 4-combo (his 2026-10-17 "time, scope, entities, chunknearness?", "that IS the 4-combo",
     "well then, build it!"; `v4_walk.storyline`, the graph asked per question in
     `STORYLINE_CYPHER`): each other chunk of the clouds is tied to each chosen chunk by scope
     (the same parent), entities (a person tied to both), time (the smallest gap between a
     record of the one and a record of the other, each record at its own time, near when before
     the knee of the upper half of the pairs' gaps) and nearness (near
     each other in what the query asks about: their closeness to the query tags points the same
     way, near when before the knee of the upper half of the pairs' correlations); its strength
     is the ways it is tied, added over
     the chosen chunks. The order: the chosen chunks, then the rest of the clouds by strength,
     equals in the clouds' order, then everything outside the clouds as the clouds order it.
  8. What is handed over (`_hand_over`): in that order, every record of each chunk, and a Slack
     conversation whole where it first shows (a channel's messages between its long gaps, each
     message at its own time, read through the chunk's pointer). Nothing is left out (his
     2026-10-23 "yes, remove them", on leaving out a channel apart, other projects' pull requests
     and talk about another project's pull request).
     A chosen chunk that is a part of a split document or transcript goes in as its whole record,
     once, at its place (his 2026-10-22 "this continued document chunks is the "other half" of
     the slack", "chosen it is"); any other part goes in as only that part.
  9. The harness's cut at the character budget is applied to what is handed over; the texts then
     reach the model in pointer order (his 2026-10-22 "after the 72k cut, but before the model gets
     it"), and the row keeps them in the arm's order, which RAGAS reads as their rank.
Everything the order is made of is asked of the graph for each question (his 2026-10-07 "it MUST
be asked of the DB", `_ask_graph`): the border's chunks with their pointers, the eligible tags on
them with their edges' facet values, every closeness (the graph's own cosine of its stored
vectors and the query side's) and the 4-combo's ties. The start of a run only checks and counts the graph (`prepare_over_corpus`).
Each delivered chunk keeps, as pointers, the query tag and graph tag of the edge that gave its
closeness through the tags as the order used it, its nearness on each side, how it is tied to
the chosen chunks and the records behind it.

HERB_V4_OFFLINE=on reads the first call's answer from the cache and raises where it is missing.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import atexit
import re
import threading
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
from arms.artefact_facet_joint import _cached_stage, _query_cosines, _sha
from harness.record_text import FORM as RECORD_FORM, record_text
from arms.artefact_v2 import _load_verified_doc

ROOT = Path(__file__).resolve().parents[2]
DATABASE = 'herb-eval-volmax'
RUN_ID = 'pilot_full_herb'
# His 2026-10-06 "yes, sonnet on those". The model is part of the cache key.
INTERPRET_MODEL = 'claude-sonnet-5'
TOPIC_TOLERANCE = 1e-6
# The word a name gives way to on the chunk side, per kind of structure node
LABEL_WORDS = {'Product': 'product', 'Channel': 'channel', 'Employee': 'person',
               'Customer': 'customer', 'Company': 'company'}
STAGE_NAMES = {'querytag': 'querytagger'}
if GL.FACETS != WK.FACETS:
    raise RuntimeError('The graph layer and the arithmetic name different facets')

# The pool: a chunk with a description vector, a tag edge of the run and a product edge (the three
# metadata files' chunks carry no product edge and stay out).
POOL = ('c.desc_emb IS NOT NULL AND (c)-[:product]->() '
        'AND EXISTS { MATCH (c)-[r:HAS_TAG]->() WHERE r.run_id = $run }')

PRODUCT_CYPHER = 'MATCH (p:Product) RETURN p.name AS name ORDER BY name'

# Every pool edge with its five facet values: read once at start to check the facet layer whole
# (`graph_layer.read`); the retrieval does not use it.
EDGE_CYPHER = '''
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $run AND c.desc_emb IS NOT NULL AND t.emb IS NOT NULL AND (c)-[:product]->()
RETURN t.name AS tag, c.chunk_id AS chunkId, r.facets AS facets, r.w_facets AS values
'''

LAYER_CYPHER = 'MATCH (l:FacetLayer {run_id: $run}) RETURN properties(l) AS properties'

# What the run starts with, counted in the graph (no retrieval is worked out from it).
COUNTS_CYPHER = f'''
MATCH (c:Chunk) WHERE {POOL}
WITH count(c) AS chunks
MATCH (c:Chunk)-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $run AND c.desc_emb IS NOT NULL AND t.emb IS NOT NULL AND (c)-[:product]->()
WITH chunks, count(r) AS edges, count(DISTINCT t) AS graph_tags,
     sum(CASE WHEN NOT toLower(t.name) IN $products THEN 1 ELSE 0 END) AS eligible_edges,
     count(DISTINCT CASE WHEN NOT toLower(t.name) IN $products THEN t END) AS eligible_graph_tags,
     count(DISTINCT CASE WHEN toLower(t.name) IN $products THEN t END) AS product_named_tags,
     count(DISTINCT CASE WHEN NOT toLower(t.name) IN $products THEN c END) AS chunks_with_an_eligible_edge,
     max(abs(r.w_facets[0] - (2 * vector.similarity.cosine(c.desc_emb, t.emb) - 1))) AS topic_apart
RETURN chunks, edges, graph_tags, eligible_edges, eligible_graph_tags, product_named_tags,
       chunks_with_an_eligible_edge, topic_apart
'''
DIM_CYPHER = 'MATCH (t:Tag) WHERE t.emb IS NOT NULL RETURN size(t.emb) AS dim LIMIT 1'
POOL_IDS_CYPHER = f'MATCH (c:Chunk) WHERE {POOL} RETURN c.chunk_id AS chunk ORDER BY chunk'

# Per question, for the chunks of the border: each chunk's record pointer, product, channels and
# parent, and its description's closeness to each of the query side's texts; each eligible graph
# tag on those chunks with its closeness to each query tag and its edges' five values. The
# closeness is the graph's own cosine (vector.similarity.cosine gives (1 + cosine) / 2).
QUESTION_CHUNKS_CYPHER = '''
UNWIND $chunks AS cid
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk {chunk_id: cid})-[:product]->(p:Product)
OPTIONAL MATCH (c)-[:channel]->(ch:Channel)
WITH f, c, p, collect(ch.id) AS channels
RETURN c.chunk_id AS chunkId, c.kind AS kind, c.parent_ref AS parent, c.ordinal AS ordinal,
       c.locator_json AS locator, f.rel_path AS relpath, f.sha256 AS sha256, p.name AS product,
       channels, [v IN $vectors | 2 * vector.similarity.cosine(c.desc_emb, v) - 1] AS closeness
ORDER BY chunkId
'''
QUESTION_TAGS_CYPHER = '''
UNWIND $chunks AS cid
MATCH (c:Chunk {chunk_id: cid})-[r:HAS_TAG]->(t:Tag)
WHERE r.run_id = $run AND t.emb IS NOT NULL AND NOT toLower(t.name) IN $products
WITH t, collect({chunk: cid, values: r.w_facets}) AS edges
RETURN t.name AS tag, edges,
       [v IN $vectors | 2 * vector.similarity.cosine(t.emb, v) - 1] AS closeness
ORDER BY tag
'''
# The 4-combo's graph side, asked per question: per chosen chunk and other chunk of the border,
# whether they sit under the same parent, whether a person is tied to both, and the gap in time:
# the smallest gap in seconds between a record of the one and a record of the other, from each
# record's own time (`test/graph/build_chunk_times.py`; null when one has no time).
STORYLINE_CYPHER = '''
UNWIND $chosen AS sid
MATCH (s:Chunk {chunk_id: sid})
UNWIND $chunks AS cid
MATCH (c:Chunk {chunk_id: cid})
CALL (s, c) {
    UNWIND s.times AS a
    UNWIND c.times AS b
    RETURN min(abs(a - b)) AS gap
}
RETURN sid AS start, cid AS chunk,
       coalesce(s.parent_ref = c.parent_ref, false) AS same_parent,
       EXISTS { MATCH (s)<-[:chunk]-(:Employee)-[:chunk]->(c) } AS shares_person,
       gap
'''
TIME_CYPHER = '''
MATCH (c:Chunk) WHERE (c)-[:product]->()
RETURN count(c) AS chunks, count(c.times) AS with_a_time,
       count(c.time_first) + count(c.time_last) AS old_spans
'''
# The border's graph side, asked per question: the structure nodes one of whose match keys
# (`test/graph/build_structure_names.py`) stands in the question's plain form, and the scope each
# one picks, never a chunk of its own (his 2026-10-06 "a match on one of those does NOT pick/boost
# a chunk, it picks/boosts a scope"): a product's and a channel's chunks; for a person, a customer
# or a company, every chunk under the parents of the chunks it is tied to (`build_person_edges.py`,
# `build_customer_edges.py`; a company through its customers).
NAME_MATCH_CYPHER = '''
MATCH (n) WHERE (n:Product OR n:Channel OR n:Employee OR n:Customer OR n:Company)
  AND any(k IN n.name_keys WHERE $plain CONTAINS k)
RETURN elementId(n) AS node, labels(n)[0] AS label, n.name AS name,
       [k IN n.name_keys WHERE $plain CONTAINS k] AS keys
'''
NAME_AREA_CYPHER = '''
UNWIND $nodes AS id
MATCH (n) WHERE elementId(n) = id
CALL (n) {
    MATCH (c:Chunk)-[:product]->(n) RETURN c
  UNION
    MATCH (c:Chunk)-[:channel]->(n) RETURN c
  UNION
    MATCH (n)-[:chunk]->(t:Chunk) WITH DISTINCT t.parent_ref AS parent
    MATCH (c:Chunk {parent_ref: parent}) RETURN c
  UNION
    MATCH (n)<-[:company]-(:Customer)-[:chunk]->(t:Chunk) WITH DISTINCT t.parent_ref AS parent
    MATCH (c:Chunk {parent_ref: parent}) RETURN c
}
WITH id, c WHERE c.desc_emb IS NOT NULL AND (c)-[:product]->()
  AND EXISTS { MATCH (c)-[r:HAS_TAG]->() WHERE r.run_id = $run }
RETURN id AS node, collect(DISTINCT c.chunk_id) AS chunks
'''
NAMES_CYPHER = '''
MATCH (n) WHERE n.name_keys IS NOT NULL
RETURN labels(n)[0] AS label, count(n) AS nodes ORDER BY label
'''
CUSTOMER_EDGE_CYPHER = 'MATCH (:Customer)-[r:chunk]->(:Chunk) RETURN count(r) AS edges'

# The harness writes this into the run manifest.
RETRIEVAL_FLAGS = {
    'interpreter_model': INTERPRET_MODEL,
    'offline': 'HERB_V4_OFFLINE=on reads the first call\'s answer from the cache and raises where '
               'it is missing; off asks the model on a miss.',
    'retrieval': (
        'Everything the order is made of is asked of the graph for each question (`_ask_graph`): '
        "the border's chunks with their pointers, the eligible tags on them with their edges' "
        "facet values, every closeness as the graph's cosine of its stored vectors and the query "
        "side's, the people of the "
        "border's products and the 4-combo's ties; the start of a run only checks and counts the "
        'graph. '
        'The border (`name_border`, asked of the graph per question): the products, channels, '
        'people, customers and companies whose name, or a person\'s or customer\'s id, stands in '
        'the question word for word (the name_keys `test/graph/build_structure_names.py` wrote); a '
        'name picks a scope, never a chunk: a product\'s and a channel\'s chunks; for a person, a '
        'customer or a company, every chunk under the parents of the chunks it is tied to (a '
        'company through its customers); names of one kind add up, kinds narrow each other from the widest area down, '
        'and a kind that would leave nothing is set aside (`border_of`); no name, nothing cut; the '
        'chunks outside the border are out of the pool. Inside it (`v4_walk.cloud_combo`): '
        'each chunk\'s closest eligible tag to a query tag and the chunk descriptions\' closeness to '
        "the question with the border's names taken out, closeness alone; each side's cloud is the "
        'chunks before the knee of its closeness sorted '
        'from the nearest (`v4_walk.levels_of`), the knee looked for among the values above the '
        'median, so a cloud holds at most half the border; a '
        "chunk's step is 2 in both clouds, 3 in one, 4 in neither; the parents holding the majority "
        "of the chunks in a cloud are the scope, whose chunks come first inside a step of the clouds' "
        "order, then the two sides' ranks counted equally: the description side's by closeness, the "
        "tags side's place by closeness (`v4_walk.closeness_places`: per query tag the border's "
        "chunks by closeness, each chunk at the best place any query tag gives it). The facets "
        "(`v4_walk.closest_edge_standing`): a chunk's edge to its closest tag stands above, the "
        "same or below the same graph tag's other edges on chunks of the same kind, in the facet "
        "the first call named for the query tag, beyond the facet's range on the FacetLayer node; "
        "the query tag's own phrase never stands below; the tags' cloud keeps the size of its knee "
        "and takes the chunks by their level of closeness moved one by the standing, then by "
        'closeness. The chunks in both clouds (with none, those of the lowest step) are the chosen chunks. The 4-combo (`v4_walk.storyline`, the graph asked per question in '
        '`STORYLINE_CYPHER`): every other chunk of the clouds is tied to each chosen chunk by scope '
        '(the same parent), entities (a person tied to both, through the person-to-chunk edges), '
        'time (the smallest gap between a record of the one and a record of the other, from the '
        "chunks' times, each record's own, near when before the knee of the upper half of the "
        "pairs' gaps on the logarithm) and nearness "
        '(near each other in what the query asks about: the correlation of their closeness to each '
        "query tag, near when before the knee of the upper half of the pairs' correlations); a "
        "chunk's strength is the ways it is tied, "
        'added over the chosen chunks; the order is the chosen chunks, then the rest of the clouds by '
        "strength, equals in the clouds' order, then everything outside the clouds as the clouds "
        'order it. What is handed over, in that order (`_hand_over`): every record of each chunk; of '
        'a batch of Slack messages its conversations, each whole where it first shows (a '
        "conversation is a channel's messages between its long gaps, `v4_walk.conversations`, no "
        'length given, read through the chunk\'s pointer); of a part of a split document or '
        'transcript that is a chosen chunk its whole record, once, at its place, of any other part '
        'only that part; nothing is left out.'),
}
# What was left out of the data this arm rests on, and on whose word (harness.fields, FIELDS.md):
# his words quoted with their time, or that no rule of his is recorded.
LEFT_OUT = [
    "The graph: the 974 chunks of the benchmark's question, unanswerable-question and "
    "product-profile sections were dropped from the graph on 2026-05-19 (5,843 chunks made, 4,869 "
    "kept). No rule in his words is recorded; his messages of those days are not in the canon.",
    "The pool: the 61 chunks of the three metadata files (employee.json, salesforce_team.json, "
    "customers_data.json) are out of the pool (4,869 chunks in the graph, 4,808 in the pool). His "
    "words: \"eh.. vector and lucene sure as fuck shoulw never use the artefact or the graph DB, "
    "and there is a fucking reason thoes 3 files or off for the artefact\" (2026-09-13T01:00:57Z) "
    "· \"just dont use those chunks, ffs, and yeah, i did ask for their fucking removal a million "
    "times but whatever\" (2026-09-13T01:10:35Z).",
    "The tags: 4,111 tags and their 5,470 edges were removed from the graph copy herb-eval-v2 on "
    "2026-08-12 (output/graph_build/herb-eval-v2/step_cleanup.json, with its predicate). His "
    "words: \"ok, so, lets do this then, draft a new design based on these thoughts and "
    "herb-eval, including removing the pr-titles and url's\" (2026-08-12T19:14:05Z) · \"well "
    "then, if you feel this is the way, construct another db using this, aka use the current as "
    "template and \"fix it\" and add these things, right?\" (2026-08-12T19:52:05Z). Which tags fall "
    "in the removed classes is the agent's rule, written in the predicate.",
]
# The words for what only this arm writes into a run folder (harness.fields, FIELDS.md).
FIELDS = {
    'meta': sub("What the arm recorded about this question's retrieval.", {
        'provenance': sub('The graph the retrieval asked, checked and counted once when the run '
                          'started. Every question asks the graph for its own chunks, tags and '
                          'closeness; nothing here is what a question was ordered from.', {
            'database': 'The graph database that was read.',
            'run_id': 'The run of tag-to-chunk edges read from it.',
            'corpus_argument': 'The corpus the harness named when it started the arm. The arm '
                               'reads the graph, not that corpus.',
            'interpreter_model': 'The model of the first call.',
            'facet_layer': whole("The graph's FacetLayer node as it stood: what the facet values "
                                 'on the tag-to-chunk edges were made from: its name and run, '
                                 'the four facets with their retrain flip gaps (equal_gap) and '
                                 'the pooled one (pooled_flip_gap), on the scale of the facet '
                                 "values on the edges and read from the bootstrap's BANDS.md "
                                 '(the columns named), how many refits the values are the mean '
                                 'of, how many edges carry them, when it was written, and the '
                                 'sha256 of its source files.'),
            'topic_on_the_edge_against_the_vectors_max_abs':
                "The largest difference, over the edges, between the topic value on the edge "
                "and the cosine of the tag's vector and the chunk description's vector.",
            'counts': sub('What the graph held, counted in it.', {
                'chunks': 'Chunks in the pool.',
                'graph_tags': 'Tags that sit on a chunk of the pool.',
                'edges': 'Tag-to-chunk edges into the pool.',
                'products': 'Products.',
                'eligible_graph_tags': "Tags that are not a product's name; only those are "
                                       'compared with the query tags.',
                'eligible_edges': 'Edges that carry such a tag.',
                'product_named_tags': "Tags that are a product's name and are never compared.",
                'chunks_with_an_eligible_edge': 'Chunks of the pool that carry an eligible tag.',
                'named_structure_nodes': whole('Per kind of structure node (Product, Channel, '
                                               'Employee, Customer, Company), how many carry '
                                               'name_keys the question is matched against.'),
                'customer_chunk_edges': 'Edges from a customer to a chunk whose records carry '
                                        "the customer's id.",
                'chunks_with_a_time': "Chunks of the pool that carry their records' own times in "
                                      'the graph (times).',
            }),
            'source_sha256': whole('The sha256 of each code file the retrieval ran from, by '
                                   'path, its line ends as git holds them (LF), so that it is '
                                   "the sha256 of the commit's file whatever the checkout "
                                   'wrote.'),
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
                    "The question with the names that made the border taken out, each replaced "
                    "by \"the\" and the word for its kind (product, channel, person, customer, "
                    "company). The chunk side is compared with this.", {
                        'text_chars': 'Its length in characters.',
                        'embedding': 'The sha256 of its vector.',
                    }),
            }),
        }),
        'scope': sub('The border, and the scope inside it.', {
            'names_in_the_question': sub('One entry a structure name that stands in the '
                                         'question word for word.', {
                'name': 'The name as the graph holds it (for a match on an id, the name of '
                        'the node the id belongs to).',
                'key': 'The plain form that was matched: lower case, everything but letters '
                       'and digits one space.',
                'labels': 'The kinds of node that carry it.',
                'nodes': 'How many nodes carry it (one name several employees share is one '
                         'name).',
                'chunks': 'Pool chunks of the scope those nodes pick: a product\'s or a '
                          "channel's chunks; for a person, a customer or a company, every chunk "
                          'under the parents of the chunks it is tied to.',
                'set_aside': 'Whether it was left out of the border because its kind would '
                             'have left nothing.',
            }),
            'nothing_cut': 'Whether no name made a border, so every chunk stayed in the pool.',
            'chunks_under_the_names': 'Chunks inside the border.',
            'chunks_kept': 'Chunks the order was made of.',
            'chunks_cut': 'Chunks left out of the pool by the border.',
            'delivered_under_the_names': 'How many of the delivered chunks lie inside the '
                                         'border.',
            'combo': sub("The two clouds and the scope gauged from them. A side's cloud is the "
                         "chunks before the knee of its closeness sorted from the nearest, as "
                         "many as the closeness shows.", {
                'chunks': 'Chunks of the border.',
                'clouds': sub("Chunks in each side's cloud.", {
                    'tags': "Of the chunks' closeness through their tags, as many as its knee "
                            'gives, taken by level moved by the facets.',
                    'description': "Of the chunk descriptions' closeness to the question "
                                   "without the names.",
                }),
                'chunks_on_each_step': whole('How many chunks stand on each step: 2 in both '
                                             'clouds, 3 in one, 4 in neither.'),
                'scope_gauged_from_chunks': 'How many chunks the scope was gauged from: those '
                                            'in a cloud.',
                'scopes_taken': 'The parents that hold the majority of those chunks. A parent '
                                "is a channel, a product's whole documents, transcripts, pull "
                                'requests, links or chats, or the parts of one document or one '
                                'transcript.',
                'chunks_in_scope': 'Chunks of the border under those parents.',
                'tags_cloud_by_the_facets': sub("What the facets' standing did to the tags' cloud.", {
                    'nearer': 'Chunks moved one level of closeness nearer.',
                    'farther': 'Chunks moved one level farther.',
                    'changed': "Chunks in the tags' cloud that were not in it by closeness alone.",
                }),
            }),
            'facets': sub("The query's facets read relative to the tag: each chunk's edge to its "
                          "closest tag against the same graph tag's other edges on chunks of its "
                          "kind, in the facet the first call named for the query tag; the standing "
                          "moves the chunk one level of closeness at the tags' cloud's edge.", {
                'per_query_tag': sub('One entry a query tag, in the order of the two tag lists (a '
                                     'phrase written in both lists stands twice).', {
                    'phrase': 'The query tag as the first call wrote it.',
                    'facet': 'The one facet the first call named as mattering most for it.',
                    'matters': 'Whether the first call said that facet matters for it at all; '
                               'only then does the facet give a standing.',
                }),
                'query_tags_with_a_facet': 'How many query tags have a facet that matters.',
                'chunks_standing': sub("Chunks of the border by their closest edge's standing.", {
                    'above': 'Standing above the same tag\'s other edges of their kind.',
                    'below': 'Standing below them.',
                }),
                'own_phrase_edges_kept_from_below': "Chunks whose closest tag is the query tag's "
                                                    'own phrase and that would have stood below.',
                'tags_cloud_by_the_facets': sub("What the standing did to the tags' cloud.", {
                    'nearer': 'Chunks moved one level of closeness nearer.',
                    'farther': 'Chunks moved one level farther.',
                    'changed': "Chunks in the tags' cloud that were not in it by closeness alone.",
                }),
            }),
            'storyline': sub("The 4-combo: the chosen chunks (those in both clouds; with none, "
                             "those of the lowest step) and how the other chunks of the clouds are "
                             "tied to them, asked of the graph for this question. A pair is a "
                             "chosen chunk and another chunk of the clouds; it is tied by scope (the "
                             "same parent), entities (a person tied to both), time (the smallest "
                             "gap between a record of the one and a record of the other, before "
                             "the knee of the upper half of the pairs' gaps) and nearness (their "
                             "closeness to the query tags pointing the "
                             "same way, before the knee of the upper half of the pairs' "
                             "correlations).", {
                'chosen_chunk_ids': 'The chosen chunks, by chunk id.',
                'chunks_in_the_clouds': "Chunks in at least one side's cloud: the only chunks "
                                        'the 4-combo reorders.',
                'chosen_chunks': 'How many chunks were chosen.',
                'pairs': 'How many pairs were asked of the graph.',
                'pairs_tied': whole('Per way, how many pairs it ties.'),
                'pairs_by_ways': whole('How many pairs are tied in 0, 1, 2, 3 and 4 ways.'),
                'time_near_up_to_seconds': 'The largest gap in time, in seconds, that counts as '
                                           'near; empty when no pair counts as near in time.',
                'nearness_from_correlation': 'The lowest correlation that counts as near; empty '
                                             'when no pair counts as near.',
                'chunks_reached': 'How many chunks are tied to a chosen chunk in at least one way.',
            }),
        }),
        'ranking': sub('The order, and what lies behind each delivered chunk. The lists that '
                       "start with delivered_ have one entry a delivered chunk, in the arm's "
                       'order (the answer model read the texts in pointer order, '
                       'reading_order).', {
            'ordered_chunk_ids': "Every chunk of the border in the arm's order, by chunk id.",
            'delivered_chunk_ids': 'The chunks whose text, what was handed over of them, went '
                                   'in whole before the budget ended, by chunk id. A text can also '
                                   'hold records of other chunks, the rest of a conversation '
                                   '(delivered_records_of_other_chunks); those records are named '
                                   'in chunk_ids by record id. A chosen part of a split record is '
                                   'its whole record; any other part is only that part.',
            'delivered_step': "The chunk's step: its two levels added, 2 in both clouds, 3 in one, "
                              '4 in neither.',
            'delivered_tags_level': "1 when it is in the tags side's cloud, 2 when it is not.",
            'delivered_description_level': "1 when it is in the description side's cloud, 2 when "
                                           'it is not.',
            'delivered_in_scope': 'Whether it sits under a parent of the scope.',
            'delivered_middle_rank': "The middle of its two ranks over the border, the tags "
                                     "side's and the description side's: the order inside a step. "
                                     'Every rank here counts from 1, the best; equal values share '
                                     'the mean of their places, so a rank can be a fraction.',
            'delivered_tags_rank': "Its tags side's rank over the border, from its place (from 1).",
            'delivered_description_rank': "Its description side's rank over the border, by "
                                          'closeness (from 1).',
            'delivered_tags_place': "Its tags side's place: the best place a query tag gives it "
                                    '(from 1).',
            'delivered_closeness_rank': 'Under that query tag, its rank by closeness among the '
                                        "border's chunks (from 1; a chunk with no edge to the tag "
                                        'stands after every chunk that has one).',
            'delivered_standing': "Its closest edge's standing in the named facet against the "
                                  "same graph tag's other edges on chunks of its kind: 1 above, "
                                  '0 the same or no facet, -1 below; it moves the chunk one level '
                                  "of closeness at the tags' cloud's edge.",
            'delivered_named_facet': 'The facet the first call named for that query tag; empty '
                                     'where the first call said it does not matter.',
            'delivered_tags_nearness': 'The cosine of its closest tag to a query tag.',
            'delivered_description_nearness': "The cosine of its description to the question "
                                              'without the names.',
            'delivered_query_description_nearness': "The cosine of its description to the "
                                                    "first call's description. It does not "
                                                    'enter the order.',
            'delivered_question_nearness': 'The cosine of its description to the question as '
                                           'asked. It does not enter the order.',
            'delivered_query_tags': 'The query tag that gave its place, counted from 0 over the '
                                    'two tag lists; -1 for a chunk with no eligible tag.',
            'delivered_graph_tags': "The graph tag of its closest edge to that query tag, by name; "
                                    'empty for such a chunk.',
            'delivered_query_tag_phrases': 'That query tag as the first call wrote it; empty '
                                           'for such a chunk.',
            'delivered_chosen': 'Whether it is one of the chosen chunks.',
            'delivered_storyline_strength': 'How strongly it is tied to the chosen chunks: the '
                                            'ways it is tied, added over the chosen chunks. The '
                                            'order is the chosen chunks first, then this, the '
                                            'higher the earlier.',
            'delivered_storyline_ways': sub('Per way, how many chosen chunks it is tied to that '
                                            'way.', {
                'scope': 'Under the same parent.',
                'entities': 'A person tied to both.',
                'time': 'Near in time.',
                'nearness': 'Near each other in what the query asks about.',
            }),
            'delivered_records': 'How many records were handed over with the chunk.',
            'delivered_records_of_other_chunks': 'How many of those lie in another chunk: the '
                                                 'rest of a conversation this chunk holds a '
                                                 'part of.',
            'delivered_records_not_handed_over': "How many of the chunk's own records were not "
                                                 'handed over with it: they went in before, with '
                                                 'another chunk.',
        }),
        'handed_over': sub("What of the ordered chunks was handed over. The counts are over the "
                           "chunks gone through until the budget was full.", {
            'chunks_gone_through': 'How many chunks of the order were gone through.',
            'chunks_with_nothing_handed_over': sub('Of those, the chunks nothing was handed '
                                                   'over of.', {
                'conversations_handed_over_before': 'A batch of messages whose conversations '
                                                    'all went in before, with another chunk.',
                'record_handed_over_before': 'A part of a split document or transcript whose '
                                             'whole record went in before.',
            }),
            'conversations_handed_over': 'Conversations handed over whole, in the texts that '
                                         'went in whole (not the one cut at the budget).',
            'conversations_reaching_into_another_chunk': 'Of those, the conversations with '
                                                         'messages in another chunk than the '
                                                         'one they first showed in.',
        }),
        'diagnostics': sub('Counts that say how the order came about.', {
            'credited_delivered_rows': 'How many texts went in whole before the budget ended.',
            'boundary_chunk_id_not_credited': 'The chunk id of the text that was cut where the '
                                              'budget ended; empty when none was.',
            'query_tags': 'Query tags in the two lists together.',
            'phrases_standing_in_both_tag_lists': 'Phrases the first call wrote in both lists.',
            'query_tag_closest_graph_tag': "Per query tag, the cosine of its closest eligible "
                                           "graph tag on the border's chunks.",
            'delivered_on_each_step': whole('How many of the delivered chunks stand on each '
                                            'step.'),
            'delivered_in_scope': 'How many of the delivered chunks are in scope.',
        }),
        'chunk_ids': 'The record ids behind each text handed over, one list a text, in the order '
                     "of contexts: the arm's order.",
        'reading_order': 'The order the answer model read the texts in, pointer order, as '
                         'positions in contexts (0 the first).',
        'returned': 'How many texts were handed over, the one cut at the budget counted.',
        'char_budget': BUDGET_FIELDS,
    }),
    'index': sub("What the arm's index is: the graph it reads, and what building that graph "
                 'cost, as the build records give it.', {
        'graph': 'The Neo4j database the arm reads.',
        'facet_layer_run': 'The run id of the facet values on the tag-to-chunk edges.',
        'counts': whole('What the start of the run counted in the graph (as in provenance).'),
        'build_cost': whole('Per build step of the graph: what it made, when, with which model '
                            'or device, its calls, tokens in and out and seconds where the '
                            "step's own record gives them, the records it is read from, and "
                            'what those records do not give. Collected from the records into '
                            '`test/graph/build_cost.json`; nothing in it is estimated except the '
                            "chunks' token estimate, which the chunker itself wrote. Every number "
                            'in it was recounted from its record on 2026-10-20 '
                            '(`test/graph/build_cost_check.json`).'),
        'build_cost_file_sha256': 'The sha256 of that file, its line ends as git holds them (LF), '
                                  'which identifies the build cost given.',
        'first_call': 'When and how the first call is made.',
        'question_embedding': 'When and how the query tags, the description and the question are '
                              'embedded.',
        'unit_text': 'The form a record is written in for the answer model, and where that form '
                     'is from; what a part of a split record brings; the order the texts reach the '
                     'model in.',
    }),
    'retrieval_flags': whole("The arm's switches in the arm's own words, by name: what each one "
                             'does, not what it was set to. What was set on the command line is '
                             'in flags; the entries that end in _at_prepare say what the run '
                             'started with.'),
}


def _offline():
    value = os.environ.get('HERB_V4_OFFLINE', 'off')
    if value not in ('off', 'on'):
        raise ValueError(f'HERB_V4_OFFLINE must be off or on, got {value!r}')
    return value == 'on'


_GRAPH = []
_GRAPH_LOCK = threading.Lock()


def _graph():
    """One driver for the questions of a run, opened at the first question and closed when the
    process ends."""
    with _GRAPH_LOCK:
        if not _GRAPH:
            from graph.db import _driver
            _GRAPH.append(_driver())
            atexit.register(_GRAPH[0].close)
        return _GRAPH[0]


def _storyline_pairs(chosen_ids, chunk_ids):
    """The 4-combo's graph side for one question (`STORYLINE_CYPHER`), one row a pair."""
    if not chosen_ids or not chunk_ids:
        return []
    with _graph().session(database=DATABASE, default_access_mode='READ') as session:
        return session.execute_read(lambda tx: [dict(r) for r in tx.run(
            STORYLINE_CYPHER, chosen=list(chosen_ids), chunks=list(chunk_ids))])


def cache_root():
    return Path(os.environ.get('HERB_V4_CACHE',
                               str(ROOT / 'output/private/artefact_v4_cache')))


def _add(a, b):
    return ModelUsage(**{name: getattr(a, name) + getattr(b, name)
                         for name in ModelUsage.__dataclass_fields__})


@dataclass(frozen=True)
class Prepared:
    """What a run starts with: the checks and counts of the graph, never a retrieval's data."""
    cache_dir: Path
    provenance: dict
    build_stats: BuildStats
    dim: int = 0
    products: tuple = ()


@dataclass(frozen=True)
class Asked:
    """What the graph gave for one question (`_ask_graph`): the border's chunks with their pointer,
    product and channels, the eligible graph tags on them with their edges as a layer
    (`v4_walk.build_layer`), the query tags' closeness to those tags, the
    chunk descriptions' closeness to the question without the names, the question and the
    description."""
    chunk_rows: tuple
    chunk_ids: tuple
    graph_tags: tuple
    layer: dict
    tag_cosines: np.ndarray
    description_closeness: np.ndarray


def _plain(text):
    """The text in lower case, everything but letters and digits as one space, a space at each end."""
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', str(text).lower()).strip() + ' '


def _name_matches(question, prepared):
    """The structure names standing in the question, asked of the graph (`NAME_MATCH_CYPHER`,
    `NAME_AREA_CYPHER`): one entry per matched node and key, (key, label, name, the ids of the pool
    chunks of the scope the node picks, sorted)."""
    plain = _plain(question)
    with _graph().session(database=DATABASE, default_access_mode='READ') as session:
        nodes = session.execute_read(lambda tx: [dict(r) for r in tx.run(NAME_MATCH_CYPHER,
                                                                         plain=plain)])
        spans = session.execute_read(lambda tx: {r['node']: r['chunks'] for r in tx.run(
            NAME_AREA_CYPHER, nodes=[n['node'] for n in nodes], run=RUN_ID)}) if nodes else {}
    return [(key, n['label'], n['name'], sorted(spans.get(n['node'], ())))
            for n in nodes for key in n['keys']]


def border_of(matched):
    """The border the names standing in a question set (his 2026-09-14 "a name and OR a product
    or whatever, should still be a "limited area". the combination i mean").

    A name is one key: its area is the scope every node that carries it picks, so an employee's
    name several employees share is one name. Names of one kind of structure add up (two products
    are both asked about). Kinds narrow each other: from the widest kind's area down, each next
    kind is met with what stands, and a kind that would leave nothing is set aside. The adding up,
    the order from the widest and the setting aside are the agent's. With no name, or none that
    spans a chunk, the border is empty and nothing is cut.

    matched: (key, label, name, chunk ids) per matched node and key (`_name_matches`).
    Returns the border's chunk ids, sorted (empty when nothing is cut), the record, and the
    (key, word) of every name that made the border (`_without_names`)."""
    names = {}
    for key, label, name, chunks in matched:
        entry = names.setdefault(key, {'name': name, 'labels': set(), 'nodes': 0, 'area': set()})
        entry['labels'].add(label)
        entry['nodes'] += 1
        entry['area'].update(chunks)
    kinds = {}
    for key, entry in names.items():
        kind = kinds.setdefault(tuple(sorted(entry['labels'])), {'keys': [], 'area': set()})
        kind['keys'].append(key)
        kind['area'] |= entry['area']
    border, made, aside = None, [], []
    for labels, kind in sorted(kinds.items(), key=lambda item: (-len(item[1]['area']), item[0])):
        met = set(kind['area']) if border is None else border & kind['area']
        if met:
            border, made = met, made + kind['keys']
        else:
            aside.extend(kind['keys'])
    inside = sorted(border) if border else []
    record = {'names_in_the_question': [
                  {'name': names[key]['name'], 'key': key, 'labels': sorted(names[key]['labels']),
                   'nodes': names[key]['nodes'], 'chunks': len(names[key]['area']),
                   'set_aside': key in aside} for key in sorted(names)],
              'nothing_cut': not border, 'chunks_under_the_names': len(inside)}
    order = [label for label in LABEL_WORDS]
    swaps = [(key, LABEL_WORDS[min(names[key]['labels'], key=order.index)]) for key in made]
    return inside, record, swaps


def name_border(question, prepared):
    """The border for one question (`border_of` on `_name_matches`)."""
    return border_of(_name_matches(question, prepared))


def _without_names(question, swaps):
    """The question with each name that made the border taken out: wherever its key stands word
    for word (letters and digits compared, case left aside, as the border found it), "the" and
    the word for its kind stand in its place, so the sentence stays whole. swaps: (key, word)."""
    out = question
    for key, word in swaps:
        parts = key.split()
        if not parts:
            continue
        found = re.compile(r'(?<![A-Za-z0-9])' + r'[^A-Za-z0-9]*'.join(map(re.escape, parts))
                           + r'(?![A-Za-z0-9])', re.IGNORECASE)
        out = found.sub('the ' + word, out)
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


def _conversations(inside, asked, doc_cache):
    """The conversations the Slack messages behind the border's chunks form, read through each
    chunk's pointer: a channel's messages between its long gaps (`v4_walk.conversations`), each
    message at its own time (a message's channel is its record's; the graph ties a chunk to that
    channel, and to two where two channels bear one name).

    talk      per message id its conversation
    messages  per conversation its messages, in the order written
    """
    rows = asked.chunk_rows
    talk, messages, channels = {}, {}, {}
    for i in inside:
        row = rows[i]
        if row['kind'] != 'slack_thread_batch':
            continue
        for record in _pointed_records(row, doc_cache):
            channel = str(record['Channel']['channelID'])
            if channel not in row['channels']:
                raise ValueError(f'A message of the Slack chunk {row["chunkId"]} lies in a '
                                 'channel the graph does not tie the chunk to')
            channels.setdefault((row['product'], channel), {})[str(record['id'])] = record
    for (product, channel), held in channels.items():
        line = sorted(held.values(),
                      key=lambda r: (_seconds(r['Message']['User']['timestamp']), str(r['id'])))
        numbers = WK.conversations([_seconds(r['Message']['User']['timestamp']) for r in line])
        for record, number in zip(line, numbers.tolist()):
            key = (product, channel, number)
            talk[str(record['id'])] = key
            messages.setdefault(key, []).append(record)
    return {'talk': talk, 'messages': messages}


BUILD_COST = ROOT / 'test/graph/build_cost.json'


def _as_in_git(raw):
    """A text file's bytes with the line ends git holds (LF): a checkout on Windows can write
    CR LF, and the sha256 is then still that of the commit's file."""
    return raw.replace(b'\r\n', b'\n')

# the keys of build_cost.json that hold elapsed seconds or a command's span; 'seconds' holds a
# step's named spans; seconds_summed_per_call is the other kind and is never added to these
_ELAPSED_KEYS = ('seconds_elapsed', 'seconds_elapsed_recorded', 'backup_seconds',
                 'report_seconds_on_the_laptop')


def _elapsed_seconds(node, out):
    """Every elapsed second and command span in a build step, in the order the file gives them;
    a key about seconds this does not know stops it, so none is dropped unseen."""
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        if key == 'seconds':
            out.extend(float(v) for v in (value or {}).values())
        elif key in _ELAPSED_KEYS:
            out.append(float(value))
        elif key == 'seconds_summed_per_call':
            continue
        elif 'second' in key:
            raise ValueError(f'build_cost.json: {key} is no kind of seconds the arm knows')
        else:
            _elapsed_seconds(value, out)


def build_stats_from_cost(cost):
    """What building the graph cost, from `test/graph/build_cost.json`: one entry per model, in
    the order of the file's steps, with its calls, tokens and the two kinds of seconds as the
    records give them; build_time_s the elapsed seconds and command spans of every step that
    records them, added (the superseded work is not counted); what no record gives."""
    steps = {s['id']: s for s in cost['steps']}
    tagged = steps['descriptions_and_tags']
    main, again = tagged['whole_run']['main'], tagged['whole_run']['recovery']
    vectors = steps['embeddings']
    embedded = [vectors['parts'][p] for p in ('tags', 'tags_with_underscores_in_readable_form',
                                              'descriptions')]
    facets = steps['facet_layer']['parts']
    judged, bake, cache = facets['opus_judgements'], facets['encoder_bake_off'], facets['encoder_cache']
    facet_gaps = steps['facet_layer']['not_recorded'].split('; ')
    if (not tagged['where'].startswith('claude-haiku-4-5') or not judged['model'].startswith(
            'claude-opus-5,') or len(facet_gaps) != 3
            or not vectors['where'].startswith('nvidia/llama-nemotron-embed-1b-v2')):
        raise ValueError('build_cost.json is not the file this reading was written for')
    models = [
        {'kind': 'chat', 'model': 'claude-haiku-4-5-20251001',
         'what': 'the tagging run pilot_full_herb: per chunk a description and its tags, five '
                 'facet scores per tag (later replaced by the facet layer), per file a '
                 'description and a score per chunk; the main run and its recovery',
         'calls': main['records'] + again['calls'],
         'tokens_in': main['tokens_in'] + again['tokens_in'],
         'tokens_out': main['tokens_out'] + again['tokens_out'],
         'seconds_summed_per_call': main['seconds_summed_per_call'] + again['seconds_summed_per_call'],
         'seconds_elapsed': main['seconds_elapsed'],
         'device': 'anthropic, forced tool use, temperature 0.3, 4 at a time',
         'not_recorded': f"{tagged['not_recorded']}; the recovery's elapsed time; token counts "
                         f"for {main['records'] - main['calls_with_usage']} records of the main run"},
        {'kind': 'embed', 'model': 'nvidia/llama-nemotron-embed-1b-v2',
         'what': vectors['what'] + ', one text a request',
         'calls': sum(p['texts'] for p in embedded),
         'tokens_in': sum(p['tokens_in'] for p in embedded), 'tokens_out': 0,
         'seconds_summed_per_call': None,
         'seconds_elapsed': sum(p['seconds_elapsed'] for p in embedded),
         'device': '; '.join(dict.fromkeys(p['device'] for p in embedded)),
         'not_recorded': vectors['not_recorded']},
        {'kind': 'chat', 'model': 'claude-opus-5',
         'what': f"pairs of tag-to-chunk edges judged for the facet layer ({judged['fitted_on']})",
         'calls': judged['calls'], 'tokens_in': judged['tokens_in'],
         'tokens_out': judged['tokens_out'],
         'seconds_summed_per_call': judged['seconds_summed_per_call'],
         'seconds_elapsed': judged['seconds_elapsed_recorded'],
         'device': judged['model'].split(', ', 1)[1],
         'not_recorded': '; '.join(facet_gaps[:2])},
        {'kind': 'encoder', 'model': f"{bake['encoders']} candidate encoders",
         'what': f"the encoder bake-off on {bake['edges']} edges, which chose the encoder; not in "
                 'the values',
         'calls': None, 'tokens_in': None, 'tokens_out': 0,
         'seconds_summed_per_call': None, 'seconds_elapsed': bake['seconds_elapsed'],
         'device': bake['device'],
         'not_recorded': 'the tokens; the candidates are named in the bake-off\'s own results'},
        {'kind': 'encoder', 'model': cache['model'].split(', ', 1)[0],
         'what': f"the encoder cache: every one of the {cache['edges']} tag-to-chunk edges "
                 f"encoded for the facet head ({cache['model'].split(', ', 1)[1]})",
         'calls': None, 'tokens_in': None, 'tokens_out': 0,
         'seconds_summed_per_call': None, 'seconds_elapsed': cache['seconds_elapsed'],
         'device': cache['device'], 'not_recorded': facet_gaps[2]},
    ]
    elapsed = []
    for step in cost['steps']:
        _elapsed_seconds(step, elapsed)
    return BuildStats(
        build_time_s=sum(elapsed), models=models,
        not_recorded=[f"{s['id']}: {s['not_recorded']}" for s in cost['steps']]
        + ['the superseded work (index.build_cost.superseded) is recorded there and not counted '
           'here'])


def index_info(prepared):
    """What the arm's index is, for the run manifest: the graph it reads and what building the
    graph cost, from `test/graph/build_cost.json` (collected from the build records)."""
    raw = BUILD_COST.read_bytes() if BUILD_COST.is_file() else None
    return {'graph': prepared.provenance['database'], 'facet_layer_run': RUN_ID,
            'counts': prepared.provenance['counts'],
            'build_cost': json.loads(raw.decode('utf-8')) if raw else None,
            'build_cost_file_sha256': _sha(_as_in_git(raw)) if raw else None,
            'first_call': f'at query time, {INTERPRET_MODEL} through the lane; an answer already '
                          'in the store (HERB_V4_CACHE) is read from it and counted as no call',
            'question_embedding': 'at query time, local embedder, query mode; a text embedded '
                                  'before is read from output/query_embed_cache and counted as '
                                  'no call',
            'unit_text': f'each record as lucene and vector write it ({RECORD_FORM}), the records '
                         'of a chunk one after the other with a blank line between them; a chosen '
                         'chunk that is a part of a split document or transcript goes in as its '
                         'whole record, once, at its place, any other part as its record with only '
                         "that part of its long field (a document's feedback with its last part); "
                         "after the cut the texts reach the answer model in pointer order: file, "
                         "section in the file's own order, place of the text's first record in its "
                         "section, part; contexts keeps "
                         "the arm's order, "
                         "which RAGAS reads as their rank, and reading_order gives the model's"}


def _same_words(a, b):
    """Whether two phrases are the same words (case and spacing aside)."""
    return ' '.join(str(a).lower().split()) == ' '.join(str(b).lower().split())


def _pointed(row, cache):
    """A chunk's records through its pointer and their section; for a part of a split record,
    also the pointer, which names the part (`char_range`, `field`, `part`)."""
    loc = json.loads(row['locator'])
    held = _load_verified_doc(row['relpath'], row['sha256'], cache)[loc['section']]
    if 'char_range' in loc:
        return loc['section'], [held[loc['index']]], loc
    return (loc['section'], [held[i] for i in (loc['indices'] if 'indices' in loc else [loc['index']])],
            None)


def _record_texts(section, records):
    """The records as lucene and vector write them (`harness.record_text`), one after the other
    with a blank line between them, and where in that text each record ends."""
    texts = [record_text(section, record) for record in records]
    ends, at = [], 0
    for n, text in enumerate(texts):
        at += (2 if n else 0) + len(text)
        ends.append(at)
    return '\n\n'.join(texts), ends


def _part_text(section, record, loc):
    """A part of a split document or transcript: its record as lucene and vector write it, with
    only this part of its long field; a document's feedback, which follows its content, stands
    with the last part (`last`)."""
    start, end = loc['char_range']
    shown = dict(record)
    shown[loc['field']] = record[loc['field']][start:end]
    if not loc['last']:
        shown.pop('feedback', None)
    return record_text(section, shown)


def _pointer(rows, unit, doc_cache):
    """Where a text stands in HERB's files: its file, its section in the file's own order, the
    place of its first record in that section, and its part (0 for a whole record)."""
    row = rows[unit['chunk']]
    doc = _load_verified_doc(row['relpath'], row['sha256'], doc_cache)
    key = ('places', row['relpath'], unit['section'])
    if key not in doc_cache:
        doc_cache[key] = {str(record['id']): n for n, record in enumerate(doc[unit['section']])}
    return (row['relpath'], list(doc).index(unit['section']),
            min(doc_cache[key][record] for record in unit['ids']),
            unit['part'][1] if 'part' in unit else 0)


def _hand_over(order, asked, char_budget, k, doc_cache, chosen=frozenset()):
    """What is handed over of the ordered chunks, and the record of it (the step as it stands).

    In the order: of a batch of Slack messages its conversations, each whole where it first
    shows (`_conversations`; its messages in other chunks come with it and are not handed over
    again); of a part of a split document or transcript that is one of the chosen chunks its
    whole record, once, at its place (the record's other parts come with it; his 2026-10-22
    "autoinclude chunks that are part of the same split object from the strongest chunks",
    "chosen it is"), of any other part only that part, not credited; any other chunk with all
    its records. Nothing is left out (his 2026-10-23 "yes, remove them"). Every record is
    written as lucene and vector write theirs (`_record_texts`).
    The harness's cut is applied to these texts (`cut_at_budget`); with no budget the first k are
    handed over. The model reads the texts in pointer order (`_pointer`; his 2026-10-22 "after
    the 72k cut, but before the model gets it"); they are returned in the arm's order, which RAGAS
    reads as their rank, with the pointer order beside them as positions (his 2026-10-22 "did we
    not agree to create that?").

    A record is credited as handed over when its whole text went in, the rule lucene and vector
    keep: every record of a text handed over whole (a part alone never), and the records of the
    cut text that end before the cut.

    chosen: the chosen chunks' indices (`answer_one_question`). Returns the texts in the arm's
    order, the record ids behind each text, the record ids handed over whole, the cut's block, the
    chunks handed over whole, and what a row keeps of it with the order the model reads the texts
    in (`reading_order`)."""
    rows = asked.chunk_rows
    book = _conversations(order, asked, doc_cache)
    units, seen, given = [], set(), set()
    nothing = Counter()
    gone = [0]

    def stream():
        for i in order:
            row, kind = rows[i], rows[i]['kind']
            gone[0] += 1
            if kind == 'slack_thread_batch':
                held = [str(record['id']) for record in _pointed_records(row, doc_cache)]
                here = list(dict.fromkeys(book['talk'][m] for m in held))
                new = [t for t in here if t not in seen]
                if not new:
                    nothing['conversations_handed_over_before'] += 1
                    continue
                seen.update(new)
                section, records = 'slack', [record for t in new for record in book['messages'][t]]
                ids = [str(record['id']) for record in records]
                unit = {'chunk': i, 'ids': ids, 'of_other_chunks': len(set(ids) - set(held)),
                        'not_handed_over': len(set(held) - set(ids)), 'conversations': len(new),
                        'reaching': sum(1 for t in new if any(
                            str(record['id']) not in held for record in book['messages'][t]))}
            else:
                # a part of a split record points at the whole record (`_pointed`)
                section, records, part = _pointed(row, doc_cache)
                unit = {'chunk': i, 'ids': list(dict.fromkeys(str(r['id']) for r in records)),
                        'of_other_chunks': 0, 'not_handed_over': 0}
                if part is not None:
                    if unit['ids'][0] in given:
                        nothing['record_handed_over_before'] += 1
                        continue
                    if i not in chosen:
                        # a part ends its record when its range reaches the end of the long field
                        last = part['char_range'][1] >= len(records[0][part['field']])
                        unit.update(section=section, part=(unit['ids'][0], part['part']), ends=[])
                        units.append(unit)
                        yield row['chunkId'], _part_text(section, records[0], {**part, 'last': last})
                        continue
                    given.add(unit['ids'][0])
            text, ends = _record_texts(section, records)
            unit.update(section=section,
                        ends=list(zip((str(record['id']) for record in records), ends)))
            units.append(unit)
            yield row['chunkId'], text

    if char_budget is not None:
        cut = cut_at_budget(stream(), char_budget)
        texts, kept = cut.contexts, cut.kept
        budget = {'budget': char_budget, 'chars': cut.chars, 'kept': cut.kept,
                  'boundary': cut.boundary, 'exhausted': cut.exhausted}
    else:
        texts = [text for _, (_, text) in zip(range(k), stream())]
        kept, budget = len(texts), None
    if len(units) != len(texts):
        raise RuntimeError(f'artefact_v4: {len(texts)} texts handed over for {len(units)} units')
    whole = units[:kept]
    credited = [record for unit in whole if 'part' not in unit for record in unit['ids']]
    if budget is not None and budget['boundary']:
        credited += [record for record, end in units[kept]['ends']
                     if end <= budget['boundary']['chars_kept']]
    context_ids = list(dict.fromkeys(credited))
    placed = sorted(range(len(texts)), key=lambda n: (_pointer(rows, units[n], doc_cache), n))
    delivered = [unit['chunk'] for unit in whole]
    record = {
        'chunks_gone_through': gone[0],
        'chunks_with_nothing_handed_over': {name: nothing[name] for name in (
            'conversations_handed_over_before', 'record_handed_over_before')},
        # counted over the texts that went in whole, not the one cut at the budget
        'conversations_handed_over': sum(unit.get('conversations', 0) for unit in whole),
        'conversations_reaching_into_another_chunk': sum(unit.get('reaching', 0)
                                                         for unit in whole),
    }
    per_chunk = {'delivered_records': [len(unit['ids']) for unit in whole],
                 'delivered_records_of_other_chunks': [unit['of_other_chunks'] for unit in whole],
                 'delivered_records_not_handed_over': [unit['not_handed_over'] for unit in whole]}
    return (texts, [unit['ids'] for unit in units], context_ids, budget, delivered,
            {'record': record, 'per_chunk': per_chunk, 'reading_order': placed})


def prepare_over_corpus(corpus) -> Prepared:
    """Once per run: checks and counts of the graph, never a retrieval's data (his 2026-10-07 "it
    MUST be asked of the DB"; every question asks the graph for its own, `_ask_graph`). The edges'
    facet values are read whole once to check they are the ones the FacetLayer node was written
    with (`graph_layer.read`); the topic value on each edge is checked against the cosine of its
    two vectors in the graph; and the structure names, the customer edges and the chunks' times
    must be in the graph. A
    graph tag that is a product's name is structure, not a tag to match: the products' names
    are kept to leave those tags out."""
    started = time.perf_counter()
    RETRIEVAL_FLAGS['offline_at_prepare'] = _offline()
    from graph.db import _driver
    say(f'artefact_v4: checking {DATABASE}')
    cache = cache_root()
    driver = _driver()
    try:
        with driver.session(database=DATABASE, default_access_mode='READ') as session:
            product_names = session.execute_read(
                lambda tx: [r['name'] for r in tx.run(PRODUCT_CYPHER)])
            folded = sorted({name.lower() for name in product_names})
            say('artefact_v4: reading the tag-to-chunk edges to check the facet layer they carry')
            edge_rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(EDGE_CYPHER,
                                                                                run=RUN_ID)])
            layer_rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(LAYER_CYPHER,
                                                                                 run=RUN_ID)])
            say('artefact_v4: counting the pool in the graph')
            counts = session.execute_read(lambda tx: tx.run(
                COUNTS_CYPHER, run=RUN_ID, products=folded).single().data())
            dim = session.execute_read(lambda tx: tx.run(DIM_CYPHER).single()['dim'])
            timed = session.execute_read(lambda tx: tx.run(TIME_CYPHER).single().data())
            named = session.execute_read(lambda tx: {r['label']: r['nodes']
                                                     for r in tx.run(NAMES_CYPHER)})
            customer_edges = session.execute_read(
                lambda tx: tx.run(CUSTOMER_EDGE_CYPHER).single()['edges'])
    finally:
        driver.close()
    node = GL.read(edge_rows, layer_rows).node
    if list(node.get('equal_gap_facets') or []) != list(WK.RANKING_FACETS) \
            or len(node.get('equal_gap') or []) != len(WK.RANKING_FACETS):
        raise ValueError('The FacetLayer node carries no range for each ranking facet')
    if counts['topic_apart'] > TOPIC_TOLERANCE:
        raise ValueError('The topic value on an edge differs from the cosine of its vectors '
                         f'by {counts["topic_apart"]:.2g}: the layer was written from other vectors')
    if not timed['with_a_time'] or timed['old_spans']:
        raise ValueError("The chunks do not carry their records' own times: run "
                         'test/graph/build_chunk_times.py write')
    if not named:
        raise ValueError('No structure node carries name_keys: run '
                         'test/graph/build_structure_names.py write')
    if not customer_edges:
        raise ValueError('No customer is tied to a chunk: run test/graph/build_customer_edges.py write')
    say(f'artefact_v4: names to match the question against: {named}; {customer_edges} customer '
        'edges to chunks')
    paths = [Path(__file__), ROOT / 'test/artefact/v4_walk.py',
             ROOT / 'test/artefact/query_content.py',
             ROOT / 'test/artefact/graph_layer.py', ROOT / 'test/arms/artefact_facet_joint.py',
             ROOT / 'test/arms/artefact_v2.py', ROOT / 'prod/harness/chat.py',
             ROOT / 'prod/harness/embed.py', ROOT / 'prod/harness/char_budget.py']
    provenance = {
        'database': DATABASE, 'run_id': RUN_ID, 'corpus_argument': str(corpus),
        'interpreter_model': INTERPRET_MODEL,
        'facet_layer': dict(node),
        'topic_on_the_edge_against_the_vectors_max_abs': float(counts['topic_apart']),
        'counts': {'chunks': int(counts['chunks']), 'graph_tags': int(counts['graph_tags']),
                   'edges': int(counts['edges']), 'products': len(product_names),
                   'eligible_graph_tags': int(counts['eligible_graph_tags']),
                   'eligible_edges': int(counts['eligible_edges']),
                   'product_named_tags': int(counts['product_named_tags']),
                   'chunks_with_an_eligible_edge': int(counts['chunks_with_an_eligible_edge']),
                   'named_structure_nodes': named,
                   'customer_chunk_edges': int(customer_edges),
                   'chunks_with_a_time': int(timed['with_a_time'])},
        'source_sha256': {str(p.relative_to(ROOT)): _sha(_as_in_git(p.read_bytes()))
                          for p in paths},
    }
    elapsed = time.perf_counter() - started
    say(f'artefact_v4: prepared: {counts["chunks"]} chunks, {counts["graph_tags"]} tags and '
        f'{counts["edges"]} edges in the graph, checked in {elapsed:.1f}s')
    # what building the graph cost; these checks' own seconds are the start's prepare_s
    built = (build_stats_from_cost(json.loads(BUILD_COST.read_text(encoding='utf-8')))
             if BUILD_COST.is_file() else
             BuildStats(None, models=[], not_recorded=['test/graph/build_cost.json is not there']))
    return Prepared(cache_dir=cache, provenance=provenance, build_stats=built,
                    dim=int(dim), products=tuple(folded))


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


def _query_vectors(description, tags, prepared):
    """The tags and the description embedded in the query role, as the graph's tags and chunk
    descriptions are since 2026-10-08 (his "i guess we need query on both query and retrieval"),
    each text on its own. `_query_cosines` multiplies its unit vectors with the matrices it is
    handed; handed the identity it returns the vectors themselves. Returns the tag vectors, the
    description's vector, the usage and the recipe."""
    eye = np.eye(prepared.dim)
    matrices, used, recipe = _query_cosines(description, tags, _QueryAxes(eye, eye), 'query')
    tag_vectors = np.asarray(matrices['query_tag_cosines'], dtype=np.float64)
    description_vector = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
    if tags and tag_vectors.shape != (len(tags), prepared.dim) or description_vector.shape != (prepared.dim,):
        raise ValueError('Expected one query vector per tag and one for the description')
    return tag_vectors, description_vector, used, recipe


def _floats(vectors):
    return [[float(x) for x in v] for v in vectors]


def _ask_graph(chunk_ids, tag_vectors, text_vectors, prepared):
    """One question's chunks and their tag edges, asked of the graph (his 2026-10-07 "it MUST be
    asked of the DB"; `QUESTION_CHUNKS_CYPHER`, `QUESTION_TAGS_CYPHER`): the border's chunks with
    their record pointer, product and channels, and their descriptions' closeness to each text
    vector; the eligible graph tags on them with each tag's closeness to each query tag vector and
    its edges' five values, in the order of chunk id and tag. Returns an `Asked`."""
    chunk_ids = list(chunk_ids)
    with _graph().session(database=DATABASE, default_access_mode='READ') as session:
        chunk_rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(
            QUESTION_CHUNKS_CYPHER, chunks=chunk_ids, vectors=_floats(text_vectors))])
        tag_rows = session.execute_read(lambda tx: [dict(r) for r in tx.run(
            QUESTION_TAGS_CYPHER, chunks=chunk_ids, run=RUN_ID, products=list(prepared.products),
            vectors=_floats(tag_vectors))])
    ids = tuple(str(r['chunkId']) for r in chunk_rows)
    if sorted(ids) != sorted(set(chunk_ids)):
        raise ValueError('The graph gave other chunks than the border holds')
    at ={c: i for i, c in enumerate(ids)}
    graph_tags = tuple(str(r['tag']) for r in tag_rows)
    edges = sorted((str(e['chunk']), t, e['values'])
                   for t, row in enumerate(tag_rows) for e in row['edges'])
    if not edges:
        raise ValueError('No chunk of the border carries an eligible tag')
    edge_values = np.asarray([v for _, _, v in edges], dtype=np.float64)
    layer = WK.build_layer(ids, [str(r['kind'] or '') for r in chunk_rows],
                           np.ones(len(graph_tags), dtype=bool),
                           np.array([t for _, t, _ in edges], dtype=np.int64),
                           np.array([at[c] for c, _, _ in edges], dtype=np.int64),
                           edge_values[:, 0], edge_values[:, 1:])
    rows = tuple({'chunkId': str(r['chunkId']), 'kind': r['kind'], 'parent': r['parent'],
                  'ordinal': r['ordinal'], 'locator': r['locator'],
                  'relpath': r['relpath'],
                  'sha256': r['sha256'], 'product': str(r['product']),
                  'channels': [str(ch) for ch in r['channels']]} for r in chunk_rows)
    return Asked(chunk_rows=rows, chunk_ids=ids, graph_tags=graph_tags, layer=layer,
                 tag_cosines=np.asarray([r['closeness'] for r in tag_rows], dtype=np.float64).T,
                 description_closeness=np.asarray([r['closeness'] for r in chunk_rows],
                                                  dtype=np.float64))


def _pool_ids():
    """Every chunk of the pool, asked of the graph: the border when no name stands in a question."""
    with _graph().session(database=DATABASE, default_access_mode='READ') as session:
        return session.execute_read(lambda tx: [r['chunk'] for r in tx.run(POOL_IDS_CYPHER,
                                                                         run=RUN_ID)])


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
    # the query role, then the question-side tags.
    tags = [t.text for t in query.tags]
    question_side = [t.text for t in query.query_tags]
    embeddings = {}
    tag_vectors, description_vector, embed_usage, recipe = _query_vectors(
        query.description, tags, prepared)
    embeddings['description_side_tags'] = {'tags': len(tags),
                                           'text_chars': len(query.description),
                                           'embedding': recipe['vector_sha256']}
    _, question_vector, used, recipe = _query_vectors(query.question, [], prepared)
    embed_usage = _add(embed_usage, used)
    embeddings['question'] = {'text_chars': len(query.question),
                              'embedding': recipe['vector_sha256']}
    if question_side:
        side_vectors, _, used, recipe = _query_vectors(query.description, question_side, prepared)
        embed_usage = _add(embed_usage, used)
        tag_vectors = np.vstack([tag_vectors, side_vectors])
        embeddings['question_side_tags'] = {'tags': len(question_side),
                                            'embedding': recipe['vector_sha256']}
    doc_cache = {}
    # The border the structure names in the question set, asked of the graph, and the question
    # with those names taken out for the chunk side.
    border, scope, swaps = name_border(text, prepared)
    bare = _without_names(text, swaps)
    _, bare_vector, used, recipe = _query_vectors(bare, [], prepared)
    embed_usage = _add(embed_usage, used)
    embeddings['question_without_the_names'] = {'text_chars': len(bare),
                                                'embedding': recipe['vector_sha256']}
    # Everything the order is made of, asked of the graph for the border's chunks
    asked = _ask_graph(border or _pool_ids(), tag_vectors,
                       [bare_vector, question_vector, description_vector], prepared)
    layer, query_rows = asked.layer, asked.tag_cosines
    d_bare, d_question, d_description = asked.description_closeness.T
    inside = np.arange(len(asked.chunk_ids))
    parents = sorted({str(row['parent']) for row in asked.chunk_rows})
    at = {name: i for i, name in enumerate(parents)}
    parent_of = np.array([at[str(row['parent'])] for row in asked.chunk_rows], dtype=np.int64)
    # The tags side's places by closeness; the query's facets read relative to the tag: each
    # chunk's closest edge against the same tag's other edges, in the facet the first call named
    # for its query tag, where it said the facet matters; the standing acts at the tags' cloud's
    # edge.
    written = (*query.tags, *query.query_tags)
    facet_of = np.array([t.facet_index if t.matters else -1 for t in written], dtype=np.int64)
    placed = WK.closeness_places(layer, query_rows, inside)
    _, t_edge = WK.tags_nearness(layer, query_rows)
    closest_q = np.where(t_edge >= 0, query_rows[:, layer['edge_tag']].argmax(axis=0)[
        np.maximum(t_edge, 0)], -1)
    own = np.array([bool(t_edge[c] >= 0 and closest_q[c] >= 0 and _same_words(
        asked.graph_tags[int(layer['edge_tag'][t_edge[c]])], written[int(closest_q[c])].text))
        for c in range(layer['chunks'])], dtype=bool)
    gaps = prepared.provenance['facet_layer']['equal_gap']
    standing = WK.closest_edge_standing(layer, inside, t_edge, closest_q, facet_of, gaps, own)
    unfloored = WK.closest_edge_standing(layer, inside, t_edge, closest_q, facet_of, gaps,
                                         np.zeros(layer['chunks'], dtype=bool))
    combo = WK.cloud_combo(layer, query_rows, d_bare, inside, parent_of, tags_place=placed['place'],
                           standing=standing)
    facets_said = {
        'per_query_tag': [{'phrase': t.text, 'facet': t.facet, 'matters': t.matters}
                          for t in written],
        'query_tags_with_a_facet': int((facet_of >= 0).sum()),
        'chunks_standing': {'above': int((standing[inside] > 0).sum()),
                            'below': int((standing[inside] < 0).sum())},
        'own_phrase_edges_kept_from_below': int((standing[inside] != unfloored[inside]).sum()),
        'tags_cloud_by_the_facets': combo['record']['tags_cloud_by_the_facets']}
    # the pointers a row keeps name the query tag that gave the place and its closest edge
    combo = {**combo, 'edge': placed['edge'], 'query_tag': placed['query_tag'], 'placed': placed,
             'facet_of': facet_of, 'standing': standing}
    gauged = combo['record']
    gauged['scopes_taken'] = [parents[s] for s in gauged['scopes_taken']]
    # The 4-combo: the chunks of both clouds (with none, of the lowest step) are the chosen chunks;
    # the rest of the clouds is ordered by how strongly it is tied to them, asked of the graph per
    # question; nothing below the clouds is lifted.
    steps = combo['step'][inside]
    chosen = inside[steps == steps.min()]
    in_a_cloud = (combo['level']['tags'] == 1) | (combo['level']['description'] == 1)
    region = [int(i) for i in inside if in_a_cloud[i]]
    others = [i for i in combo['order'] if in_a_cloud[i] and i not in set(chosen.tolist())]
    pairs = _storyline_pairs([asked.chunk_ids[i] for i in chosen],
                             [asked.chunk_ids[i] for i in others])
    at_chunk = {c: i for i, c in enumerate(asked.chunk_ids)}
    profiles = WK.query_tag_profiles(layer, query_rows[:, layer['edge_tag']])
    story = WK.storyline(
        len(asked.chunk_ids), chosen, [at_chunk[p['start']] for p in pairs],
        [at_chunk[p['chunk']] for p in pairs], [bool(p['same_parent']) for p in pairs],
        [bool(p['shares_person']) for p in pairs],
        [np.nan if p['gap'] is None else float(p['gap']) for p in pairs], profiles)
    order = WK.storyline_order(combo['order'], chosen, story['strength'], region)
    scope = {**scope, 'combo': gauged, 'chunks_kept': len(order),
             'chunks_cut': prepared.provenance['counts']['chunks'] - len(order),
             'facets': facets_said,
             'storyline': {'chosen_chunk_ids': [asked.chunk_ids[i] for i in chosen],
                           'chunks_in_the_clouds': len(region), **story['record']}}
    said = ('under ' + (', '.join(n['name'] for n in scope['names_in_the_question']
                                  if not n['set_aside']) or 'no name of the graph, nothing cut')
            + f'; {len(chosen)} chosen chunks, {story["record"]["chunks_reached"]} tied to them')
    contexts, id_lists, context_ids, budget, delivered, handed = _hand_over(
        order, asked, char_budget, k, doc_cache, chosen=frozenset(int(i) for i in chosen))
    boundary = budget['boundary']['id'] if budget and budget['boundary'] else None
    scope['delivered_under_the_names'] = len(delivered) if border else 0
    diagnostics, ranking = _combo_record(qid, combo, asked, query, order, delivered, scope, said,
                                         boundary, query_rows, tags, question_side,
                                         d_description, d_question)
    chosen_set = set(chosen.tolist())
    ranking['delivered_chosen'] = [i in chosen_set for i in delivered]
    ranking['delivered_storyline_strength'] = [int(story['strength'][i]) for i in delivered]
    ranking['delivered_storyline_ways'] = {name: [int(count[i]) for i in delivered]
                                           for name, count in story['ways'].items()}
    ranking.update(handed['per_chunk'])
    gone = handed['record']
    say(f'artefact_v4 {qid}: {gone["chunks_gone_through"]} chunks gone through, nothing '
        f'handed over of {sum(gone["chunks_with_nothing_handed_over"].values())}; '
        f'{gone["conversations_handed_over"]} conversations whole')
    # the arm's own count, which the harness checks against the call records; the row holds
    # those per model
    retrieval = _add(interp_usage, embed_usage)
    timing = chat.take_timing()
    for name, value in timing.items():
        setattr(retrieval, name, value)
    meta = {'provenance': prepared.provenance,
            'interpreter': {'model': INTERPRET_MODEL, 'stages': stages,
                            'description_side_tags': len(tags),
                            'question_side_tags': len(question_side),
                            'embeddings': embeddings},
            'scope': scope, 'ranking': ranking, 'diagnostics': diagnostics,
            'chunk_ids': id_lists, 'reading_order': handed['reading_order'],
            'returned': len(contexts), 'char_budget': budget,
            'handed_over': handed['record']}
    # without any model call or embedder request: the first call as the arm timed it, the tries
    # of a first call that was refused and asked again (retry_s), and every embedder request
    search_time = max(0., time.perf_counter() - started - interp_usage.time_s
                      - timing['retry_s'] - embed_usage.time_s)
    if generate is None:
        answer, gen_usage = '', ModelUsage()
    else:
        # the model reads the texts in pointer order; contexts keeps the arm's order, which RAGAS
        # reads as their rank
        read = [contexts[n] for n in handed['reading_order']]
        gen_started = time.perf_counter()
        answer, gen_usage = unpack_generation(generate(text, read),
                                              time.perf_counter() - gen_started)
    return ArmOutput(answer=answer, contexts=contexts, context_ids=context_ids,
                     search_time_s=search_time, generator=gen_usage, retrieval=retrieval,
                     meta=meta)


def _combo_record(qid, combo, asked, query, order, delivered, scope, said, boundary, rows, tags,
                  question_side, d_description, d_question):
    """What a row keeps of the step as it stands (`v4_walk.cloud_combo`, `closeness_places`,
    `closest_edge_standing`): per delivered chunk its step, its level and nearness on each side,
    whether it is in scope, its ranks, the query tag (as written) that gave its tags side's place
    with its rank by closeness under it and the facet named for it, its closest edge's standing,
    and the graph tag of its closest edge to that query tag. The first call's description and the question as asked do not enter the
    order; their nearness is kept beside it."""
    layer = asked.layer
    steps = [int(combo['step'][i]) for i in delivered]
    edges = [int(combo['edge'][i]) for i in delivered]
    diagnostics = {
        'credited_delivered_rows': len(delivered),
        'boundary_chunk_id_not_credited': boundary,
        'query_tags': len(rows),
        'phrases_standing_in_both_tag_lists': len({t.strip().casefold() for t in tags}
                                                  & {t.strip().casefold() for t in question_side}),
        'query_tag_closest_graph_tag': [float(np.asarray(row).max()) if np.size(row) else None
                                        for row in rows],
        'delivered_on_each_step': {str(s): steps.count(s) for s in sorted(set(steps))},
        'delivered_in_scope': int(combo['in_scope'][delivered].sum()) if len(delivered) else 0,
    }
    say(f'artefact_v4 {qid}: {len(delivered)} delivered, '
        f'{scope["delivered_under_the_names"]} {said}; delivered on step '
        + ', '.join(f'{s}: {count}' for s, count in diagnostics['delivered_on_each_step'].items())
        + f'; {diagnostics["delivered_in_scope"]} in scope')
    ranking = {'ordered_chunk_ids': [asked.chunk_ids[i] for i in order],
               'delivered_chunk_ids': [asked.chunk_ids[i] for i in delivered],
               'delivered_step': steps,
               'delivered_tags_level': [int(combo['level']['tags'][i]) for i in delivered],
               'delivered_description_level': [int(combo['level']['description'][i])
                                               for i in delivered],
               'delivered_in_scope': [bool(combo['in_scope'][i]) for i in delivered],
               'delivered_middle_rank': [float(combo['middle_rank'][i]) for i in delivered],
               'delivered_tags_rank': [float(combo['rank']['tags'][i]) for i in delivered],
               'delivered_description_rank': [float(combo['rank']['description'][i])
                                              for i in delivered],
               'delivered_tags_place': [float(combo['placed']['place'][i]) for i in delivered],
               'delivered_closeness_rank': [float(combo['placed']['closeness_rank'][i])
                                            for i in delivered],
               'delivered_standing': [int(combo['standing'][i]) for i in delivered],
               'delivered_tags_nearness': [float(combo['tags_nearness'][i]) for i in delivered],
               'delivered_description_nearness': [float(combo['description_nearness'][i])
                                                  for i in delivered],
               'delivered_query_description_nearness': [float(d_description[i])
                                                        for i in delivered],
               'delivered_question_nearness': [float(d_question[i]) for i in delivered],
               'delivered_query_tags': [int(combo['query_tag'][i]) for i in delivered],
               'delivered_graph_tags': [asked.graph_tags[int(layer['edge_tag'][e])]
                                        if e >= 0 else None for e in edges]}
    phrases = [t.text for t in (*query.tags, *query.query_tags)]
    ranking['delivered_query_tag_phrases'] = [phrases[int(combo['query_tag'][i])]
                                              if int(combo['query_tag'][i]) >= 0 else None
                                              for i in delivered]
    written = (*query.tags, *query.query_tags)
    ranking['delivered_named_facet'] = [
        written[int(combo['query_tag'][i])].facet
        if int(combo['query_tag'][i]) >= 0 and combo['facet_of'][int(combo['query_tag'][i])] >= 0
        else None for i in delivered]
    return diagnostics, ranking
