"""A corpus record written as text: what lucene and vector index, embed and hand to the generator.

The forms are the benchmark authors' own, SalesforceAIResearch/HERB at commit db3bf9b3:
`code/react.py` (MyRAG._setup_data_loaders) for the four kinds its retrieval index holds
(slack, documents, meeting transcripts, meeting chats), and `code/oracle_eval.py` for the two it
does not hold (urls, prs). Two fields the authors' forms do not write are added, because the
baselines' text held them before: a document's `feedback` after its content, and a meeting
transcript's `document_type` on the line before the transcript, where the authors put a
document's `type`. A field a form reads is taken by its key, so a record without it raises.
"""
from __future__ import annotations

import hashlib

ARTIFACT_TYPES = (
    "slack",
    "documents",
    "meeting_transcripts",
    "meeting_chats",
    "urls",
    "prs",
)

FORM = ("SalesforceAIResearch/HERB db3bf9b3: code/react.py for slack, documents, "
        "meeting_transcripts, meeting_chats; code/oracle_eval.py for urls, prs; added: "
        "documents.feedback after the content, meeting_transcripts.document_type before the "
        "transcript")


def record_text(kind: str, rec: dict) -> str:
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


def units_digest(ids, texts) -> str:
    """sha256 over the units in index order. Per unit: the id, then the text, each as UTF-8
    behind its byte length written as 8 bytes, big end first."""
    h = hashlib.sha256()
    for uid, text in zip(ids, texts):
        for part in (str(uid).encode("utf-8"), text.encode("utf-8")):
            h.update(len(part).to_bytes(8, "big"))
            h.update(part)
    return h.hexdigest()
