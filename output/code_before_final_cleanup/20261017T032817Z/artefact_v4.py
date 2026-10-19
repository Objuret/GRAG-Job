"""artefact_v4: inside the border the question's name sets, the chunk cloud and the tags' cloud
together order the chunks.

Per question:
  1. One model call writes a description of the content the question is looking for and two
     tag lists, one from that content and one from the question's own words, each tag with
     the one facet that matters most for it (`query_content.request`). Its input goes as
     marked parts and its answer is forced into a JSON schema.
  2. The border (his 2026-10-11 "if we take our latest best run, and do that part for scope
     instead"): every branch of the tree whose name stands in the question word for word
     (`scope_by_name`); the chunks outside it are out of the pool. No model call.
  3. The tags, the description and the question are embedded in the query role, as the graph's
     tags and chunk descriptions are; so is the question with the border's names taken out
     (`_without_names`: inside the border the name tells nothing).
  4. The order (his 2026-10-12 "the combo should fucking work", `v4_walk.cloud_combo`): the
     chunk descriptions' closeness to the question without the names and each chunk's closest
     tag to a query tag are each cut into HERB_V4_K clusters over the border; a chunk's step is
     its two levels added; the parents holding the majority of the first two steps' chunks are
     the scope, whose chunks come first inside a step. No strength, no second call. The query's
     facets influence the tag relationship (2026-10-15/16, `v4_walk.facet_influenced_nearness`):
     the facet net reads the query tags against the question and the description; a reading's
     level among its facet's levels over the graph's edges is that facet's weight, for the whole
     question (HERB_V4_FACETS=question) or per query tag (tag); an edge's weight is the tag's
     closeness plus, per facet, that weight times where the edge stands in the facet's ranking.
     The order follows; nothing forces it. Each delivered chunk keeps the query tag and graph tag
     that found it, and its nearness before and after the influence, as pointers.
  5. What is handed over (2026-10-13, under his "/goal solve this"; the agent's find, `_hand_over`):
     in that order, each chunk without the records that are not the product's own work, and a
     conversation whole where it first shows. Whose work a record is comes from the graph's
     people (his 2026-10-11 "things related to persons ... nothing at all is actually using the
     graph", `product_persons`): a channel none of whose employees is tied to another channel
     or to a meeting of the product is apart; a pull request is the product's own when its
     author is one of the product's people. The author, a message's links and its time are
     fields of the records, read through the chunk's pointer; the graph does not hold them.
The harness's cut at the character budget is applied to what is handed over.

HERB_V4_OFFLINE=on reads the model answers from the cache and raises where one is missing.

HERB_V4_SCOPE_STEP names an older step kept in the file (`RETRIEVAL_FLAGS`). `combo` is the
2026-10-12 step before this one (the same order, every chunk handed over as it is). `name` is the
2026-10-11 step before that (the same border, the order `v4_walk.chain`'s). `map` is the
2026-10-11 build (the border from the chunk descriptions' closeness to the question, then one
more model call that reads the border's map and names chunks). `both` is the
2026-10-10 build (`v4_walk.both_sides`); the others order by `v4_walk.chain`'s strength. `tags`
has no second call, the scope read off the picked tags, the
structure last as a filter. `cluster` reads
it off the main cluster of the chain's relevance instead. `call` asks a second call for the
places (`query_content.scope_request`) and puts the chunks under their products
first. `off` asks no second call and leaves the chain's order as it is. `clouds` asks no second call, keeps the chunks under the scopes that hold the
largest clouds (`v4_walk.scope_clouds`, the tags' number and the description's number each in
the shape HERB_V4_CLOUD_SHAPE names: as_is, spread, unit or order) and cuts the others.
HERB_V4_CLOUD_LEVELS, HERB_V4_CLOUD_PLACES and HERB_V4_CLOUD_GROUPS narrow what is gauged and
fix the clustering to two groups (`RETRIEVAL_FLAGS`). `hits` asks no second call either: the
chunks each stage named in HERB_V4_HIT_STAGES alone would deliver are gauged over every place
of the tree (`v4_walk.scan_clouds`), the places where they gather are kept and the others cut.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
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
from artefact import landing as LAND
from artefact import graph_layer as GL
from artefact import v4_walk as WK
from arms.artefact_facet_joint import _cached_stage, _query_cosines, _sha, _unit
from arms.artefact_v2 import _budget_contexts, _load_verified_doc, _resolve_chunk
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
STAGE_NAMES = {'querytag': 'querytagger', 'scope': 'scope', 'map': 'map reader'}
# The chunk description texts are on no database, only their vectors. The map call reads them
# from the file the description vectors of 2026-10-07 were made from (its MANIFEST names it).
DESCRIPTIONS = ROOT / 'output/embed_local/20261007_rev113abe4acafa_float32/descriptions.jsonl'
DESCRIPTIONS_SHA256 = 'e3b840dd475f33bf4206e01891e6574c374319c0030ea9128cff30049eb967b2'
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
    'cos_noise': COS_NOISE,
    'k_nearest': 'HERB_V4_K, 5 unless named. With the step as it stands (persons), with combo, '
                 'map and both: the number of clusters a list of nearness values is cut into '
                 '(`v4_walk.levels`). With the older steps: the pick is each query tag\'s k '
                 'nearest graph tags, and the dogleg main clusters are switched off in '
                 '`v4_walk.chain`.',
    'offline': 'HERB_V4_OFFLINE=on reads both query-side answers from the cache and raises '
               'where one is missing; off asks the model on a miss.',
    'facets': "HERB_V4_FACETS, read with the step as it stands: question (the default) weighs the "
              "facets by one reading per facet for the whole question (the middle one of its "
              "query tags'); tag by each query tag's own reading; off uses no facets. The facet "
              "net reads the query tags on the laptop; it is no model call.",
    'scope_step': 'HERB_V4_SCOPE_STEP: call puts the chunks under the products of the second '
                  'call\'s places first; off has no scope step and no second call; clouds keeps '
                  'the chunks under the scopes whose totals are the top group of the clustering '
                  'and cuts the others, no second call.',
    'cloud_shape': 'HERB_V4_CLOUD_SHAPE, read with scope_step clouds: the shape of each '
                   'place\'s numbers before they are added up per scope (as_is, spread, unit, '
                   'order).',
    'cloud_levels': 'HERB_V4_CLOUD_LEVELS: the levels of the tree gauged, of product, kind, '
                    'channel; all three unless named.',
    'cloud_places': 'HERB_V4_CLOUD_PLACES: the places gauged (`v4_walk.place_numbers`: tags, '
                    'description, chunk_desc, question, hits, topic, tags_to_desc); tags and '
                    'description unless named. HERB_V4_CLOUD_SHAPE may name one shape per place.',
    'cloud_groups': 'HERB_V4_CLOUD_GROUPS: picked lets the clustering pick the number of '
                    'groups (the largest mean silhouette); two splits the totals in two.',
    'hit_stages': 'HERB_V4_HIT_STAGES, read with scope_step hits: the stages whose hit chunks '
                  'are gauged over the tree (`_stage_hits`: arm, tags, chunk_desc, question, '
                  'topic, picked); a stage\'s hits are the chunks it alone would deliver inside '
                  'the character budget. The places where the hits gather beyond every random '
                  'scatter are kept (`v4_walk.scan_clouds`), the others cut, no second call.',
    'scan_scatters': 999, 'scan_seed': 20261008,
    'level_places': 'HERB_V4_LEVEL_PLACES, read with scope_step levels: the places whose '
                    'levels are gauged (tags, chunk_desc, question; tags and chunk_desc unless '
                    'named). The clustering decides what is hit: each list of nearness values '
                    'is split into levels at its knees (`v4_walk.levels_of`), a level is a 0-1 '
                    'relevancy, a scope\'s cloud is its chunks\' relevancy added up, the '
                    'largest clouds are kept with the minorities that share their parent '
                    '(`v4_walk.level_clouds`), the others cut, no second call. '
                    'HERB_V4_LEVEL_DEPTH: how many nearest levels count as hit; all unless '
                    'named.',
}
RETRIEVAL_FLAGS['map'] = (
    'HERB_V4_SCOPE_STEP=map (his 2026-10-11 "/goal reason and research until you find an actual '
    'viable solution ... implement that"; his "dont use more ai in the artefact" the same day '
    'took it out of use). The border: the chunk '
    'descriptions\' closeness to the question cut into HERB_V4_K clusters, the branch most of '
    'the first cluster sits in, the rest out of the pool (`v4_walk.border_by_nearness`). Then '
    'one more model call, the map call: the model reads the border\'s map (its parts in order, '
    'each chunk a label, its description and its tags) and names the chunks an answer would be '
    'read from (`query_content.map_request`); labels, no number. The named chunks come first in '
    'the model\'s order; the border\'s other chunks follow, one from each route in turn (the '
    'chunk\'s closest tag to a query tag, the description, the question). No second (scope) '
    'call, no strength, no facet. The description texts are read from a side file, not from '
    'the graph.')
RETRIEVAL_FLAGS['both'] = (
    'HERB_V4_SCOPE_STEP=both (his 2026-10-10 "now i want to do the both, '
    'side by side, together, either cleanly, or overlapping clouds for each step"; overlapping '
    'clouds for each step is built): no second call and no strength (`v4_walk.both_sides`). A '
    'chunk\'s nearness through its tags is the closeness of its closest eligible tag to a query '
    'tag; by its description, the description\'s closeness to the query description. Each list '
    'is cut into HERB_V4_K clusters and the first is the cloud. Scope step: the scopes both '
    'scope clouds hold (the same nearness per scope, the mean of its chunks) that hold a chunk '
    'both nearness clouds hold; their branches are the border, the rest is out of the pool; '
    'with no such scope nothing is cut. Inside step: both sides cut again over the border; the '
    'chunks both clouds hold first, then the chunks one holds, then the rest; inside each the '
    'cluster of the chunk\'s nearness through its tags, then where the query tag\'s named '
    'facet stands among the four facets of that edge, then that nearness.')
RETRIEVAL_FLAGS['tags'] = (
    'HERB_V4_SCOPE_STEP=tags (his 2026-10-08 "first tags, then '
    'clustering on them, THEN check the scope on all tags ... take the scopes of the greatest '
    'cluster(s)? and then after that, we do the facets sorting"): no second call. Per query tag '
    'its picked edges in the main cluster of its first facet; per scope the tags of those edges, '
    'each once with its closeness, added up; the main '
    'cluster of the scopes\' values (the dogleg deciding) is kept, the other scopes are out of '
    'the pool (`v4_walk.scope_by_tags`); the facets sort inside, as the chain does.')
RETRIEVAL_FLAGS['cluster'] = (
    'HERB_V4_SCOPE_STEP=cluster, the step as it stands (his 2026-10-07 "use the structure '
    'last, as a vertical cut" / "as a filter", "we can just cluster by scope", "keep minorities '
    'if same parents", "i dont think we use the second call if we do this"): no second call. '
    "What is hit: the main cluster of the chain's relevance, every chunk's strength in one "
    'list, the dogleg deciding (`v4_walk.cluster_hits`; HERB_V4_CLUSTER_PLACES: relevance, tags, '
    'chunk_desc, question; relevance unless named). HERB_V4_CLUSTER_READING, his '
    'two readings of 2026-10-08 ("indeed, try them"): scopes (the scopes are the clusters; the '
    "largest clouds are the main cluster of the clouds' sizes, the dogleg deciding; minorities "
    'with the same parent are kept) or formed (the clustering forms the clouds: scopes with hit '
    'chunks and the same parent are one cloud). The chunks outside the kept scopes are out of '
    'the pool (`v4_walk.scope_clusters`).')
RETRIEVAL_FLAGS['name'] = (
    'HERB_V4_SCOPE_STEP=name (his 2026-10-11 "if we take our latest best '
    'run, and do that part for scope instead"): no second call. The border is every branch of '
    'the tree whose name stands in the question word for word (`scope_by_name`); the chunks '
    'outside it are out of the pool, and with no such name nothing is cut. Inside it the order '
    'is the chain\'s (`v4_walk.chain`).')
RETRIEVAL_FLAGS['combo'] = (
    'HERB_V4_SCOPE_STEP=combo, the step before the one as it stands (his 2026-10-12 "the combo '
    'should fucking work.. So, if we use the chunk-cloud, see if you can find a way to combo or '
    'lift with the tags", then "/goal solve this"): no second call, no strength, no facet. '
    'Every chunk is handed over as it is. The border is the '
    'name step\'s (`scope_by_name`). Inside it (`v4_walk.cloud_combo`): the chunk descriptions\' '
    'closeness to the question with the border\'s names taken out (each replaced by "the" and '
    'the tree\'s word for that level, `_without_names`), and each chunk\'s closest eligible tag '
    'to a query tag, are each cut into HERB_V4_K clusters; a chunk\'s step is its two levels '
    'added; the scope is the parents (a channel, or a product\'s documents, transcripts, pull '
    'requests, links, chats) that hold the majority of the chunks on the first two steps, and '
    'inside a step the chunks in scope come first, then the two standings added. The first '
    'call\'s description is embedded and kept in the row and does not enter the order.')
RETRIEVAL_FLAGS['persons'] = (
    'HERB_V4_SCOPE_STEP=persons, the step as it stands (2026-10-13, under his "/goal solve '
    'this"; his 2026-10-11 "what fucking IS missing, is a REAL use of the graph format ... '
    'things related to persons etc (or users) and nothing at all is actually using the graph"). '
    'The border and the order are the combo step\'s, with the query\'s facets as an influence on '
    'the tag relationship (2026-10-15/16, his "they are supposed to influence the already existing '
    'relationship for chunks and tags", "how important the facet conecpt is", "YOU CANNOT FORCE '
    'THEM TO TRY AND CHANGE THE FUCKING ORDERS"; `v4_walk.facet_influenced_nearness`, '
    'HERB_V4_FACETS): the facet net reads each query tag against the question and the '
    'description; a reading\'s level among that facet\'s levels over the graph\'s edges is the '
    'facet\'s weight; an edge\'s weight for a query tag is the tag\'s closeness plus, per facet, '
    'that weight times where the edge stands in the facet\'s ranking. What differs from the combo '
    'step besides is what is '
    'handed over, in that order (`_hand_over`): no message of a channel apart; of a batch of pull '
    'requests only the product\'s own; of a batch of Slack messages only the conversations '
    'that are not about another project\'s pull request, each conversation whole where it '
    'first shows (its messages in the chunk before or after come with it and are not handed '
    'over again); any other chunk as it is. From the graph (`product_persons`): a channel is '
    'apart when it has employees and none of them is tied to another channel or to a meeting '
    'of the product; the product\'s people are the employees of its other channels and of its '
    'meetings. From the records, through the chunk\'s pointer: a pull request is the '
    'product\'s own when its author is one of the product\'s people; a conversation is a '
    'channel\'s messages between its long gaps (`v4_walk.conversations`, no length given); it '
    'is about another project\'s when a message of it links to a pull request that is not the '
    'product\'s own and none links to an own pull request or to a document of the product. '
    'The agent\'s find, read off the benchmark\'s own account of the distraction it holds '
    '(arXiv 2506.23139), not his concept; it never reads the question.')
SCOPE_STEPS = ('persons', 'combo', 'name', 'map', 'both', 'tags', 'call', 'off', 'clouds', 'hits',
               'levels', 'cluster')
# The words for what only this arm writes into a run folder (harness.fields, FIELDS.md), for the
# step as it stands. A run made with an older step writes other fields under scope, ranking and
# diagnostics, and those have no words here.
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
            'same_thing_pairs': sub('How close two graph tags are when they are the same word '
                                    'in another spelling.', {
                'pairs': 'How many such pairs of graph tags there are.',
                'median': 'The middle cosine of those pairs.',
                'point': 'The percent of the pairs that lie under the level.',
                'level': 'The cosine that percent of the pairs lie under.',
            }),
            'counts': sub('What was read from the graph.', {
                'chunks': 'Chunks in the pool.',
                'graph_tags': 'Tags that sit on a chunk of the pool.',
                'edges': 'Tag-to-chunk edges read.',
                'products': 'Products.',
                'eligible_graph_tags': "Tags that are not a product's name; only those are "
                                       'compared with the query tags.',
                'eligible_edges': 'Edges that carry such a tag.',
                'chunks_without_an_edge': 'Chunks that carry no such edge.',
                'near_groups': 'Groups of chunks that follow each other in one file.',
                'chunks_in_a_near_group': 'Chunks that sit in such a group.',
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
            'step': 'The step this question went through: persons is the step as it stands.',
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
            'facets': sub("The query's facets as an influence on the tag relationship "
                          "(HERB_V4_FACETS): the facet net reads each query tag against the "
                          "question and the description; a reading's level among its facet's "
                          "levels over the graph's edges is the facet's weight (0 to 1); an "
                          "edge's weight for a query tag is the tag's closeness plus, per facet, "
                          "that weight times where the edge stands in the facet's ranking, in the "
                          "query tag's own spread of closeness.", {
                'mode': 'question: one reading per facet for the whole question, the middle '
                        "one of its query tags'; tag: each query tag's own; off: no facets.",
                'readings': whole("Per query tag as written, the facet net's four scores: "
                                  'temporal, why, activity, concreteness.'),
                'weights': whole('For the question, or per query tag, the four facets\' weights '
                                 'from 0 to 1, in that order.'),
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
            'named_facets': 'The facet the first call named for each query tag. This step does '
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
HIT_STAGES = ('arm', 'tags', 'chunk_desc', 'question', 'topic', 'picked')
SCAN_SCATTERS, SCAN_SEED = RETRIEVAL_FLAGS['scan_scatters'], RETRIEVAL_FLAGS['scan_seed']
LEVELS = ('product', 'kind of record', 'channel')
CLOUD_LEVELS = dict(zip(('product', 'kind', 'channel'), LEVELS))
CLOUD_SWITCHES = ('HERB_V4_CLOUD_SHAPE', 'HERB_V4_CLOUD_LEVELS', 'HERB_V4_CLOUD_PLACES',
                  'HERB_V4_CLOUD_GROUPS')


def _k_nearest():
    """HERB_V4_K, 5 unless named (his 2026-10-09 "what if we force the n of k in the kNN
    instead?", "5 for the total amount of k?"): with the step as it stands the number of
    clusters a list of nearness values is cut into; with the older steps how many nearest graph
    tags a query tag picks."""
    value = os.environ.get('HERB_V4_K', '5')
    if not value.isdigit() or int(value) < 1:
        raise ValueError(f'HERB_V4_K must be a count, got {value!r}')
    return int(value)


def _offline():
    value = os.environ.get('HERB_V4_OFFLINE', 'off')
    if value not in ('off', 'on'):
        raise ValueError(f'HERB_V4_OFFLINE must be off or on, got {value!r}')
    return value == 'on'


FACET_MODES = ('question', 'tag', 'off')


def _facets_mode():
    """HERB_V4_FACETS (his 2026-10-15 "take 10.. with and without facets", and his worry that
    each query tag's own reading "will overweight these tags"): question, one level per facet for
    the whole question (the default); tag, each query tag's own; off, no facets."""
    value = os.environ.get('HERB_V4_FACETS', FACET_MODES[0])
    if value not in FACET_MODES:
        raise ValueError(f'HERB_V4_FACETS must be one of {FACET_MODES}, got {value!r}')
    return value


def _query_facet_readings(query, phrases):
    """Per query tag the facet net's four scores (temporal, why, activity, concreteness), the net
    that scored the graph's edges (his 2026-10-09 "we DID build that neural net for judging the
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


def _listed(name, default, allowed):
    """A comma-separated switch as a tuple of distinct allowed values."""
    values = tuple(os.environ.get(name, default).split(','))
    if not values or len(set(values)) != len(values) or any(v not in allowed for v in values):
        raise ValueError(f'{name} must list distinct values of {tuple(allowed)}, got {values!r}')
    return values


def _scope_step():
    """The scope step and, with `clouds`, its settings: the shape of the numbers, the levels
    and the places gauged, and whether the clustering picks the number of groups or makes two;
    None for the settings otherwise."""
    step = os.environ.get('HERB_V4_SCOPE_STEP', 'persons')
    if step not in SCOPE_STEPS:
        raise ValueError(f'HERB_V4_SCOPE_STEP must be one of {SCOPE_STEPS}, got {step!r}')
    if step != 'clouds' and any(os.environ.get(name) is not None for name in CLOUD_SWITCHES):
        raise ValueError('The HERB_V4_CLOUD_ switches are read only with '
                         'HERB_V4_SCOPE_STEP=clouds')
    if step != 'hits' and os.environ.get('HERB_V4_HIT_STAGES') is not None:
        raise ValueError('HERB_V4_HIT_STAGES is read only with HERB_V4_SCOPE_STEP=hits')
    if step != 'levels' and os.environ.get('HERB_V4_LEVEL_PLACES') is not None:
        raise ValueError('HERB_V4_LEVEL_PLACES is read only with HERB_V4_SCOPE_STEP=levels')
    if step != 'cluster' and any(os.environ.get(name) is not None for name in
                                 ('HERB_V4_CLUSTER_READING', 'HERB_V4_CLUSTER_PLACES')):
        raise ValueError('The HERB_V4_CLUSTER_ switches are read only with '
                         'HERB_V4_SCOPE_STEP=cluster')
    if step == 'tags':
        level = os.environ.get('HERB_V4_SCOPE_LEVEL', 'product')
        value = os.environ.get('HERB_V4_SCOPE_VALUE', 'majority')
        if level not in ('product', 'kind', 'leaf') or value not in ('majority', 'closeness'):
            raise ValueError('HERB_V4_SCOPE_LEVEL must be product, kind or leaf and '
                             'HERB_V4_SCOPE_VALUE majority or closeness')
        return step, {'level': level, 'value': value}
    if step == 'cluster':
        reading = os.environ.get('HERB_V4_CLUSTER_READING', 'scopes')
        if reading not in ('scopes', 'formed'):
            raise ValueError(f'HERB_V4_CLUSTER_READING must be scopes or formed, got {reading!r}')
        return step, {'reading': reading,
                      'places': list(_listed('HERB_V4_CLUSTER_PLACES', 'relevance',
                                             WK.CLUSTER_PLACES))}
    if step != 'levels' and os.environ.get('HERB_V4_LEVEL_DEPTH') is not None:
        raise ValueError('HERB_V4_LEVEL_DEPTH is read only with HERB_V4_SCOPE_STEP=levels')
    if step == 'levels':
        depth = os.environ.get('HERB_V4_LEVEL_DEPTH', 'all')
        if depth != 'all' and not (depth.isdigit() and int(depth) >= 1):
            raise ValueError(f'HERB_V4_LEVEL_DEPTH must be all or a count of levels, got '
                             f'{depth!r}')
        return step, {'places': list(_listed('HERB_V4_LEVEL_PLACES', 'tags,chunk_desc',
                                             WK.LEVEL_PLACES)),
                      'depth': None if depth == 'all' else int(depth)}
    if step == 'hits':
        return step, {'stages': list(_listed('HERB_V4_HIT_STAGES', 'arm', HIT_STAGES))}
    if step != 'clouds':
        return step, None
    places = _listed('HERB_V4_CLOUD_PLACES', 'tags,description', WK.PLACE_NAMES)
    shapes = tuple((os.environ.get('HERB_V4_CLOUD_SHAPE') or '').split(','))
    if len(shapes) == 1:
        shapes = shapes * len(places)
    if len(shapes) != len(places) or any(shape not in WK.CLOUD_SHAPES for shape in shapes):
        raise ValueError(f'HERB_V4_CLOUD_SHAPE must name one of {WK.CLOUD_SHAPES} for every '
                         f'place or one per place, got {shapes!r}')
    groups = os.environ.get('HERB_V4_CLOUD_GROUPS', 'picked')
    if groups not in ('picked', 'two'):
        raise ValueError(f'HERB_V4_CLOUD_GROUPS must be picked or two, got {groups!r}')
    levels = _listed('HERB_V4_CLOUD_LEVELS', 'product,kind,channel', CLOUD_LEVELS)
    return step, {'shape': dict(zip(places, shapes)), 'groups': groups,
                  'levels': [CLOUD_LEVELS[level] for level in levels], 'places': list(places)}


def tree_levels(tree):
    """The tree's scopes by level (`LEVELS`: a path's depth), each as (path, chunk indices), in
    sorted path order."""
    levels = {name: [] for name in LEVELS}
    for path in sorted(tree['paths']):
        levels[LEVELS[path.count('/')]].append(
            (path, np.array(sorted(tree['paths'][path]), dtype=np.int64)))
    return levels


def tree_level(tree, level):
    """The scopes at one level of the tree, as (path, chunk indices): `product` the products
    with everything under them (a branch; his 2026-10-09 "if majority of something, BRANCH is
    chosen"), `kind` the product/kind places, `leaf` the lowest places (`tree_leaves`)."""
    if level == 'leaf':
        return tree_leaves(tree)
    depth = {'product': 1, 'kind': 2}[level]
    return [(path, np.array(sorted(tree['paths'][path]), dtype=np.int64))
            for path in sorted(tree['paths']) if path.count('/') == depth - 1]


def tree_leaves(tree):
    """Each chunk's own scope: the tree's places that hold no place under them (a channel, or
    a kind of record without channels), as (path, chunk indices), in sorted path order."""
    inner = {path.rsplit('/', 1)[0] for path in tree['paths'] if '/' in path}
    return [(path, np.array(sorted(tree['paths'][path]), dtype=np.int64))
            for path in sorted(tree['paths']) if path not in inner]


def _stage_hits(stage, walked, layer, rows, char_budget, k, doc_cache):
    """The chunks one stage alone would deliver: its own order, the chain's order breaking
    ties, cut as the delivery is cut (the character budget, or k). `arm` is the chain's order.
    `topic` orders only the chunks that carry a tag that is the same thing as a query tag;
    `picked` is every such chunk, uncut."""
    if stage == 'arm':
        order = list(walked['order'])
    else:
        name = 'hits' if stage == 'picked' else stage
        number = WK.place_numbers((name,), walked, layer)[name]
        if stage == 'picked':
            return np.flatnonzero(number > 0)
        position = np.empty(number.size, dtype=np.int64)
        position[np.asarray(walked['order'], dtype=np.int64)] = np.arange(number.size)
        order = sorted(range(number.size), key=lambda i: (-number[i], position[i]))
        if stage == 'topic':
            order = [i for i in order if number[i] > 0]
    if not order:
        return np.zeros(0, dtype=np.int64)
    if char_budget is None:
        return np.array(order[:k], dtype=np.int64)
    kept = _budget_contexts([rows[i] for i in order], char_budget, doc_cache)[3]['kept']
    return np.array(order[:int(kept)], dtype=np.int64)


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
    descriptions: dict | None = None
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
    five facet values, each chunk's product and file neighbours, and the tree."""
    started = time.perf_counter()
    RETRIEVAL_FLAGS['offline_at_prepare'] = _offline()
    (RETRIEVAL_FLAGS['scope_step_at_prepare'],
     RETRIEVAL_FLAGS['scope_settings_at_prepare']) = _scope_step()
    RETRIEVAL_FLAGS['k_at_prepare'] = _k_nearest()
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
            persons = None
            if _scope_step()[0] == 'persons':
                say('artefact_v4: reading the people of each product\'s channels and meetings')
                persons = product_persons(
                    session.execute_read(lambda tx: [dict(r) for r in tx.run(CHANNEL_PEOPLE_CYPHER)]),
                    session.execute_read(lambda tx: [dict(r) for r in tx.run(MEETING_PEOPLE_CYPHER)]))
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
                               shape['product'], adjacency['ptr'], adjacency['members'])
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
        if persons is not None:
            missing = sorted({found[c]['product'] for c in chunk_ids} - set(persons))
            if missing:
                raise ValueError(f'The graph names no channel and no meeting for {missing}')
            provenance['counts']['channels_apart'] = sum(len(p['apart']) for p in persons.values())
            provenance['counts']['people'] = sum(len(p['people']) for p in persons.values())
            say(f'artefact_v4: {provenance["counts"]["channels_apart"]} channels apart over '
                f'{len(persons)} products')
    finally:
        driver.close()
    elapsed = time.perf_counter() - started
    say(f'artefact_v4: prepared {len(chunk_ids)} chunks, {len(graph_tags)} tags, '
        f'{len(endpoints)} edges in {elapsed:.1f}s')
    # each chunk row with its product and its channel as the graph ties them
    rows = tuple({**dict(r), 'product': str(found[r['chunkId']]['product']),
                  'channels': [str(ch) for ch in found[r['chunkId']]['channels']]}
                 for r in chunk_rows)
    return Prepared(rows, chunk_ids, graph_tags, tag_vectors,
                    chunk_vectors, layer, tree, cache, provenance,
                    BuildStats(elapsed, ModelUsage(), [INTERPRET_MODEL]),
                    read_descriptions(chunk_ids) if _scope_step()[0] == 'map' else None,
                    persons)


def read_descriptions(chunk_ids):
    """The chunk description texts of the pool, chunk id -> text with its blanks run together,
    from the side file (`DESCRIPTIONS`); the file is checked against its recorded sha256."""
    data = DESCRIPTIONS.read_bytes()
    if _sha(data) != DESCRIPTIONS_SHA256:
        raise ValueError(f'{DESCRIPTIONS} is not the file the description vectors were made from')
    found = {}
    for line in data.decode('utf-8').splitlines():
        if line.strip():
            row = json.loads(line)
            found[row['id']] = ' '.join(str(row['text']).split())
    missing = [c for c in chunk_ids if not found.get(c)]
    if missing:
        raise ValueError(f'{len(missing)} pool chunks have no description text')
    return {c: found[c] for c in chunk_ids}


def branch_map(prepared, inside, branches):
    """The map of a border as the graph has it, for the map call. The border's parts (a chunk's
    `parent`: a channel, or a product's documents, transcripts, PRs, links) in name order, under
    each its chunks in their own order, one line a chunk: a label, its description, and between
    square brackets its eligible tags, the most central (topic) first. With more than one branch
    a part's line names its branch. Returns the text and label -> chunk index."""
    if prepared.descriptions is None:
        raise ValueError('The description texts were not read; the map step reads them at prepare')
    layer = prepared.layer
    tags = {int(i): [] for i in inside}
    for e in np.lexsort((-layer['raw'][:, 0], layer['edge_chunk'])).tolist():
        c = int(layer['edge_chunk'][e])
        if c in tags:
            tags[c].append(_readable(prepared.graph_tags[int(layer['edge_tag'][e])]))
    parts = {}
    for i in inside:
        row = prepared.chunk_rows[int(i)]
        if row.get('parent') is None or row.get('ordinal') is None:
            raise ValueError('A chunk of the border has no parent or no place in it')
        parts.setdefault(str(row['parent']), []).append((row['ordinal'], int(i)))
    lines, chunk_of = [], {}
    for parent in sorted(parts):
        name = parent
        for branch in branches:
            if parent.startswith(f'product.{branch}.'):
                name = parent[len(f'product.{branch}.'):]
                if len(branches) > 1:
                    name = f'{branch}.{name}'
        lines.append('== ' + name.replace('.', ' / ') + ' ==')
        for _, i in sorted(parts[parent]):
            label = f'p{len(chunk_of) + 1}'
            chunk_of[label] = i
            lines.append(f'{label} {prepared.descriptions[prepared.chunk_ids[i]]}'
                         + (f' [tags: {", ".join(tags[i])}]' if tags[i] else ''))
    return '\n'.join(lines), chunk_of


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
    parsed content with its places, the model usage and one record a call. Only the first
    call is asked, and no places come back, unless the scope step is `call`."""
    offline = _offline()
    dropped = []

    def validate(raw):
        cleaned, n = _collapse_duplicate_tags(raw)
        dropped.append(n)
        return Q.parse(text, cleaned)

    content, usage, first = _ask('querytag', Q.request(text), validate, prepared.cache_dir,
                                 offline)
    first['duplicate_tags_dropped'] = dropped[-1] if dropped else None
    if _scope_step()[0] != 'call':
        return content, usage, [first]
    places, used, second = _ask('scope', Q.scope_request(content, prepared.tree['text']),
                                Q.parse_places, prepared.cache_dir, offline)
    return replace(content, places=places), _add(usage, used), [first, second]


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
    rows, to_description = list(got['tags']), got['tags_to_description'].tolist()
    to_chunks = [got.get('tags_to_chunks')]
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
        to_chunks.append(got.get('tags_to_chunks'))
        embeddings['question_side_tags'] = {'tags': len(question_side),
                                            'embedding': recipe['vector_sha256']}
    # Each query tag names one facet (the first call's answer); the chain reads it as an index.
    named_facet = np.array([t.facet_index for t in (*query.tags, *query.query_tags)],
                           dtype=np.int64)
    layer = prepared.layer
    step, cloud = _scope_step()
    doc_cache = {}
    # The older steps order by the chain's strength; the step as it stands makes none.
    walked = None if step in ('persons', 'combo', 'map', 'both') else WK.chain(layer, {
        'cosines': np.array(rows, dtype=np.float64),
        'named_facet': named_facet,
        'description_cosines': np.array(to_description, dtype=np.float64),
        'd_description': d_description, 'd_question': d_question}, COS_NOISE, _k_nearest())
    found_near = None                         # the tags side's closeness as found, when facets deal it
    if step in ('persons', 'combo'):          # the same border; persons adds the query's facets
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
        dealt, facets_said = None, None
        mode = _facets_mode() if step == 'persons' else 'off'
        if mode != 'off':
            found_near, _ = WK.tags_nearness(layer, query_rows)
            phrases = [t.text for t in (*query.tags, *query.query_tags)]
            readings = _query_facet_readings(query, phrases)
            floors = _facet_floors(layer)
            if mode == 'question':
                weights = [_facet_weights(np.median(readings, axis=0), floors)] * len(phrases)
            else:
                weights = [_facet_weights(row, floors) for row in readings]
            dealt, _, _ = WK.facet_influenced_nearness(layer, query_rows, np.array(weights))
            facets_said = {
                'readings': {phrase: [float(r) for r in row] for phrase, row in zip(phrases, readings)},
                'weights': ({'the question': weights[0]} if mode == 'question' else
                            {phrase: w for phrase, w in zip(phrases, weights)}),
                'chunks_whose_nearness_changed': int(sum(1 for i in inside
                                                         if dealt[i] != found_near[i]))}
        combo = WK.cloud_combo(layer, query_rows, d_bare, inside, parent_of, _k_nearest(),
                               tags_near=dealt)
        order, gauged = combo['order'], combo['record']
        gauged['scopes_taken'] = [parents[s] for s in gauged['scopes_taken']]
        scope = {**scope, 'combo': gauged, 'chunks_kept': len(order),
                 'chunks_cut': len(prepared.chunk_ids) - len(order)}
        if step == 'persons':
            scope['facets'] = {'mode': mode, **(facets_said or {})}
        said = ('under ' + (', '.join(scope['names_in_the_question'])
                            or 'no name of the tree, nothing cut')
                + f'; {gauged["chunks_on_each_step"].get(2, 0)} chunks in both first clusters, '
                  f'the scope {len(gauged["scopes_taken"])} parents')
    elif step == 'map':
        first, gauged = WK.border_by_nearness(d_question, dict(tree_level(prepared.tree, 'product')),
                                             _k_nearest())
        inside = np.flatnonzero(first)
        t_near, t_edge = WK.tags_nearness(layer, np.array(rows, dtype=np.float64))
        by = [inside[np.lexsort((layer['id_rank'][inside], -np.asarray(x, dtype=np.float64)[inside]))]
              for x in (t_near, d_description, d_question)]
        turned, source = WK.in_turn(by)
        mapped = ({'reason': 'nothing was cut: no branch holds a near chunk'}
                  if gauged['nothing_cut'] else None)
        named = []
        if mapped is None:
            map_text, chunk_of = branch_map(prepared, inside, gauged['kept'])
            pieces, used, asked = _ask('map', Q.map_request(query, map_text), Q.parse_pieces,
                                       prepared.cache_dir, _offline())
            say(f'artefact_v4: {qid} {asked["stage"]} cache_hit={asked["cache_hit"]} '
                f'asks={asked["asks"]} offline={asked["offline"]}')
            interp_usage = _add(interp_usage, used)
            stages.append(asked)
            named = list(dict.fromkeys(chunk_of[x] for x in pieces if x in chunk_of))
            mapped = {'chunks': len(chunk_of), 'parts': map_text.count('\n== ') + 1,
                      'chars': len(map_text), 'labels_named': len(pieces),
                      'labels_not_in_the_map': [x for x in pieces if x not in chunk_of]}
        taken = set(named)
        order = named + [i for i in turned if i not in taken]
        came = {i: 'named' for i in named}
        for i, which in zip(turned, source):
            came.setdefault(i, ('tags', 'description', 'question')[which])
        scope = {'gauged': gauged, 'map': mapped,
                 'named_chunk_ids': [prepared.chunk_ids[i] for i in named],
                 'chunks_kept': int(first.sum()), 'chunks_cut': int((~first).sum())}
        said = (f'of the {scope["chunks_kept"]} chunks kept (border '
                + (', '.join(gauged['kept']) or 'none, nothing cut')
                + f'; the map reader named {len(named)} chunks)')
        mapped_view = {'came': came, 'tags_nearness': t_near, 'edge': t_edge}
    elif step == 'both':
        sided = WK.both_sides(layer, np.array(rows, dtype=np.float64), named_facet,
                              d_description, tree_leaves(prepared.tree),
                              dict(tree_level(prepared.tree, 'product')), _k_nearest())
        first, order, gauged = sided['border'], sided['order'], sided['record']
        scope = {**gauged, 'chunks_kept': int(first.sum()), 'chunks_cut': int((~first).sum())}
        inside = gauged['inside']
        said = (f'of the {scope["chunks_kept"]} chunks kept (k={gauged["k"]}; border '
                + (', '.join(gauged['branches']) or 'none, no scope in both scope clouds')
                + f'; inside it {inside["in_both"]} chunks in both clouds, '
                  f'{inside["in_one"]} in one, {inside["in_neither"]} in neither)')
    elif step == 'call':
        first, scope = scope_first(query.places, prepared.tree, len(prepared.chunk_ids))
        order = sorted(walked['order'], key=lambda i: not first[i])
        said = f'under the products of {scope["places_in_the_tree"]}'
    elif step == 'name':
        first, scope = scope_by_name(text, prepared.tree, len(prepared.chunk_ids))
        order = ([i for i in walked['order'] if first[i]] if first.any()
                 else list(walked['order']))
        scope['chunks_kept'] = len(order)
        scope['chunks_cut'] = len(walked['order']) - len(order)
        said = ('under ' + (', '.join(scope['names_in_the_question'])
                            or 'no name of the tree, nothing cut'))
    elif step == 'off':
        first = np.zeros(len(prepared.chunk_ids), dtype=bool)
        scope, order, said = {}, list(walked['order']), 'no scope step'
    elif step == 'tags':
        first, gauged = WK.scope_by_tags(walked['picked_edge'], np.array(rows, dtype=np.float64),
                                         walked['facet_class'], walked['facet_orders'], layer,
                                         tree_level(prepared.tree, cloud['level']),
                                         majority=cloud['value'] == 'majority')
        gauged['level'], gauged['value'] = cloud['level'], cloud['value']
        order = [i for i in walked['order'] if first[i]]
        scope = {'gauged': gauged, 'chunks_kept': int(first.sum()),
                 'chunks_cut': int((~first).sum())}
        said = (f'of the {scope["chunks_kept"]} chunks kept (edges surviving the facets '
                f'{gauged["edges_surviving_by_depth"]} of {gauged["picked_edges"]}; their tags lie in '
                f'{gauged["scopes_with_a_tag"]} scopes, {gauged["clusters"]} clusters, '
                f'{len(gauged["kept"])} kept: '
                + (', '.join(f'{r["scope"]} {r["value"]:.1f}' for r in gauged['kept'][:3]) or 'none')
                + ('...' if len(gauged['kept']) > 3 else '') + ')')
    elif step == 'cluster':
        hits, apart = WK.cluster_hits(cloud['places'], walked, layer, d_description, d_question)
        leaves = tree_leaves(prepared.tree)
        first = np.zeros(len(prepared.chunk_ids), dtype=bool)
        gauged = {}
        for place in cloud['places']:
            kept, gauged[place] = WK.scope_clusters(hits[place], leaves,
                                                    cloud['reading'] == 'formed')
            gauged[place]['found'] = apart[place]
            if gauged[place]['hit_chunks']:
                first |= kept
        if not first.any():
            first[:] = True                   # nothing hit in any place: nothing is cut
        order = [i for i in walked['order'] if first[i]]
        scope = {**cloud, 'gauged': gauged, 'chunks_kept': int(first.sum()),
                 'chunks_cut': int((~first).sum())}
        said = (f'of the {scope["chunks_kept"]} chunks kept ({cloud["reading"]}; '
                + '; '.join(f'{place}: {g["hit_chunks"]} hit in {g["hit_scopes"]} scopes, '
                            f'{g["clouds"]} clouds, largest '
                            + (', '.join(f'{c["cloud"]} {c["hit_chunks"]}'
                                         for c in g['largest'][:3]) or 'none')
                            + ('...' if len(g['largest']) > 3 else '')
                            + f', {len(g["minorities"])} minorities'
                            for place, g in gauged.items()) + ')')
    elif step == 'levels':
        relevancy, sizes = WK.level_places(cloud['places'], np.array(rows, dtype=np.float64),
                                           layer, d_description, d_question, cloud['depth'])
        leaves = tree_leaves(prepared.tree)
        first = np.zeros(len(prepared.chunk_ids), dtype=bool)
        gauged = {}
        for place in cloud['places']:
            kept, gauged[place] = WK.level_clouds(relevancy[place], leaves)
            gauged[place]['levels'] = sizes[place]
            if gauged[place]['clouds']:
                first |= kept
        if not first.any():
            first[:] = True                   # no cloud in any place: nothing is cut
        order = [i for i in walked['order'] if first[i]]
        scope = {**cloud, 'gauged': gauged, 'chunks_kept': int(first.sum()),
                 'chunks_cut': int((~first).sum())}
        said = (f'of the {scope["chunks_kept"]} chunks kept (levels of '
                f'{"+".join(cloud["places"])}; '
                + '; '.join(f'{place}: {g["hit_chunks"]} hit, {g["clouds"]} clouds, largest '
                            + (', '.join(c['scope'] for c in g['largest'][:3]) or 'none')
                            + ('...' if len(g['largest']) > 3 else '')
                            + f', {len(g["minorities"])} minorities'
                            for place, g in gauged.items()) + ')')
    elif step == 'hits':
        stage_hits = {stage: _stage_hits(stage, walked, layer, prepared.chunk_rows, char_budget,
                                         k, doc_cache) for stage in cloud['stages']}
        places = [place for level in tree_levels(prepared.tree).values() for place in level]
        first, scan = WK.scan_clouds(np.concatenate(list(stage_hits.values())), places,
                                     len(prepared.chunk_ids), SCAN_SCATTERS, SCAN_SEED)
        order = [i for i in walked['order'] if first[i]]
        scope = {**cloud, 'stage_hits': {stage: [prepared.chunk_ids[i] for i in found]
                                         for stage, found in stage_hits.items()},
                 **scan, 'chunks_kept': int(first.sum()), 'chunks_cut': int((~first).sum())}
        said = (f'of the {scope["chunks_kept"]} chunks kept ({scan["hits"]} hits of '
                f'{"+".join(cloud["stages"])}; clouds '
                + (', '.join(f'{c["place"]} {c["hits"]}' for c in scan['clouds']) or 'none')
                + f'; minorities {len(scan["minorities"])})')
    else:
        levels = tree_levels(prepared.tree)
        first, clouds = WK.scope_clouds(
            WK.place_numbers(cloud['places'], walked, layer,
                             np.vstack(to_chunks) if 'tags_to_desc' in cloud['places'] else None),
            {level: levels[level] for level in cloud['levels']}, cloud['shape'],
            2 if cloud['groups'] == 'two' else None)
        order = [i for i in walked['order'] if first[i]]
        scope = {**cloud, 'clouds': clouds, 'chunks_kept': int(first.sum()),
                 'chunks_cut': int((~first).sum())}
        said = (f'of the {scope["chunks_kept"]} chunks kept '
                f'({"/".join(cloud["shape"].values())}; groups '
                + ', '.join(f'{name} ' + '/'.join(str(clouds[name][level]['groups'])
                                                  for level in cloud['levels'])
                            for name in cloud['places']) + ')')
    scope['step'] = step
    ordered_rows = [prepared.chunk_rows[i] for i in order]
    handed = None
    if step == 'persons':
        contexts, id_lists, context_ids, budget, delivered, handed = _hand_over(
            order, prepared, char_budget, k, doc_cache)
        boundary = budget['boundary']['id'] if budget and budget['boundary'] else None
    elif char_budget is not None:
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
    if handed is None:
        delivered = order[:credited]
    scope['delivered_under_the_products'] = int(first[delivered].sum())
    if step in ('persons', 'combo'):
        diagnostics, ranking = _combo_record(qid, combo, layer, prepared, query, order, delivered,
                                             scope, said, boundary, rows, tags, question_side,
                                             d_description, d_question, found_near)
        if handed is not None:
            ranking.update(handed['per_chunk'])
            gone = handed['record']
            say(f'artefact_v4 {qid}: {gone["chunks_gone_through"]} chunks gone through, nothing '
                f'handed over of {sum(gone["chunks_with_nothing_handed_over"].values())}; '
                f'{sum(gone["records_left_out"].values())} records left out; '
                f'{gone["conversations_handed_over"]} conversations whole')
    elif step == 'map':
        diagnostics, ranking = _map_record(qid, mapped_view, layer, prepared, query, order,
                                           delivered, scope, said, boundary, rows, tags,
                                           question_side, d_description, d_question)
    elif step == 'both':
        diagnostics, ranking = _both_record(qid, sided, layer, prepared, query, order, delivered,
                                            scope, said, boundary, rows, tags, question_side)
    else:
        diagnostics, ranking = _chain_record(qid, walked, layer, prepared, query, order,
                                             delivered, scope, said, boundary, rows, tags,
                                             question_side, to_description)
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
    if handed is not None:
        meta['handed_over'] = handed['record']
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
    `facets_in_equal_closeness`): per delivered chunk its step, its level and nearness on each
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


def _map_record(qid, view, layer, prepared, query, order, delivered, scope, said, boundary, rows,
                tags, question_side, d_description, d_question):
    """What a row keeps of the step as it stands: per delivered chunk where it came from (named
    by the map reader, or a route's turn), its nearness on each route, and its closest tag."""
    came = [view['came'][i] for i in delivered]
    edges = [int(view['edge'][i]) for i in delivered]
    diagnostics = {
        'credited_delivered_rows': len(delivered),
        'boundary_chunk_id_not_credited': boundary,
        'chunks_with_an_eligible_edge': int((layer['n_c'] > 0).sum()),
        'product_named_tags_left_out': int((~layer['eligible']).sum()),
        'query_tags': len(rows),
        'phrases_standing_in_both_tag_lists': len({t.strip().casefold() for t in tags}
                                                  & {t.strip().casefold() for t in question_side}),
        'named_facets': [t.facet for t in (*query.tags, *query.query_tags)],
        'delivered_from': {name: came.count(name)
                           for name in ('named', 'tags', 'description', 'question')},
    }
    say(f'artefact_v4 {qid}: {len(delivered)} delivered, '
        f'{scope["delivered_under_the_products"]} {said}; delivered '
        + ', '.join(f'{count} {name}' for name, count in diagnostics['delivered_from'].items()))
    ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
               'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
               'delivered_from': came,
               'delivered_tags_nearness': [float(view['tags_nearness'][i]) for i in delivered],
               'delivered_description_nearness': [float(d_description[i]) for i in delivered],
               'delivered_question_nearness': [float(d_question[i]) for i in delivered],
               'delivered_graph_tags': [prepared.graph_tags[int(layer['edge_tag'][e])]
                                        if e >= 0 else None for e in edges]}
    return diagnostics, ranking


def _both_record(qid, sided, layer, prepared, query, order, delivered, scope, said, boundary,
                 rows, tags, question_side):
    """What a row keeps of the step as it stands (`v4_walk.both_sides`): per delivered chunk
    which clouds hold it, its level and nearness on each side, and the query tag, graph tag and
    facet rank its place among the tags' order comes from."""
    clouds = [('both', 'one', 'neither')[int(sided['group'][i])] for i in delivered]
    edges = [int(sided['edge'][i]) for i in delivered]
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
        'delivered_in_clouds': {name: clouds.count(name) for name in ('both', 'one', 'neither')},
    }
    say(f'artefact_v4 {qid}: {len(delivered)} delivered, '
        f'{scope["delivered_under_the_products"]} {said}; delivered '
        + ', '.join(f'{count} in {name}' for name, count in
                    diagnostics['delivered_in_clouds'].items()))
    ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
               'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
               'delivered_clouds': clouds,
               'delivered_tags_level': [int(sided['level']['tags'][i]) for i in delivered],
               'delivered_description_level': [int(sided['level']['description'][i])
                                               for i in delivered],
               'delivered_tags_nearness': [float(sided['tags_nearness'][i]) for i in delivered],
               'delivered_description_nearness': [float(sided['description_nearness'][i])
                                                  for i in delivered],
               'delivered_facet_rank': [int(sided['facet_rank'][i]) for i in delivered],
               'delivered_query_tags': [int(sided['query_tag'][i]) for i in delivered],
               'delivered_graph_tags': [prepared.graph_tags[int(layer['edge_tag'][e])]
                                        if e >= 0 else None for e in edges]}
    return diagnostics, ranking


def _chain_record(qid, walked, layer, prepared, query, order, delivered, scope, said, boundary,
                  rows, tags, question_side, to_description):
    """What a row keeps of an older step: the chain's strength behind each delivered chunk."""
    terms = {'tags': walked['tags'], 'description': walked['text'], **walked['lift']}
    sums = {name: float(terms[name][delivered].sum()) for name in TERMS}
    total = float(walked['strength'][delivered].sum())
    shares = {name: (sums[name] / total if total != 0. else None) for name in TERMS}
    levels = walked['level'][delivered]
    won = [bool(walked['has_edge'][i] and walked['tags'][i] != 0.) for i in delivered]
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
        'pick': walked['pick'],
        'picked_edges_per_query_tag': walked['picked_edge'].sum(axis=1).tolist(),
        'facet_classes': walked['facet_classes'],
        'named_facets': [t.facet for t in (*query.tags, *query.query_tags)],
        'delivered_winning_edge_is_a_picked_edge': [
            bool(walked['picked_edge'][walked['winner'][i], walked['win_edge'][i]]) if w else None
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
        f'{scope["delivered_under_the_products"]} {said}; shares '
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
    return diagnostics, ranking
