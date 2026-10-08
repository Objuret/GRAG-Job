# What a baseline unit's text holds (2026-10-09)

His words: *"yes, they get those fields!"* (2026-10-09), said to: "The baselines' text gets those
fields, written the way the benchmark's own code writes a record. The vector corpus is then
embedded again on the desktop, and both baselines are new."

A unit is one record of the corpus, as before: 38,540 units, the same ids. The unit's text is
what lucene indexes, what vector embeds, and what both hand to the generator inside the
72,000 characters.

## Before

Lucene and vector each built their own text, from part of the record.

| Record | n | In the text | Left out |
|---|---|---|---|
| Slack message | 33,632 | channel name, writer's id, text | time, ids |
| PR | 3,562 | title, summary, review comments | author, reviewers, review state and time, state, mergeable, merged, created at, link, number, id |
| URL | 575 | description, link | id |
| Document | 400 | type, content, feedback | author, date, link, id |
| Meeting transcript | 321 | type, transcript | participants, date, id |
| Meeting chat | 50 | text | id |

The two texts were not the same text: lucene joined a title and the contents, and for a URL both
held the description, so lucene's URL units carried it twice.

## Now

One function, `prod/harness/record_text.py` · `record_text`, builds the text for both arms. The
forms are the benchmark authors' own, from their repository `SalesforceAIResearch/HERB` at commit
`db3bf9b3f911745726c579c9dbf9f7f6b2c05b36` (the copy read was checked blob by blob against that
commit's tree):

- `code/react.py`, `MyRAG._setup_data_loaders`, the documents of the authors' own retrieval
  index: Slack messages, documents, meeting transcripts, meeting chats.
- `code/oracle_eval.py`, the authors' oracle setting: URLs and PRs. The authors' own retrieval
  index holds no URL and no PR record; these baselines hold them, as they did before.

| Record | The text |
|---|---|
| Slack message | `Message ID: <id>`, `Channel Name: <name>`, `Timestamp: <time>`, a blank line, `<writer's id>: <text>` |
| Document | `Doc ID: <id>`, `Link: <link>`, `<date>`, `Author: <author>`, a blank line, `<type>`, `<content>`, then `<feedback>` when the record has one |
| Meeting transcript | `Meeting ID: <id>`, `<date>`, `Participants: <list>`, a blank line, `<type>`, `<transcript>` |
| Meeting chat | `Meeting ID: <id>`, a blank line, `Chats:`, `<text>` |
| URL | `URL: <link>`, a blank line, `Description: <description>` |
| PR | `Title:`, `Author:`, `Created At:`, `State:`, `Mergeable:`, `Merged:`, `Link:`, `Summary:`, a blank line, `Reviews:`, then one line per review: `- <state> by <reviewer> at <time>: <comment>` |

Two things here are not the authors' form and are this build's own choice. Both keep something
the baselines' text already held, which the authors' forms do not write:

- a document's `feedback` (200 of the 400 documents have one) follows its content;
- a meeting transcript's `document_type` stands on the line before the transcript, where the
  authors put a document's `type`.

Fields that neither of the authors' forms writes stay out: a Slack message's channel id,
reactions and thread replies, and a PR's number.

Every field a form reads is present, as a string (the participants and the reviews as lists), on
every record of its kind in the corpus the runs read; counted over all 38,540. The one optional
field is `feedback`. A record without a field its form reads is refused.

The record's id now stands in the text, so it is indexed, embedded and counted in the 72,000
characters. The ids a run reports for a delivered unit (`context_ids`) come from the unit, as
before, not from the text.

## What changed, counted

`output/research/2026-10-09-baseline-unit-text/prep_units.print.txt`; "before" is vector's text
as stored with its vectors of 2026-10-07.

| Record | n | Characters per unit, median before → after | Total characters before → after |
|---|---|---|---|
| Slack message | 33,632 | 194 → 262 | 6,931,269 → 9,221,516 (×1.33) |
| PR | 3,562 | 162 → 391 | 1,312,949 → 2,181,977 (×1.66) |
| URL | 575 | 114 → 133 | 67,439 → 78,364 (×1.16) |
| Document | 400 | 4,654 → 4,836 | 1,943,308 → 2,014,838 (×1.04) |
| Meeting transcript | 321 | 2,895 → 3,426 | 977,076 → 1,142,756 (×1.17) |
| Meeting chat | 50 | 115 → 160 | 5,880 → 8,070 (×1.37) |
| All | 38,540 | mean 292 → 380 | 11,237,921 → 14,647,521 (×1.30) |

- At the mean unit length 72,000 characters hold 246 units before and 189 now.
- Units whose text equals an earlier unit's text: 354 before, none now.
- The embedder's longest input is 8,192 tokens; no unit is over it (the longest is 1,540).
- Lucene's and vector's units are the same ids with the same text, in the same order.

## In a run's record

The manifest's `index` entry of both arms holds `unit_text` (the form and the commit it is taken
from) and `units_sha256`: sha256 over the units in index order, per unit the id and then the
text, each as UTF-8 behind its byte length written as 8 bytes, big end first. For the corpus the
runs read it is `af778f9dc9fbf1519ebb6a8b252351d5b6647a1c12112c23e7ab4924c28c1ef1`.

Lucene's `index` entry also names its BM25 parameters and where they come from: k1 0.9 and b 0.4
are Anserini's defaults (Lucene's own are 1.2 and 0.75, bm25s's 1.5 and 0.75).
