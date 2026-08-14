"""embed_questions.py — precompute the dense (vector) arm's question vectors.

Run once for the question set, and again only if the embedder (EMBED_MODEL) changes:

    python embed_questions.py        # all questions -> data/question_query_vecs.npz

Embeds every question as input_type="query" in batched NIM calls and writes one
npz: aligned `ids` + L2-normalised `matrix`, keyed by the question id the vector
arm looks up at retrieval time. The arm itself never embeds a question.
linked to: pipelines.vector.load_query_vecs (the consumer)
"""
import numpy as np

import nim
import questions
from pipelines.vector import EMBED_MODEL, QUERY_VECS_PATH, _embed


def main():
    nim.require_key()  # fail loud before embedding — no silent offline mode
    qs = questions.load_questions()
    ids = [q.id for q in qs]
    texts = [q.question for q in qs]

    nim.reset_timing()
    matrix, calls, tokens_in, tokens_out, secs = _embed(texts, "query")
    transport = nim.take_timing()

    QUERY_VECS_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(QUERY_VECS_PATH, ids=np.array(ids, dtype=object), matrix=matrix)
    print(f"embedded {len(ids)} questions ({EMBED_MODEL}) -> {QUERY_VECS_PATH}")
    print(f"  {calls} request(s), in={tokens_in} out={tokens_out} tokens, {secs:.1f}s")
    print(f"  of that: {transport['request_s']:.1f}s in request, "
          f"{transport['wait_s']:.1f}s queued, {transport['retry_s']:.1f}s retrying "
          f"({transport['attempts']} attempts)")


if __name__ == "__main__":
    main()
