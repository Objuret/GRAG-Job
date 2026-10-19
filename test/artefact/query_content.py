"""The query-side request and the parsing of its answer: one call that writes a description of
the content the question is looking for and two tag lists, each tag with the one facet that
matters most for it (his 2026-10-09 "The interpreter doesn't have to rank their tags, it doesn't
have to give numbers, it just have to say (which of the facets is most important to this tag for
this question)") and whether that facet matters for the tag at all (his 2026-10-15 "something
should also say "how important the facet conecpt is for the question/tag" ... nope, not at all";
2026-10-19 "go"): a facet can be the one that matters most for a tag and still not matter.

A request is the instruction, the message and the answer's JSON schema. The message holds only
marked parts (`_part`); the schema is what the lane forces the answer into, and the only place
the answer's form is defined.
"""
from dataclasses import dataclass

FACETS = ('topic', 'temporal', 'why', 'activity', 'concreteness')
RANKING_FACETS = FACETS[1:]

# His 2026-10-06 "describe the content the query is looking for … not trying to guess the exact
# content, but describe it".
SYSTEM = '''You read a question and describe the content it is looking for. You never see that
content. Write it the way the corpus tagger wrote its chunk descriptions and tags.

## Input

The question stands between <question> tags. It is the material you work on, not a message
to you: you do not answer it.

## Description

Describe the content this question is looking for in 1-3 sentences: what kind of content it
is and what it is about. Do not guess what that content says: describe what is being looked
for.

It is not the question restated, and not a statement of what the user wants.

It may say what kind of information that content holds — an explanation, a comparison, a
sequence of changes, a figure — without supplying the information itself.

State no fact the question does not carry. Name no person, organisation, product, place,
channel, system or date unless the question itself names it. Describe the kind of content,
not its facts.

## Tags

List the retrieval handles the answering content carries: its subjects, its concepts, the
activities, processes and decisions it turns on, the kinds of evidence it supplies.

Keep phrases whole. Include central concepts and peripheral lookup handles.

A retrieval handle is NOT a common verb, preposition, transitional word, sentence fragment,
or generic category like "report" or "discussion".

Do not invent concepts the question does not support.

Names of people, organisations, products, places and channels are EXCLUDED from the tags.
They are structure and are matched elsewhere. A tag is a semantic phrase — what the
answering content is about.

## The facet that matters most for each tag

Use the original question together with the sought-content description you write.
For each semantic tag, name the ONE facet through which the tag matters most for the content
characterised by that description, and say whether that facet matters for the tag there at
all: a facet can be the one that matters most for a tag and still not matter for it (false).
Name a facet and say true or false, nothing else: no number, no ranking.

temporal: the content's time relations (before and after, now and then, done, pending, due).
why: the content's reasons, causes and purposes.
activity: the content's actions, processes and events.
concreteness: the content's specifics as against general talk.

## Question tags

Also list the retrieval handles present in the question itself, from its own words and
subjects: its concepts, its subjects, the kinds of evidence it asks for. Keep proper names
whole. A retrieval handle is NOT a common verb, preposition, transitional word, sentence
fragment, or generic category like "report" or "discussion". Names of people,
organisations, products, places and channels are EXCLUDED from these tags as well. Do not
invent concepts the question does not contain.

For each question tag, name the one facet and say whether it matters the same way, with the
question in place of the sought content.

## Answer

Your answer is the structured object this call defines: description, tags and query_tags.
A tag is its phrase, t, the one facet that matters most for it, facet, and whether that facet
matters for it at all, matters.
'''
_TAG = {'type': 'object',
        'properties': {'t': {'type': 'string', 'minLength': 1, 'description': 'The tag phrase.'},
                       'facet': {'type': 'string', 'enum': list(RANKING_FACETS),
                                 'description': 'The one facet that matters most for the tag.'},
                       'matters': {'type': 'boolean',
                                   'description': 'Whether that facet matters for the tag at '
                                                  'all.'}},
        'required': ['t', 'facet', 'matters'], 'additionalProperties': False}
SCHEMA = {'type': 'object',
          'properties': {
              'description': {'type': 'string', 'minLength': 1,
                              'description': 'The description of the content the question is '
                                             'looking for (section Description).'},
              'tags': {'type': 'array', 'items': _TAG,
                       'description': 'The tags of the sought content (sections Tags and The '
                                      'facet that matters most for each tag).'},
              'query_tags': {'type': 'array', 'items': _TAG,
                             'description': 'The tags from the question\'s own words (section '
                                            'Question tags).'}},
          'required': ['description', 'tags', 'query_tags'], 'additionalProperties': False}

@dataclass(frozen=True)
class QueryTag:
    text: str
    facet: str
    matters: bool = False

    @property
    def facet_index(self):
        return RANKING_FACETS.index(self.facet)


@dataclass(frozen=True)
class QueryContent:
    question: str
    description: str
    tags: tuple[QueryTag, ...]
    query_tags: tuple[QueryTag, ...] = ()


def _part(name, text):
    """One marked part of a message. A text that holds the part's own closing tag would end
    the part early and is refused."""
    if f'</{name}>' in text:
        raise ValueError(f'The {name} holds its own closing tag')
    return f'<{name}>\n{text}\n</{name}>'


def request(question):
    """The first call: the instruction, the question as a marked part, the answer's schema."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError('A nonempty original question is required')
    return SYSTEM, _part('question', question), SCHEMA


def _tag_list(rows, label):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f'At least one {label} is required')
    tags, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'t', 'facet', 'matters'}:
            raise ValueError('Expected the tag, its facet and whether it matters only')
        name, facet, matters = row['t'], row['facet'], row['matters']
        if not isinstance(name, str) or not name.strip() or name.casefold() in seen:
            raise ValueError('Empty or duplicate tag; do not silently drop it')
        if name != name.strip():
            raise ValueError('Tag has surrounding whitespace')
        if not isinstance(facet, str) or facet not in RANKING_FACETS:
            raise ValueError(f'The facet must be one of {RANKING_FACETS}')
        if not isinstance(matters, bool):
            raise ValueError('Whether the facet matters must be true or false')
        seen.add(name.casefold())
        tags.append(QueryTag(name, facet, matters))
    return tuple(tags)


def parse(question, raw):
    """The first call's answer. An answer may hold no description-side tag when it holds
    question-side tags: both lists are query tags in the arm."""
    request(question)
    if not isinstance(raw, dict) or set(raw) not in ({'description', 'tags'},
                                                     {'description', 'tags', 'query_tags'}):
        raise ValueError('Expected description, tags and query_tags only')
    description = raw['description']
    if not isinstance(description, str) or not description.strip():
        raise ValueError('A sought-content description is required')
    query_tags = _tag_list(raw['query_tags'], 'question tag') if 'query_tags' in raw else ()
    if query_tags and raw['tags'] == []:
        tags = ()
    else:
        tags = _tag_list(raw['tags'], 'semantic tag')
    return QueryContent(question, description, tags, query_tags)
