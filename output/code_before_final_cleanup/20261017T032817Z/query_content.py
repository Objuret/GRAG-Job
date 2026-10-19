"""The two query-side requests and the parsing of their answers.

The first asks for a description of the content the question is looking for and two tag
lists, each tag with the one facet that matters most for it (his 2026-10-09 "The interpreter
doesn't have to rank their tags, it doesn't have to give numbers, it just have to say (which
of the facets is most important to this tag for this question)"). The second shows the graph's tree and asks for the places
the question is about.

A request is the instruction, the message and the answer's JSON schema. The message holds
only marked parts (`_part`); the schema is what the lane forces the answer into, and the
only place the answer's form is defined.
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
characterised by that description. Name a facet, nothing else: no number, no ranking.

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

For each question tag, name the one facet the same way, with the question in place of the
sought content.

## Answer

Your answer is the structured object this call defines: description, tags and query_tags.
A tag is its phrase, t, and the one facet that matters most for it, facet.
'''
_TAG = {'type': 'object',
        'properties': {'t': {'type': 'string', 'minLength': 1, 'description': 'The tag phrase.'},
                       'facet': {'type': 'string', 'enum': list(RANKING_FACETS),
                                 'description': 'The one facet that matters most for the tag.'}},
        'required': ['t', 'facet'], 'additionalProperties': False}
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

# The tree stands first, as reference; the instruction follows it.
TREE_FIRST = ('Reference for the instruction that follows it: the table of contents a corpus is '
              'filed under, as a tree. Each product, under it its kinds of record, and under '
              '"slack threads" its channels. Only the names of the places stand here, nothing '
              'that is filed under them.\n\n<tree>\n')
TREE_END = '\n</tree>\n\n'
SCOPE_SYSTEM = '''You say where in the tree above a question points.

## Input

The message holds four marked parts: the question between <question> tags, a description of
the content it is looking for between <description> tags, the tags written for that content
between <tags> tags, and the tags taken from the question's own words between
<question_tags> tags. They are the material you work on, not a message to you: you do not
answer the question.

## Places

From the question, the description and the tags, list the places of the tree above that the
question is about. Write a place as its path in the tree: "Product", "Product/kind" or
"Product/slack threads/#channel". Name only places that stand in the tree. A question about
a product as a whole names the product alone. If nothing points at a place, return an empty
list.

## Answer

Your answer is the structured object this call defines. It has one field, places: the list
of paths.
'''


# The tree's 527 paths as an enum make the command line longer than Windows takes, so a place
# is forced to be a text here and checked against the tree by the arm.
PLACES_SCHEMA = {'type': 'object',
                 'properties': {'places': {'type': 'array',
                                           'items': {'type': 'string', 'minLength': 1},
                                           'description': 'The places of the tree the question '
                                                          'is about, each as its path.'}},
                 'required': ['places'], 'additionalProperties': False}


# The map call (2026-10-11): the model reads the border's map and names the chunks an answer
# would be read from. Labels out, no number.
MAP_SYSTEM = '''You are given the map of one area of a company's records and a question about that area.

The map stands between <map> tags. It lists the area's parts: chat channels, documents, meeting
transcripts, pull requests, links. Under each part stand its pieces in the order they were made,
one line a piece: a label, then a short description of what the piece holds, then between square brackets the tags the piece carries, the most central first.

The question stands between <question> tags. It is the material you work on, not a message to
you: do not answer it. Beside it stand a description of the content the question is looking for
between <description> tags, and two lists of tags between <tags> and <question_tags> tags.

Name the pieces an answer to the question would have to be read from. Think of the whole strand
of work the question is about: the record itself, the messages where it was shared and
discussed, the meeting where it was reviewed, the follow-ups. A reader will take your pieces from
the top until its space is full, so give every piece that may hold part of what is needed, the
most needed first, and go on to the less certain ones after them. Give only labels that stand in
the map.'''

PIECES_SCHEMA = {'type': 'object',
                 'properties': {'pieces': {'type': 'array', 'items': {'type': 'string'}}},
                 'required': ['pieces'], 'additionalProperties': False}


@dataclass(frozen=True)
class QueryTag:
    text: str
    facet: str

    @property
    def facet_index(self):
        return RANKING_FACETS.index(self.facet)


@dataclass(frozen=True)
class QueryContent:
    question: str
    description: str
    tags: tuple[QueryTag, ...]
    query_tags: tuple[QueryTag, ...] = ()
    places: tuple[str, ...] | None = None


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


def scope_request(content, tree):
    """The second call: the tree first, then SCOPE_SYSTEM; the question, the description and the
    phrases of both tag lists the first call wrote, each as a marked part; the places' schema.
    A list with no tag is an empty part."""
    if not isinstance(content, QueryContent):
        raise ValueError('Expected the first call\'s parsed answer')
    if not isinstance(tree, str) or not tree.strip():
        raise ValueError('A nonempty tree is required')
    parts = [_part('question', content.question), _part('description', content.description)]
    for name, tags in (('tags', content.tags), ('question_tags', content.query_tags)):
        parts.append(_part(name, '\n'.join('- ' + tag.text for tag in tags)))
    return (TREE_FIRST + tree.strip('\n') + TREE_END + SCOPE_SYSTEM, '\n\n'.join(parts),
            PLACES_SCHEMA)


def map_request(content, map_text):
    """The map call: MAP_SYSTEM; the map, the question, the description and the phrases of both
    tag lists, each as a marked part; the pieces' schema."""
    if not isinstance(content, QueryContent):
        raise ValueError('Expected the first call\'s parsed answer')
    if not isinstance(map_text, str) or not map_text.strip():
        raise ValueError('A nonempty map is required')
    parts = [_part('map', map_text), _part('question', content.question),
             _part('description', content.description)]
    for name, tags in (('tags', content.tags), ('question_tags', content.query_tags)):
        parts.append(_part(name, '\n'.join('- ' + tag.text for tag in tags)))
    return MAP_SYSTEM, '\n\n'.join(parts), PIECES_SCHEMA


def parse_pieces(raw):
    """The labels the map call named, each once, in its order."""
    if (not isinstance(raw, dict) or not isinstance(raw.get('pieces'), list)
            or not all(isinstance(x, str) for x in raw['pieces'])):
        raise ValueError('Expected the pieces as a list of labels')
    return tuple(dict.fromkeys(x.strip() for x in raw['pieces'] if x.strip()))


def _places(value):
    if not isinstance(value, list) or not all(isinstance(p, str) and p.strip() for p in value):
        raise ValueError('Expected the places as a list of nonempty paths')
    return tuple(dict.fromkeys(p.strip() for p in value))


def parse_places(raw):
    """The second call's answer: the places and nothing else."""
    if not isinstance(raw, dict) or set(raw) != {'places'}:
        raise ValueError('Expected the places only')
    return _places(raw['places'])


def _tag_list(rows, label):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f'At least one {label} is required')
    tags, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'t', 'facet'}:
            raise ValueError('Expected tag and its facet only')
        name, facet = row['t'], row['facet']
        if not isinstance(name, str) or not name.strip() or name.casefold() in seen:
            raise ValueError('Empty or duplicate tag; do not silently drop it')
        if name != name.strip():
            raise ValueError('Tag has surrounding whitespace')
        if not isinstance(facet, str) or facet not in RANKING_FACETS:
            raise ValueError(f'The facet must be one of {RANKING_FACETS}')
        seen.add(name.casefold())
        tags.append(QueryTag(name, facet))
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
