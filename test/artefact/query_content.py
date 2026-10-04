"""Question-only interpretation, before graph access or retrieval arithmetic.

The original question stays available while description-targeted facet readings
are produced. Readings are retained as readings, not calibrated graph weights.
"""
from dataclasses import dataclass
import math

from artefact.querytagger import GENERATE_SYSTEM

FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')
SYSTEM = GENERATE_SYSTEM.split('Return ONLY valid JSON:')[0] + '''
## Tag relevance through facets

Use the original question together with the sought-content description you write.
For each semantic tag, judge its relevance to the content characterised by that
description, seen through each facet. The question supplies the intended context;
the target of these judgments is the sought content, not the question's phrasing.
Do not invent the facts of an unseen answer.

topic: looking at what that content is about, how relevant is the tag?
temporal: looking at its time relations (before and after, now and then, done,
pending, due), how relevant is the tag? A date alone does not establish relevance.
why: looking at its reasons, causes and purposes, how relevant is the tag?
activity: looking at its actions, processes and events, how relevant is the tag?
concreteness: looking at its specifics as against general talk, how relevant is the tag?

These are tag-to-content relationships, not classifications of tags and not
general importance weights for the facets. Describe what the requested content
would contain without supplying missing facts. A description requesting causes,
for example, need not already state those causes to preserve that relationship.

Use the existing query reading range: 0 means not relevant through that facet;
1 means could not be more relevant through it. Do not force any maximum or sum.
These readings do not claim numerical calibration to a graph's learned scores.

## Question tags

Also list the retrieval handles present in the question itself, from its own words and
subjects: its concepts, its subjects, the kinds of evidence it asks for. Keep proper names
whole. A retrieval handle is NOT a common verb, preposition, transitional word, sentence
fragment, or generic category like "report" or "discussion". Names of people,
organisations, products, places and channels are EXCLUDED from these tags as well. Do not
invent concepts the question does not contain.

For each question tag, judge its relevance to the question itself, seen through each of
the same five facets, with the question in place of the sought content and the same
reading range.

Return ONLY valid JSON: {"description":"...","tags":[{"t":"semantic phrase",
"facets":{"topic":0.0,"temporal":0.0,"why":0.0,"activity":0.0,"concreteness":0.0}}],
"query_tags":[{"t":"phrase from the question",
"facets":{"topic":0.0,"temporal":0.0,"why":0.0,"activity":0.0,"concreteness":0.0}}]}
'''


@dataclass(frozen=True)
class QueryTag:
    text: str
    readings: tuple[float, ...]

    def facet_priority(self):
        """An ordinal view; equal readings stay tied, including ties with topic."""
        return tuple(tuple(f for f, v in zip(FACETS, self.readings) if v == level)
                     for level in sorted(set(self.readings), reverse=True))


@dataclass(frozen=True)
class QueryContent:
    question: str
    description: str
    tags: tuple[QueryTag, ...]
    query_tags: tuple[QueryTag, ...] = ()


def request(question):
    if not isinstance(question, str) or not question.strip():
        raise ValueError('A nonempty original question is required')
    return SYSTEM, 'Question: ' + question


def _tag_list(rows, label):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f'At least one {label} is required')
    tags, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'t', 'facets'}:
            raise ValueError('Expected tag and facet readings only')
        name, readings = row['t'], row['facets']
        if not isinstance(name, str) or not name.strip() or name.casefold() in seen:
            raise ValueError('Empty or duplicate tag; do not silently drop it')
        if name != name.strip():
            raise ValueError('Tag has surrounding whitespace')
        if not isinstance(readings, dict) or set(readings) != set(FACETS):
            raise ValueError('Exactly the five relational facets are required')
        values = tuple(readings[f] for f in FACETS)
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
               for v in values):
            raise ValueError('Facet readings must be finite numbers in [0,1]')
        seen.add(name.casefold())
        tags.append(QueryTag(name, values))
    return tuple(tags)


def parse(question, raw):
    """description and tags always; query_tags when the answer carries them (answers
    written before the question-side list parse with none)."""
    request(question)
    if not isinstance(raw, dict) or set(raw) not in ({'description', 'tags'},
                                                     {'description', 'tags', 'query_tags'}):
        raise ValueError('Expected description, tags and query_tags only')
    description = raw['description']
    if not isinstance(description, str) or not description.strip():
        raise ValueError('A sought-content description is required')
    tags = _tag_list(raw['tags'], 'semantic tag')
    query_tags = _tag_list(raw['query_tags'], 'question tag') if 'query_tags' in raw else ()
    return QueryContent(question, description, tags, query_tags)
