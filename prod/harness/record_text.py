"""A corpus record written as text: what lucene and vector index, embed and hand to the generator.

The forms are the benchmark authors' own, SalesforceAIResearch/HERB at commit db3bf9b3:
`code/react.py` (MyRAG._setup_data_loaders) for the four kinds its retrieval index holds
(slack, documents, meeting transcripts, meeting chats), and `code/oracle_eval.py` for the two it
does not hold (urls, prs). Two fields the authors' forms do not write are added, because the
baselines' text held them before: a document's `feedback` after its content, and a meeting
transcript's `document_type` on the line before the transcript, where the authors put a
document's `type`. A field a form reads is taken by its key, so a record without it raises.

The employees and customers of the two metadata files that HERB counts among its 39,190
artifacts (one record per entry) have no form in the authors' code, which reads them only as
lookup tables: every field of the record, one `key: value` line each in the file's own keys and
order, under a line naming the file (`employee directory`, `customers_data directory`).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

ARTIFACT_TYPES = (
    "slack",
    "documents",
    "meeting_transcripts",
    "meeting_chats",
    "urls",
    "prs",
)

# The metadata files, by kind; the kind is the file's name. salesforce_team.json is not used
# (his 2026-10-31 "yeah, so, dont fucking talk about or use it then").
METADATA_TYPES = {
    "employee": "metadata/employee.json",
    "customers_data": "metadata/customers_data.json",
}

FORM = ("SalesforceAIResearch/HERB db3bf9b3: code/react.py for slack, documents, "
        "meeting_transcripts, meeting_chats; code/oracle_eval.py for urls, prs; added: "
        "documents.feedback after the content, meeting_transcripts.document_type before the "
        "transcript; employee, customers_data: every field as a 'key: value' line under "
        "'<file> directory'")


def metadata_records(corpus_root) -> list:
    """(kind, id, record) for every employee and customer, in the files' own order; the id is
    the record's own (`employee_id`, `id`)."""
    root = Path(corpus_root)
    employees = json.loads((root / METADATA_TYPES["employee"]).read_text(encoding="utf-8"))
    customers = json.loads((root / METADATA_TYPES["customers_data"]).read_text(encoding="utf-8"))
    return ([("employee", rec["employee_id"], rec) for rec in employees.values()]
            + [("customers_data", rec["id"], rec) for rec in customers])


def record_text(kind: str, rec: dict) -> str:
    if kind in METADATA_TYPES:
        return record_header(kind, rec) + record_content(kind, rec)
    if kind == "slack":
        msg = rec["Message"]["User"]
        return (f"Message ID: {msg['utterranceID']}\nChannel Name: {rec['Channel']['name']}\n"
                f"Timestamp: {msg['timestamp']}\n\n{msg['userId']}: {msg['text']}")
    if kind == "documents":
        text = (f"Doc ID: {rec['id']}\nLink: {rec['document_link']}\n{rec['date']}\n"
                f"Author: {rec['author']}\n\n{rec['type']}\n{rec['content']}")
        return f"{text}\n{rec['feedback']}" if rec.get("feedback") else text
    if kind == "meeting_transcripts":
        return (f"Meeting ID: {rec['id']}\n{rec['date']}\nParticipants: {rec['participants']}\n\n"
                f"{rec['document_type']}\n{rec['transcript']}")
    if kind == "meeting_chats":
        return f"Meeting ID: {rec['id']}\n\nChats:\n{rec['text']}"
    if kind == "urls":
        return f"URL: {rec['link']}\n\nDescription: {rec['description']}"
    if kind == "prs":
        text = (f"Title: {rec['title']}\nAuthor: {rec['user']['login']}\n"
                f"Created At: {rec['created_at']}\nState: {rec['state']}\n"
                f"Mergeable: {rec['mergeable']}\nMerged: {rec['merged']}\nLink: {rec['link']}\n"
                f"Summary: {rec['summary']}\n\nReviews:\n")
        for review in rec["reviews"]:
            text += (f"- {review['state']} by {review['user']['login']} at "
                     f"{review['submitted_at']}: {review['comment']}\n")
        return text
    raise KeyError(f"no text form for a record of kind {kind!r}")


# the field each kind's content starts with in record_text
CONTENT_START = {"slack": ("Message", "User", "text"), "documents": ("content",),
                 "meeting_transcripts": ("transcript",), "meeting_chats": ("text",),
                 "urls": ("description",), "prs": ("summary",)}


def record_content(kind: str, rec: dict) -> str:
    """A record's content, without its ids, labels, dates and names: the message, the document
    and its feedback, the transcript, the chat, the description, or the pull request's summary and
    review comments. An employee or a customer has no content apart from its fields: its content
    is its field lines."""
    if kind in METADATA_TYPES:
        return "\n".join(f"{key}: {value}" for key, value in rec.items())
    if kind == "slack":
        return rec["Message"]["User"]["text"]
    if kind == "documents":
        return f"{rec['content']}\n{rec['feedback']}" if rec.get("feedback") else rec["content"]
    if kind == "meeting_transcripts":
        return rec["transcript"]
    if kind == "meeting_chats":
        return rec["text"]
    if kind == "urls":
        return rec["description"]
    if kind == "prs":
        return "\n".join([rec["summary"]] + [review["comment"] for review in rec["reviews"]])
    raise KeyError(f"no content for a record of kind {kind!r}")


def record_header(kind: str, rec: dict) -> str:
    """The start of a record's record_text, before its content."""
    if kind in METADATA_TYPES:
        return f"{kind} directory\n"
    marked = copy.deepcopy(rec)
    *path, last = CONTENT_START[kind]
    holder = marked
    for key in path:
        holder = holder[key]
    holder[last] = "\x00"
    return record_text(kind, marked).split("\x00")[0]


def units_digest(ids, texts) -> str:
    """sha256 over the units in index order. Per unit: the id, then the text, each as UTF-8
    behind its byte length written as 8 bytes, big end first."""
    h = hashlib.sha256()
    for uid, text in zip(ids, texts):
        for part in (str(uid).encode("utf-8"), text.encode("utf-8")):
            h.update(len(part).to_bytes(8, "big"))
            h.update(part)
    return h.hexdigest()
