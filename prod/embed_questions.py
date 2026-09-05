import numpy as np

from harness import questions
from harness.embed import EMBED_MODEL, QUERY_VECS_PATH, _embed


def main():
    qs = questions.load_questions()
    ids = [q.id for q in qs]
    texts = [q.question for q in qs]
    print(f"embed_questions: {len(ids)} questions -> {EMBED_MODEL}", flush=True)

    matrix, calls, tokens_in, tokens_out, secs = _embed(texts, "query")

    QUERY_VECS_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(QUERY_VECS_PATH, ids=np.array(ids, dtype=object), matrix=matrix)
    print(f"embedded {len(ids)} questions ({EMBED_MODEL}) -> {QUERY_VECS_PATH}")
    print(f"  {calls} forward pass(es), in={tokens_in} out={tokens_out} tokens, "
          f"{secs:.1f}s")


if __name__ == "__main__":
    main()
