"""A query tag's five facet readings from the facet instrument that scored the graph's edges,
not from the model (his 2026-10-08 "we DID build that neural net for judging the facets, why
the fuck is the model doing that work then?").

The round-1 instrument (`output/facet_pairs/rounds/round1/model`): the backbone
`Alibaba-NLP/gte-reranker-modernbert-base` reads a pair as one sequence, the phrase first and
the text second (`tokenizer(phrase, text)`, truncation only of the text), the pair's
representation is the attention-masked mean of the third-last hidden layer, standardised with
the saved mean and deviation, and the round-1 linear head gives the five scores (topic,
temporal, why, activity, concreteness). On the edges the pair was the tag and the chunk's text;
here it is the query tag and the query description (his 2026-09-14: the readings are the tag's
"relevance to the query-description"). The head's four non-topic scores are the readings on
those facets, on the edges' own scale; topic is the cosine of the query tag's vector and the
description's, both behind "query: ", as topic is on the edges. The head's own topic score is
kept in the record beside it and not used.

The head was fitted on tag–chunk pairs; a tag against a one-sentence description is a pair of
another kind, and what the head says there has not been checked against anything.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "output/facet_pairs/rounds/round1/model"
FACETS = ("topic", "temporal", "why", "activity", "concreteness")
VARIANT_LAYER = 3            # mean_L-3: the third-last hidden layer, attention-masked mean

_lock = threading.Lock()
_instrument = None


def _load():
    global _instrument
    with _lock:
        if _instrument is None:
            import torch
            from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
            cfg = json.loads((MODEL_DIR / "config.json").read_text(encoding="utf-8"))
            if cfg["variant"] != f"mean_L-{VARIANT_LAYER}" or cfg["head"] != "linear":
                raise RuntimeError(f"query_facets reads a linear head on mean_L-{VARIANT_LAYER}; "
                                   f"the round-1 model is {cfg['head']} on {cfg['variant']}")
            name, revision = cfg["backbone"], cfg["cache_meta"]["revision"]
            config = AutoConfig.from_pretrained(name, revision=revision, trust_remote_code=False)
            config.output_hidden_states = True
            config.reference_compile = False
            model = AutoModelForSequenceClassification.from_pretrained(
                name, revision=revision, config=config, attn_implementation="sdpa")
            model.float().eval()
            tok = AutoTokenizer.from_pretrained(name, revision=revision)
            z = np.load(MODEL_DIR / "standardisation.npz")
            state = torch.load(MODEL_DIR / "head.pt", map_location="cpu")
            weight, bias = state["net.weight"].numpy(), state["net.bias"].numpy()
            if weight.shape != (len(FACETS), z["mu"].shape[0]):
                raise RuntimeError("the head's shape does not fit the standardisation")
            _instrument = {"model": model, "tok": tok, "mu": z["mu"].astype(np.float32),
                           "sd": z["sd"].astype(np.float32), "weight": weight, "bias": bias,
                           "max_length": int(cfg["cache_meta"]["max_length"]),
                           "backbone": name, "revision": revision, "round": cfg["round"]}
    return _instrument


def head_scores(phrases: list, text: str) -> np.ndarray:
    """The round-1 head's five scores for every (phrase, text) pair, [phrases, 5] in FACETS
    order, computed as the edges' were: one joint sequence, mean of the third-last layer,
    standardised, the linear head."""
    import torch
    ins = _load()
    if not phrases:
        return np.zeros((0, len(FACETS)), dtype=np.float64)
    enc = ins["tok"]([str(p) for p in phrases], [text] * len(phrases), truncation="only_second",
                     max_length=ins["max_length"], padding=True, return_tensors="pt")
    with torch.no_grad():
        out = ins["model"](**enc)
    h = out.hidden_states[-VARIANT_LAYER]
    mask = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
    mean = ((h * mask).sum(1) / mask.sum(1).clamp(min=1e-6)).float().numpy()
    mean = mean.astype(np.float16).astype(np.float32)        # stored as the cache stored it
    x = (mean - ins["mu"]) / ins["sd"]
    return (x @ ins["weight"].T + ins["bias"]).astype(np.float64)


def readings(phrases: list, text: str, topic_cosines) -> tuple:
    """Per phrase the five readings: topic from `topic_cosines` (the phrase's vector against
    the description's), the other four from the head. Returns the readings [phrases, 5] and
    the record (the instrument and the head's own topic column)."""
    scores = head_scores(phrases, text)
    topic = np.asarray(topic_cosines, dtype=np.float64)
    if topic.shape != (len(phrases),):
        raise ValueError("Expected one topic cosine per phrase")
    out = scores.copy()
    out[:, 0] = topic
    ins = _load()
    return out, {"instrument": f"round {ins['round']} head on {ins['backbone']}@{ins['revision'][:12]}",
                 "pair": "query tag, query description", "topic": "cosine, both behind query:",
                 "head_topic": scores[:, 0].tolist()}
