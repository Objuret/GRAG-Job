"""Two complementary texts, one tag/facet and graph-matching procedure.

The original question is analysed directly. Its generated description is analysed
by the exact same procedure. Neither branch supplies tags or readings to the other.
"""
from dataclasses import dataclass

from artefact import query_content as Q
from artefact.querytagger import GENERATE_SYSTEM
from artefact import learned_relations as L

DESCRIBE_SYSTEM = GENERATE_SYSTEM.split('## Tags')[0] + '\nReturn ONLY valid JSON: {"description":"..."}'
ANALYSE_SYSTEM = '''The supplied text expresses an information need, either as a
question or as a description of sought content. Extract semantic retrieval tags
directly from this text and judge each tag's relevance to the content it calls
for, through each of the five facets. Do not rewrite the text first. Do not
invent answer facts or add concepts unsupported by the supplied text.

Keep semantic phrases whole. Include central concepts and peripheral retrieval
handles: subjects, concepts, actions, processes, decisions and kinds of evidence.
Names of people, organisations, products, places and channels are handled as
structure separately; do not turn them into semantic tags. Avoid filler phrases
and generic categories such as "report" or "discussion" alone.

topic: looking at what that content is about, how relevant is the tag?
temporal: looking at its time relations (before and after, now and then, done,
pending, due), how relevant is the tag? A date alone does not establish relevance.
why: looking at its reasons, causes and purposes, how relevant is the tag?
activity: looking at its actions, processes and events, how relevant is the tag?
concreteness: looking at its specifics as against general talk, how relevant is the tag?

Judge tag-to-content relevance through each facet, not the tag's category or the
general importance of a facet. The text need not contain an answer's facts to
express the relationships sought. Use 0 for not relevant through that facet and
1 for could not be more relevant. Do not force a maximum or normalize a sum.
These readings do not claim calibration to learned graph scores.

Return ONLY valid JSON: {"tags":[{"t":"semantic phrase","facets":{
"topic":0.0,"temporal":0.0,"why":0.0,"activity":0.0,"concreteness":0.0}}]}
'''


@dataclass(frozen=True)
class Branch:
    origin: str
    content: Q.QueryContent

    @property
    def text(self):
        return self.content.description


@dataclass(frozen=True)
class ComplementaryQuery:
    question: str
    branches: tuple[Branch, Branch]


def parse_description(raw):
    if not isinstance(raw, dict) or set(raw) != {'description'}:
        raise ValueError('Expected a description only')
    text = raw['description']
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Empty sought-content description')
    return {'description': text}


def parse_analysis(question, text, raw):
    if not isinstance(raw, dict) or set(raw) != {'tags'}:
        raise ValueError('Expected tags and their facet readings only')
    return Q.parse(question, {'description': text, 'tags': raw['tags']})


def interpret(question, call):
    """call(stage, system, user, validator) supplies transport/caching only."""
    Q.request(question)  # Same nonempty-original-question validation.

    def analyse(text):
        # Same stage and request shape: no branch-specific prompt or defaults.
        return call('analyse_representation', ANALYSE_SYSTEM, 'Text: ' + text,
                    lambda raw: parse_analysis(question, text, raw))

    # Direct analysis cannot accidentally depend on the generated description.
    original = analyse(question)
    description = call('describe_question', DESCRIBE_SYSTEM, 'Question: ' + question,
                       parse_description)['description']
    interpreted = analyse(description)
    return ComplementaryQuery(question, (
        Branch('original', original), Branch('interpreted', interpreted)))


def connect_both(query, learned, match, *, graph_tag_names, chunk_ids, topic_cosines):
    """Use both branch texts/tags identically, preserving origin and all evidence.

    match(text, tags) returns the three matching matrices. No branch wins by
    default; this packet is joint evidence, not an invented fusion score.
    """
    packets = {}
    for branch in query.branches:
        matrices = match(branch.text, [t.text for t in branch.content.tags])
        packets[branch.origin] = L.connect(
            branch.content, learned, graph_tag_names=graph_tag_names,
            chunk_ids=chunk_ids, topic_cosines=topic_cosines,
            query_tag_cosines=matrices['query_tag_cosines'],
            query_chunk_cosines=matrices['query_chunk_cosines'],
            description_chunk_cosines=matrices['query_description_cosines'])
        if packets[branch.origin]['omitted_endpoints']:
            raise ValueError('Graph matching omitted learned endpoints')
    if set(packets) != {'original', 'interpreted'}:
        raise ValueError('Both complementary representations are required')
    return packets
