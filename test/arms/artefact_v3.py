"""artefact_v3 — the artefact arm under test.

A connection is a tag on a chunk (one per HAS_TAG edge). Per query part: fit = FIT_RULE over the
tag's cosine and the chunk description's cosine to the part.

HERB_V3_SORT=concept (the arm since 2026-09-11): his chain built link by link from his words;
every link, with the sentence it rests on, is in _retrieve_concept's docstring. No part of it
was chosen by a score.

HERB_V3_SORT=combo (09-11, chosen by ranking formulas on the smoke gold — kept for the record,
not a construction): one strength per chunk —
per part, the chunk's best tag cosine times that part's cosine to the chunk description, summed
over the parts and the raw question; banded; inside a band the five facets of the edge that
reached the chunk, in that part's facet order; then the description-to-description level; then
the strength. Scope first. Measured in-product against the same delivered depth (09-10):
midpoint fit 0.22, tag only 0.26, description only 0.33, this 0.45, plus a facet tiebreak 0.47.

HERB_V3_SORT=chain (the 09-10 first build): the query's description and the raw question
are embedded beside the parts. The band (HERB_V3_BAND=paraphrase) is how far rephrasing the same
need moves a chunk's cosine; fit is levelled at that band. Levels open nearest first across all
parts to the end of the region, and inside a level the key is: the part's centrality rank (cosine
to the description), the five facets in the part's order, the description-to-description link
level, the tag's cosine, chunk id. No sum, no count, no chosen width. HERB_V3_CHAIN_KEYS switches
part / facets / desc off for the on/off measurement.
HERB_V3_SORT=v3: the 09-07 walk — noise-width levels per part, facets then tag cosine inside a
level, parts merged round robin, no description link.

FACET_SOURCE = edge (the arm, 2026-09-13; THE ORCHESTRATOR'S CONSTRUCTION, not his ruling):
the four text statistics are read per EDGE, on the tag's own sentences inside the chunk, the
sentences located by nearness — his "NEARNESS, we cant fucking use explicit shit" (09-09) — and
only for the chunks of the question's region, at query time, cached on disk — his "embed the
entire corpus … is retarded" (09-09). The statistic stays the chunk's text statistic; what the
tag changes is which sentences it is read on ("the importance or weight of temporality in the
chunk, AND the tag's relevance to the chunk and that combo IS the tag's temporality", 09-08
13:02). Which sentences are the tag's, and how a set is aggregated, is in
test/graph/sentence_facets.py. Outside the region, and where the text does not resolve, the
edge keeps its chunk-level value from the statistics file — the stats source below.

FACET_SOURCE = stats (the arm 2026-09-09 to 09-13): the five are topic, temporal, why, activity,
concreteness, each a text statistic on the tag's sentences inside the chunk, read from the
file test/graph/facet_stats.py --overlay writes (never from the database, never from a model).
The interpreter names, per query part, the ORDER of the five and a weight per facet — how much
that facet matters for that part. The order is the sort priority; every column runs strongest
first, and the weight is carried in the plan and the traces without touching a key — where it
sits inside a column is open on his record (2026-09-13). Edges the statistics could not anchor
sort last in every column; on the four chunk-level statistics an edge takes its chunk's value
whenever any edge of that chunk is anchored.
FACET_SOURCE = file (2026-09-20): the five are the ruled five, read PER EDGE off the overlay
HERB_FACET_FILE names — the same JSON shape facet_stats.py --overlay writes, one row per
(tag, chunkId) with five weights. A null topic is the graph's cos(Tag.emb, Chunk.desc_emb), as
under stats. The four other columns are levelled per EDGE, never collapsed to one value per
chunk: the file carries a value per edge, and the values differ between the tags of one chunk.
A missing value (NaN) sorts last in its column; negative and zero are ordinary values.

FACET_SOURCE = weight | rank: the earlier editions (graph w_facets through FACET_KEY /
DIST_RULE, or a rank overlay), kept for the sweep.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.signal import argrelmin
from scipy.stats import gaussian_kde

from harness import chat
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from arms.artefact_v2 import (
    ALL_FACETS, DATABASE, DATASET_ID, FILLER, FRESH_INTERP, INTERP_CACHE_DIR, INTERPRET_MODEL,
    NEUTRAL_FACETS, NO_REVIEW, RAW_QUESTION, RUN_ID, _EXCLUDED_PARAM, _PASS1_SYSTEM,
    _budget_contexts, _chat_json, _clean_tag, _driver, _embed_cached, _interpret_cached,
    _parse_gate, _qid_text, _readable, _resolve_chunk, _sufficient_cut, _unit,
)

STAT_FACETS = ("topic", "temporal", "why", "activity", "concreteness")   # ruled 09-08 / 09-09
_ROOT = Path(__file__).resolve().parent.parent.parent
FACET_STATS = os.environ.get("HERB_FACET_STATS") or str(
    _ROOT / "output" / "facet_stats" / f"{DATABASE}.overlay.json")   # facet_stats.py --overlay
FACET_OVERLAY = os.environ.get("HERB_FACET_OVERLAY") or None   # reweight_facet_layer --out file
RANK_OVERLAY = os.environ.get("HERB_RANK_OVERLAY") or None     # order_facet_layer --out file
FACET_FILE = os.environ.get("HERB_FACET_FILE") or None   # FACET_SOURCE=file reads this overlay
FACET_SOURCE = os.environ.get("HERB_FACET_SOURCE") or (
    "rank" if RANK_OVERLAY else "weight" if FACET_OVERLAY else "edge")
                            # edge | stats | file | weight | rank
if FACET_SOURCE not in ("edge", "stats", "file", "weight", "rank"):
    raise ValueError(f"HERB_FACET_SOURCE is {FACET_SOURCE!r}; the sources are edge, stats, "
                     f"file, weight, rank")
if FACET_SOURCE == "file":
    if not FACET_FILE:
        raise ValueError("HERB_FACET_SOURCE=file reads a per-edge overlay; name it with "
                         "HERB_FACET_FILE=<path to the overlay json>")
    if not Path(FACET_FILE).is_file():
        raise ValueError(f"HERB_FACET_FILE {FACET_FILE} does not exist")
TEXT_SOURCES = ("edge", "stats", "file")   # the five ruled facets, read off a file
STATS_SOURCES = ("edge", "stats")  # the four columns are the 09-09 text statistics, per chunk


def active_facets() -> tuple:
    """the column layout of the five: the stats names under FACET_SOURCE=edge|stats, the
    graph's names otherwise. Read at call time so a source switched at runtime (tests, sweeps)
    is honoured."""
    return STAT_FACETS if FACET_SOURCE in TEXT_SOURCES else ALL_FACETS


FACETS = active_facets()   # the layout at import, for the flags; the sort reads active_facets()


def _file_sha(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _overlay_sha() -> Optional[str]:
    return _file_sha(FACET_OVERLAY)


RETRIEVAL_FLAGS = {
    "HERB_RAW_QUESTION": RAW_QUESTION,
    "facets": list(FACETS),
    "HERB_FACET_STATS": FACET_STATS if FACET_SOURCE in STATS_SOURCES else None,
    "facet_stats_sha256": _file_sha(FACET_STATS) if FACET_SOURCE in STATS_SOURCES and Path(FACET_STATS).is_file() else None,
    "sentence_facets_sha256": _file_sha(str(_ROOT / "test" / "graph" / "sentence_facets.py")) if FACET_SOURCE == "edge" else None,
    "HERB_FACET_FILE": FACET_FILE if FACET_SOURCE == "file" else None,
    "facet_file_sha256": _file_sha(FACET_FILE) if FACET_SOURCE == "file" else None,
    "HERB_FACET_OVERLAY": FACET_OVERLAY,
    "facet_overlay_sha256": _overlay_sha(),
    "HERB_RANK_OVERLAY": RANK_OVERLAY,
    "rank_overlay_sha256": _file_sha(RANK_OVERLAY),
    "HERB_FACET_SOURCE": FACET_SOURCE,
}

# knobs — the arm's values are the first of each; test/sweep_v3.py sets the others
FACET_KEY = "distance"      # distance — |edge weight − part weight|, nearest first; raw — edge
                            # weight, strongest first. Which is right is unruled.
DIST_RULE = "clump"         # clump | grid (floor(d / DIST_RANGE)) | none (every distinct value)
DIST_RANGE = 0.05           # grid only
WEIGHT_GRAIN = 0.001        # clump cell; not measured
LEVEL_RULE = "kde"          # column with no query weight: kde | none
KDE_BW = "silverman"
KDE_BW_FACTOR = 1.0
KDE_GRID = 2048
MIN_LEVELS = 1              # fit levels opened per part before the depth stop is consulted
SCOPE_RULE = "ahead"        # ahead (in-scope first) | cut | off. Hard cut vs soft is unruled.
FIT_RULE = "midpoint"       # midpoint (mean of the two cosines) | min | tag
COS_NOISE = 0.0020          # measured 2026-09-06: median cosine shift on re-embedding, 200 tags × 50 probes

# the sort, ruled 2026-09-10 ("i think i agree, enough to atleast build it first"):
#   concept (the arm since 2026-09-11): his chain built link by link from his words, see
#     _retrieve_concept. No design choice in it was made by a score.
#   combo (09-11, SELECTED ON GOLD — kept for the record, not a construction): every link on one chunk —
#     strength(chunk) = SUM over parts of [ best tag cosine for that part ] x [ that part's
#     cosine to the chunk description ]; the parts' evidence adds, the tag end and the
#     description end multiply ("the chunk descriptions and the tags are supposed to work
#     TOGETHER", 08-11). The strength is banded (BAND_RULE), and inside a band the five facets
#     of the edge that reached the chunk sort it, in the reaching part's facet order.
#   chain = the 09-10 first build (fit levels per part, part centrality first).
#   v3 = the 09-07 walk (round-robin merge, noise-width levels, no description link).
#   multirank / weighted (2026-09-21, his /goal "have a forum amongst the agents, build the
#     weightend and the multiranked"): the two forum modes, built to
#     output/research/2026-09-21-forum/SPEC.md as SPEC-v2.md supersedes it. Neither is the
#     arm's default. They share every step but one key: the pick is the tag side alone
#     (his 09-06 "thats how you PICK the tags"), the pool is one pick level of one part inside
#     one scope pass, every column is levelled by steps below the pool's best, and the mode key
#     is either the five facet levels in the part's order (multirank) or topic adjusted by the
#     part's weighted facet sum (weighted).
SORT_MODE = os.environ.get("HERB_V3_SORT") or "concept"
FORUM_MODES = ("multirank", "weighted")
if SORT_MODE not in ("concept", "combo", "chain", "v3") + FORUM_MODES:
    raise ValueError(f"HERB_V3_SORT is {SORT_MODE!r}; the sorts are concept, combo, chain, v3, "
                     f"multirank, weighted")
CHAIN_KEYS = tuple(k for k in ("part,facets,desc" if os.environ.get("HERB_V3_CHAIN_KEYS") is None
                               else os.environ["HERB_V3_CHAIN_KEYS"]).split(",") if k)
for _k in CHAIN_KEYS:
    if _k not in ("part", "facets", "desc"):
        raise ValueError(f"HERB_V3_CHAIN_KEYS names {_k!r}; the keys are part, facets, desc")
COMBO_KEYS = tuple(k for k in ("facets,desc2desc" if os.environ.get("HERB_V3_COMBO_KEYS") is None else os.environ["HERB_V3_COMBO_KEYS"]).split(",") if k)
for _k in COMBO_KEYS:
    if _k not in ("facets", "desc2desc"):
        raise ValueError(f"HERB_V3_COMBO_KEYS names {_k!r}; the keys are facets, desc2desc")
LINK2 = os.environ.get("HERB_V3_LINK2") or "and"
    # his 09-07 sentence gives two readings of link 2, both built, neither chosen by a score;
    # RULED 2026-09-11: AND ("AND yesAND"). adjust stays for the record, not a choice:
    # and    — "the matching chunks via desc should be an AND with the one from the tags":
    #          the connection's level is the worse of its tag steps and its description steps
    # adjust — "or the ones from the tags gets a math adjustment before the facetweights do
    #          their thing": the tag pick sets the level (his 09-06 "first you pick … the
    #          tags"), and inside it the description steps sort ahead of the facets
    # sum    — THE ORCHESTRATOR'S CONSTRUCTION, 2026-09-13, not his ruling; his "AND yesAND"
    #          names a conjunction, and this is the compensatory one: the connection's level
    #          is the tag steps PLUS the description steps, both sides counted in the same
    #          semiorder unit (band steps below their own best match), neither side vetoing
    #          the other, no weight and no chosen number. Measured beside it: inside one
    #          product the tag level is near constant, so max() reads as the description's
    #          steps alone — the veto. Literature: Salton, Fox & Wu 1983 (extended boolean
    #          p-norm, the strict Zadeh min losing to soft conjunctions); Fox & Shaw 1994
    #          (CombSUM against CombMIN); Lee 1997 (combining runs by sum).
    # product — THE ORCHESTRATOR'S CONSTRUCTION, 2026-09-13, not his ruling: the two ends
    #          multiply before anything is counted — cos(part, tag) x cos(part, chunk
    #          description) — so the connection's closeness is one number in one unit and no
    #          scale has to be reconciled (the product t-norm, Menger 1942 / Schweizer &
    #          Sklar 1961; combo's per-part strength, 09-11). The level is band_steps of that
    #          product over the part's edges. Measured beside it: adding the two sides' steps
    #          adds two scales (tag spread ~150 steps, description ~90 under the noise band),
    #          and buried gold sat at tag level 0 with its description 60 steps down.
    #          Literature as for sum: Salton, Fox & Wu 1983; Fox & Shaw 1994; Lee 1997.
    # strength — THE ORCHESTRATOR'S CONSTRUCTION, 2026-09-13, not his ruling: the connection
    #          is read on the CHUNK, not on one part and not on one edge. Its closeness is the
    #          sum over the parts (and the raw question under RAW_PART=on) of that part's
    #          best tag cosine to the chunk times that part's cosine to the chunk description,
    #          over the pass's edges (TAGSIDE respected), and its level is the band steps of
    #          that closeness. It stands against his 09-10 "a chunk beeing supported by more
    #          parts, does not mean it's a better fit": a COUNT of parts was measured (09-10)
    #          to carry nothing (0.419 against 0.449) and again 09-13 to separate buried gold
    #          from delivered non-gold not at all, while the SUM of the per-part closeness
    #          separated them most (share above the non-gold median 0.36, against 0.16 for
    #          the single best part). Whether a sum of closeness is "fit" where a count is not
    #          is his to rule. Literature: Fox & Shaw 1994, CombSUM over CombMAX/CombMIN.
if LINK2 not in ("and", "adjust", "sum", "product", "strength"):
    raise ValueError(f"HERB_V3_LINK2 is {LINK2!r}; the readings are and, adjust, sum, "
                     "product, strength")
TAGSIDE = os.environ.get("HERB_V3_TAGSIDE") or "all"
    # concept mode only. all — every edge of the pool is a candidate connection (today).
    # nonscope — THE ORCHESTRATOR'S CONSTRUCTION, 2026-09-13, not his ruling: an edge whose
    # tag name is a Product node's name is left out of the candidate edges, because the gate
    # already read the product (scope); the product-name tag is the same structure read a
    # second time as evidence. A chunk then enters on its best non-product edge, or by the
    # shape's hop.
if TAGSIDE not in ("all", "nonscope"):
    raise ValueError(f"HERB_V3_TAGSIDE is {TAGSIDE!r}; the sides are all, nonscope")
PARTCOMB = os.environ.get("HERB_V3_PARTCOMB") or "product"
    # concept mode only, LINK2=strength: how a part's two cosines to a chunk combine before
    # the parts are summed.
    # product — today's strength: best tag cosine x the part's cosine to the chunk
    #   description. The two ends multiply, so either end near zero zeroes the part.
    # sum     — THE ORCHESTRATOR'S CONSTRUCTION, 2026-09-13, not his ruling: best tag cosine
    #   PLUS the part's cosine to the chunk description. Both numbers are cosines of the same
    #   part against the same chunk, one unit, so they add without a weight and no factor can
    #   zero the other — CombSUM across the two sources against the product (Fox & Shaw 1994).
    #   Measured 09-13 beside it: under TAGSIDE=nonscope the product collapses questions whose
    #   chunks carry no strong non-product tag (ActionGenie::a::0 0.71 -> 0.00), because the
    #   tag factor floors at ~0; combo keeps the product-name tag and so keeps that floor.
    #   A chunk no edge of this pass reaches contributes nothing under either reading.
if PARTCOMB not in ("product", "sum"):
    raise ValueError(f"HERB_V3_PARTCOMB is {PARTCOMB!r}; the combinations are product, sum")
FACETADJ = os.environ.get("HERB_V3_FACETADJ") or "off"
    # concept mode only, LINK2=strength. HIS CONCEPT: "Of course they dont change with the
    # question, thats why we have the interpreter put a value on its tags in relation to the
    # query... So we can weight-adjust the facets based on that.." (2026-09-13); "the facet
    # weight in COMBINATION with the tag's chunk relevance weight would tell how relevant the
    # tag actually is in relation to the prompt" (06-27); "the query facetweight, and that is
    # the 'multiplier' (not actual multiplication, i cant remember what math we decided on as
    # weightadjustor here..)" (08-23).
    # Per part and per edge, rel is the weighted MEAN of that edge's five facet positions
    # (facet_relevance), the weights being that part's interpreter facet weights; a part that
    # names none — the raw question — reads the five equal. A mean, so rel stays in [0, 1] and
    # no part's weight magnitude moves the scale.
    # THE TWO JOINS ARE THE ORCHESTRATOR'S READINGS of "weight-adjust", 2026-09-13, neither
    # his ruling and neither chosen by a score; both measured:
    # off — the tag side of a part's closeness is the tag cosine alone (the arm to 09-13).
    # add — tag cosine + rel.
    # mul — tag cosine x rel.
if FACETADJ not in ("off", "add", "mul"):
    raise ValueError(f"HERB_V3_FACETADJ is {FACETADJ!r}; the joins are off, add, mul")
if FACETADJ != "off" and (SORT_MODE != "concept" or LINK2 != "strength"):
    raise ValueError(f"HERB_V3_FACETADJ is {FACETADJ!r}, which adjusts the tag side of the "
                     f"concept walk's strength; HERB_V3_SORT is {SORT_MODE!r} and "
                     f"HERB_V3_LINK2 is {LINK2!r}")
REGION = os.environ.get("HERB_V3_REGION") or "shape"
    # concept mode only. tags — the region is what the parts' tags reach (the walk to 09-12).
    # shape — the tags seed and the graph's shape grows the region: every chunk sharing a
    # [:channel] Channel node with a seed. The group node is a relation the graph holds
    # between the chunk and its file ("use the graph shape", 09-13), not a number.
    # shape+cooc — that growth and, beside it, the co-occurrence path: a chunk with a
    # chunk→tag→chunk path to a seed through a tag that is not a product name. Off by
    # default: any threshold on that path is a chosen number, his to rule.
if REGION not in ("tags", "shape", "shape+cooc"):
    raise ValueError(f"HERB_V3_REGION is {REGION!r}; the regions are tags, shape, shape+cooc")
TAGREL = os.environ.get("HERB_V3_TAGREL") or "shape"
    # concept mode only, facets 2-5: which half of the AND stands for "the tag's relevance to
    # the chunk" (09-08 13:02). topic — cos(tag, chunk description), the topic facet again
    # (kept for the on/off measurement). shape — the tag's concentration around the chunk in
    # the graph (tag_concentration; the orchestrator's construction, 09-13, not his ruling).
    # shape acts only where the four columns are per edge: inside a FACET_SOURCE=edge region,
    # or over the pass-1 edges under FACET_SOURCE=file. Everywhere else the AND is with topic.
if TAGREL not in ("topic", "shape"):
    raise ValueError(f"HERB_V3_TAGREL is {TAGREL!r}; the halves are topic, shape")
LOCALITY = os.environ.get("HERB_V3_LOCALITY") or "on"
    # concept mode only. THE ORCHESTRATOR'S CONSTRUCTION, 2026-09-13, not his ruling: among
    # the chunks the description band calls equal, the ones the graph holds near the part's
    # seeds come first. Locality is the distance in hops to the nearest seed of the part:
    # 1 file-adjacent to a seed, 2 sharing a [:channel] group of the same product with one,
    # 3 neither; a seed beside another seed is 0. No count, no sum.
if LOCALITY not in ("off", "on"):
    raise ValueError(f"HERB_V3_LOCALITY is {LOCALITY!r}; the settings are off, on")
BAND_RULE = os.environ.get("HERB_V3_BAND") or "paraphrase"
if BAND_RULE not in ("paraphrase", "noise"):
    raise ValueError(f"HERB_V3_BAND is {BAND_RULE!r}; the bands are paraphrase, noise")
                            # paraphrase: per question, the median over chunks of
                            #   |cos(chunk desc, query description) − cos(chunk desc, raw question)|
                            #   — how far rephrasing the same need moves the number (a semiorder
                            #   threshold with a basis; Tversky 1969). noise: COS_NOISE.
RAW_PART = os.environ.get("HERB_V3_RAW_PART") or "off"
    # concept mode only. THE ORCHESTRATOR'S CONSTRUCTION, 2026-09-13, not his ruling.
    # off — the raw question is the band's instrument only, not a part (the concept walk to
    # 09-12). on — the raw question is appended as one more part of the plan: its own tag
    # levels and description steps, its facet order the key order with no weights, its rank
    # among the parts read by cos to the query description like any other part, as
    # _retrieve_combo reads it. The bands are unchanged.
if RAW_PART not in ("off", "on"):
    raise ValueError(f"HERB_V3_RAW_PART is {RAW_PART!r}; the settings are off, on")
SCOPE_FIELDS = os.environ.get("HERB_V3_SCOPE_FIELDS") or "all"
if SCOPE_FIELDS not in ("all", "product"):
    raise ValueError(f"HERB_V3_SCOPE_FIELDS is {SCOPE_FIELDS!r}; the fields are all, product")
                            # which fields of the gate the scope gate reads. all — product,
                            # section and years as they are named (today). product — THE
                            # ORCHESTRATOR'S CONSTRUCTION, 2026-09-13, not his ruling: only
                            # the named product gates; section and years are dropped from the
                            # gate. Measured 09-13: the gold sits in the named product on
                            # 100 of 100 gold100 questions and in the named section on 95 of
                            # 321 gold chunks. Under product the join knob is moot.
SCOPE_JOIN = os.environ.get("HERB_V3_SCOPE_JOIN") or "and"
if SCOPE_JOIN not in ("and", "or"):
    raise ValueError(f"HERB_V3_SCOPE_JOIN is {SCOPE_JOIN!r}; the joins are and, or")
                            # concept mode only: how the fields the gate names are joined
                            # when the scope is read — and: a chunk must answer every named
                            # field; or: any one of them.
# ---------------- the forum modes' own knobs (multirank / weighted, 2026-09-21)
TOPIC_KEY = os.environ.get("HERB_V3_TOPIC_KEY") or "ordered"
    # multirank only. ordered — topic sits where the part's cached order puts it (the default;
    # SPEC-v2 §2). first — topic is forced to the front of the key. Recorded: 27 of the 44
    # 10smoke parts are topic-first in the cached order, so the knob can differ on 17 parts.
if TOPIC_KEY not in ("ordered", "first"):
    raise ValueError(f"HERB_V3_TOPIC_KEY is {TOPIC_KEY!r}; the places are ordered, first")
TOPIC_BAND = os.environ.get("HERB_V3_TOPIC_BAND") or "write"
    # both forum modes. write — 0.028, the median |dcos| between two independent writes of a
    # chunk description (18,209 units, measured 09-18). noise — COS_NOISE 0.0020, the
    # embedder's own measured resolution (09-06). inf — no topic band at all: the mode key
    # vanishes and the reference run reads pick -> description (SPEC-v2 §7 M0 / W0).
if TOPIC_BAND not in ("write", "noise", "inf"):
    raise ValueError(f"HERB_V3_TOPIC_BAND is {TOPIC_BAND!r}; the bands are write, noise, inf")
TOPIC_WRITE_BAND = 0.028
FACET_BAND_RULE = os.environ.get("HERB_V3_FACET_BAND") or "flip"
    # both forum modes, the four head columns. flip — the pooled retrain band, flip_gap at
    # rate 0.05 on grid 0.01 over the fixed-seed same-chunk pair sample of the stored
    # bootstrap score matrices (SPEC-v2 S6). inf — the four columns vanish (SPEC-v2 §7 M0).
if FACET_BAND_RULE not in ("flip", "inf"):
    raise ValueError(f"HERB_V3_FACET_BAND is {FACET_BAND_RULE!r}; the rules are flip, inf")
DESC_PLACE = os.environ.get("HERB_V3_DESC_PLACE") or "after"
    # both forum modes. after — the key order of SPEC-v2's "Full key": part rank, mode key,
    # link 2, link 6, -tag cosine, chunk id (his chain). before — links 2 and 6 move ahead of
    # the mode key, so the facets order what the description calls equal.
if DESC_PLACE not in ("after", "before"):
    raise ValueError(f"HERB_V3_DESC_PLACE is {DESC_PLACE!r}; the places are after, before")
W_RULE = os.environ.get("HERB_V3_W") or "cached"
    # weighted only. cached — the part's cached facet weights for the four (the order
    # interpreter's, NOT his 09-14 per-tag object); equal — 1.0 each; roc — the rank-order
    # centroid of the part's facet order over the four (Barron & Barrett 1996); zero — all
    # four at 0.0, the reference run with no facet in the key (SPEC-v2 §7 W0 / W0t; the value
    # is the orchestrator's, the spec names the run but not a knob value for it).
if W_RULE not in ("cached", "equal", "roc", "zero"):
    raise ValueError(f"HERB_V3_W is {W_RULE!r}; the weightings are cached, equal, roc, zero")
BETA_RULE = os.environ.get("HERB_V3_BETA") or "off"
    # weighted only. off (the default, SPEC-v2 §3) — every column enters at 1.0. on — the four
    # held-out calibration slopes temporal 0.722, why 0.679, activity 0.845, concreteness
    # 0.603.
if BETA_RULE not in ("off", "on"):
    raise ValueError(f"HERB_V3_BETA is {BETA_RULE!r}; the settings are off, on")
BETA = {"temporal": 0.722, "why": 0.679, "activity": 0.845, "concreteness": 0.603}
ADJUST = os.environ.get("HERB_V3_ADJUST") or "bounded"
    # weighted only. bounded (the default) — r = topic cosine + the topic band times g's place
    # in the pool's g range, levelled at COS_NOISE: the facets adjust topic and can move an
    # edge by at most topic's own band. level — the mode key is (topic level, g level), so the
    # facets only order what topic calls equal.
if ADJUST not in ("bounded", "level"):
    raise ValueError(f"HERB_V3_ADJUST is {ADJUST!r}; the adjusts are bounded, level")
BOOTSTRAP_NPZ = os.environ.get("HERB_V3_BOOTSTRAP") or str(
    _ROOT / "output" / "facet_pairs" / "rounds" / "round1" / "bootstrap" / "scores_b24.npz")
BAND_PAIR_SAMPLE = int(os.environ.get("HERB_V3_BAND_PAIRS") or 200000)
BAND_PAIR_SEED = 20260922        # bootstrap_scores.SEED_SAME_CHUNK, so the band this arm
                                 # computes reproduces the number in that run's BANDS.md
BAND_FLIP_RATE = 0.05
BAND_FLIP_GRID = 0.01

if SORT_MODE in FORUM_MODES:
    if FACET_SOURCE != "file":
        raise ValueError(f"HERB_V3_SORT={SORT_MODE} reads the five values per edge off an "
                         f"overlay; set HERB_FACET_SOURCE=file and HERB_FACET_FILE "
                         f"(HERB_FACET_SOURCE is {FACET_SOURCE!r})")
    # knobs these modes do not support: a value the spec does not give them raises rather than
    # running another walk silently (SPEC-v2 S4)
    for _name, _allowed in (("HERB_V3_LINK2", ("and",)), ("HERB_V3_PARTCOMB", ("product",)),
                            ("HERB_V3_FACETADJ", ("off",)), ("HERB_V3_RAW_PART", ("off",)),
                            ("HERB_V3_REGION", ("tags",)), ("HERB_V3_LOCALITY", ("off",)),
                            ("HERB_V3_TAGREL", ()), ("HERB_V3_CHAIN_KEYS", ()),
                            ("HERB_V3_COMBO_KEYS", ()), ("HERB_V3_TAGSIDE", ("nonscope",)),
                            # "product" allowed since 2026-09-21: measured on the old walk,
                            # fields=all with the AND join sinks the three section-named
                            # 10smoke questions (0.71/0.44/0.58 -> 0.18/0.07/0.08); the
                            # default stays "all" (the arm's), his to rule
                            ("HERB_V3_SCOPE_FIELDS", ("all", "product")),
                            ("HERB_V3_SCOPE_JOIN", ("and",))):
        _raw = os.environ.get(_name)
        if _raw is not None and _raw not in _allowed:
            raise ValueError(
                f"HERB_V3_SORT={SORT_MODE} does not read {_name}; it is "
                f"{_raw!r} and these modes support "
                + (", ".join(_allowed) if _allowed else "no value of it"))
    REGION = "tags"          # no growth (SPEC-v2 S4)
    LOCALITY = "off"
    TAGSIDE = "nonscope"     # the 45 product-name tags are structure, not candidates (09-14)
    RETRIEVAL_FLAGS.update({
        "HERB_V3_TOPIC_KEY": TOPIC_KEY, "HERB_V3_TOPIC_BAND": TOPIC_BAND,
        "HERB_V3_FACET_BAND": FACET_BAND_RULE, "HERB_V3_DESC_PLACE": DESC_PLACE,
        "HERB_V3_W": W_RULE, "HERB_V3_BETA": BETA_RULE, "HERB_V3_ADJUST": ADJUST,
        "HERB_V3_BOOTSTRAP": BOOTSTRAP_NPZ,
        "bootstrap_sha256": _file_sha(BOOTSTRAP_NPZ) if Path(BOOTSTRAP_NPZ).is_file() else None,
    })

RETRIEVAL_FLAGS.update({"HERB_V3_SORT": SORT_MODE, "HERB_V3_CHAIN_KEYS": list(CHAIN_KEYS),
                        "HERB_V3_COMBO_KEYS": list(COMBO_KEYS), "HERB_V3_BAND": BAND_RULE,
                        "HERB_V3_LINK2": LINK2, "HERB_V3_REGION": REGION,
                        "HERB_V3_TAGREL": TAGREL, "HERB_V3_LOCALITY": LOCALITY,
                        "HERB_V3_SCOPE_JOIN": SCOPE_JOIN, "HERB_V3_SCOPE_FIELDS": SCOPE_FIELDS,
                        "HERB_V3_TAGSIDE": TAGSIDE, "HERB_V3_PARTCOMB": PARTCOMB,
                        "HERB_V3_RAW_PART": RAW_PART, "HERB_V3_FACETADJ": FACETADJ})

_NO_SCOPE_QUESTIONS = 0     # run level: questions whose gate named no field, so the region
                            # was the whole corpus and no edge statistic was read

_ALL_TAGS_CYPHER = """
MATCH (t:Tag)
WHERE t.emb IS NOT NULL
  AND EXISTS { MATCH (t)<-[r:HAS_TAG]-(c:Chunk) WHERE r.run_id = $runId AND (c)-[:product]->() }
RETURN t.name AS name, t.emb AS emb
ORDER BY name
"""

_ALL_CHUNKS_CYPHER = """
MATCH (c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE c.desc_emb IS NOT NULL
  AND coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
  AND (c)-[:product]->()
RETURN c.chunk_id AS chunkId, c.desc_emb AS emb, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256
ORDER BY chunkId
"""

_ALL_EDGES_CYPHER = """
MATCH (t:Tag)<-[r:HAS_TAG]-(c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE r.run_id = $runId
  AND t.emb IS NOT NULL
  AND c.desc_emb IS NOT NULL
  AND coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
  AND (c)-[:product]->()
RETURN t.name AS tag, c.chunk_id AS chunkId, r.w_facets AS w
"""

_SHAPE_CYPHER = """
MATCH (c:Chunk)<-[:HAS_CHUNK]-(f:File)
WHERE (c)-[:product]->()
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
RETURN c.chunk_id AS chunkId,
       [(c)-[:product]->(p) | elementId(p)] AS products,
       [(c)-[:channel]->(ch) | elementId(ch)] AS channels
"""

_PRODUCT_NAMES_CYPHER = """
MATCH (p:Product)
RETURN p.name AS name
"""


@dataclass
class Prepared:
    driver: object
    tag_names: list
    tag_vecs: np.ndarray
    chunk_ids: list
    chunk_vecs: np.ndarray
    chunk_rows: list          # {chunkId, locator, relpath, sha256}, indexed as chunk_vecs
    edge_tag: np.ndarray      # tag index per connection
    edge_chunk: np.ndarray    # chunk index per connection
    edge_w: np.ndarray        # the five facetweights per connection
    edge_rank: Optional[np.ndarray] = None    # per connection, five group indices (rank source)
    edge_groups: Optional[np.ndarray] = None  # per connection, the tag's five group counts
    overlay: Optional[dict] = None   # {path, sha256, edges} when HERB_FACET_OVERLAY is read
    rank_overlay: Optional[dict] = None       # the same for HERB_RANK_OVERLAY
    build_stats: Optional[BuildStats] = None
    facets: tuple = ALL_FACETS                # the five names, by column, of edge_w
    shape: Optional[dict] = None              # the graph shape the region grows on (REGION=shape)
    adjacency: Optional[dict] = None          # which chunks touch inside their file (LOCALITY=on)
    bands: Optional[dict] = None              # the retrain bands of the four head columns
    kinds: Optional[list] = None              # the record kind per chunk, reported never sorted


def _csr(keys: np.ndarray, values: np.ndarray, rows: int) -> tuple:
    """(pointer, values sorted by key) — the members of each of `rows` keys, contiguously"""
    order = np.argsort(keys, kind="stable")
    ptr = np.zeros(rows + 1, dtype=np.int64)
    np.add.at(ptr, keys.astype(np.int64) + 1, 1)
    return np.cumsum(ptr), values[order]


def load_shape(session, chunk_ids: list, chunk_at: dict, e_tag: np.ndarray,
               e_chunk: np.ndarray, tag_names: list) -> dict:
    """the graph shape the region grows on: each chunk's product and Channel group, the tag
    sets both ways, and which tag names are product names (scope, not evidence — the
    co-occurrence path leaves them out). The tag sets are the connections already in memory
    (the same run_id / embedded-tag / described-chunk universe the walk sorts), not a second
    query."""
    n = len(chunk_ids)
    n_tags = len(tag_names)
    product = np.full(n, -1, dtype=np.int64)
    prod_at: dict = {}
    chan_at: dict = {}
    ch_chunk, ch_group = [], []
    for rec in session.run(_SHAPE_CYPHER, datasetId=DATASET_ID,
                           excludedSections=_EXCLUDED_PARAM):
        ci = chunk_at.get(rec["chunkId"])
        if ci is None:
            continue
        for p in rec["products"]:
            product[ci] = prod_at.setdefault(p, len(prod_at))
            break
        for g in rec["channels"]:
            ch_chunk.append(ci)
            ch_group.append(chan_at.setdefault(g, len(chan_at)))
    ch_chunk_a = np.asarray(ch_chunk, dtype=np.int64)
    ch_group_a = np.asarray(ch_group, dtype=np.int64)
    group_ptr, group_members = _csr(ch_group_a, ch_chunk_a, len(chan_at))
    chunk_group_ptr, chunk_groups = _csr(ch_chunk_a, ch_group_a, n)
    chunk_tag_ptr, chunk_tags = _csr(e_chunk.astype(np.int64), e_tag.astype(np.int64), n)
    tag_chunk_ptr, tag_chunks = _csr(e_tag.astype(np.int64), e_chunk.astype(np.int64), n_tags)
    prod_names = {str(rec["name"]).strip().lower() for rec in session.run(_PRODUCT_NAMES_CYPHER)
                  if rec["name"]}
    product_tag = np.fromiter((t.strip().lower() in prod_names for t in tag_names),
                              dtype=bool, count=n_tags)
    with_group = int(np.count_nonzero(np.diff(chunk_group_ptr)))
    print(f"artefact_v3: shape: {len(chan_at)} channels, {len(ch_chunk)} chunk-channel edges, "
          f"{with_group} chunks with at least one channel, {len(prod_at)} products",
          flush=True)
    print(f"artefact_v3: shape: {int(product_tag.sum())} of {n_tags} tags carry a Product "
          f"node's name ({len(prod_names)} names)", flush=True)
    return {"product": product, "product_tag": product_tag,
            "group_ptr": group_ptr, "group_members": group_members,
            "chunk_group_ptr": chunk_group_ptr, "chunk_groups": chunk_groups,
            "chunk_tag_ptr": chunk_tag_ptr, "chunk_tags": chunk_tags,
            "tag_chunk_ptr": tag_chunk_ptr, "tag_chunks": tag_chunks,
            "channels": len(chan_at), "chunk_channel_edges": len(ch_chunk),
            "chunks_with_channel": with_group, "products": len(prod_at),
            "product_tags": int(product_tag.sum())}


def file_adjacency(chunk_rows: list) -> dict:
    """which chunks sit next to each other inside their file — THE ORCHESTRATOR'S
    CONSTRUCTION 2026-09-13, not his ruling.

    The locator says what the chunk was cut from, and adjacency is read per record kind:

      slack — a chunk is a run of messages of ONE channel (`parent_ref` ends in the channel,
        `channel` names it). Two chunks of the same channel are adjacent when their message
        index ranges overlap or touch (the end of one is the start of the next minus one):
        consecutive messages of one conversation.
      a record cut into parts (documents, meeting transcripts — `char_range` inside one `id`)
        — adjacent when the two are parts of the SAME record and their character ranges
        overlap or touch.
      runs of whole records (prs, urls, meeting chats, the metadata files) — each item index
        is its own record, so two touching index ranges are two DIFFERENT records and are not
        neighbours; only chunks whose index ranges OVERLAP share a record.

    No number and no threshold: either the locators put the two inside one record, or
    consecutive in one channel, or they are not neighbours. Returns the CSR of each chunk's
    neighbours, the pair count, and the pairs per record kind."""
    n = len(chunk_rows)
    spans: dict = {}
    rule_of: dict = {}
    placed = 0
    for ci, row in enumerate(chunk_rows):
        raw = row.get("locator")
        if not raw:
            continue
        try:
            loc = json.loads(raw)
        except (TypeError, ValueError):
            continue
        kind = loc.get("section") or (f"metadata:{loc['metadata']}" if loc.get("metadata")
                                      else None)
        if kind is None:
            continue
        rng = loc.get("char_range")
        if rng and len(rng) == 2:
            # one record cut into parts: the record is the unit, the range is characters
            lo, hi = int(rng[0]), int(rng[1])
            key = (row.get("relpath"), loc.get("parent_ref"), loc.get("id"),
                   loc.get("index"), loc.get("field"))
            touching = True
        else:
            if loc.get("indices"):
                lo, hi = int(min(loc["indices"])), int(max(loc["indices"]))
            elif loc.get("index_start") is not None:
                lo, hi = int(loc["index_start"]), int(loc.get("index_end", loc["index_start"]))
            elif loc.get("index") is not None:
                lo = hi = int(loc["index"])
            else:
                continue
            if kind == "slack":
                key = (row.get("relpath"), loc.get("parent_ref"), loc.get("channel"))
                touching = True
            else:
                key = (row.get("relpath"), loc.get("parent_ref"))
                touching = False
        spans.setdefault(key, []).append((lo, hi, ci))
        rule_of[key] = (kind, touching)
        placed += 1
    pairs = []
    per_kind: dict = {}
    for key, members in spans.items():
        kind, touching = rule_of[key]
        gap = 1 if touching else 0
        members.sort()
        for a in range(len(members)):
            lo_a, hi_a, ci = members[a]
            for b in range(a + 1, len(members)):
                lo_b, hi_b, cj = members[b]
                if lo_b > hi_a + gap:
                    break
                if lo_a <= hi_b + gap:
                    pairs.append((ci, cj))
                    per_kind[kind] = per_kind.get(kind, 0) + 1
    left = np.asarray([p[0] for p in pairs] + [p[1] for p in pairs], dtype=np.int64)
    right = np.asarray([p[1] for p in pairs] + [p[0] for p in pairs], dtype=np.int64)
    ptr, members = (_csr(left, right, n) if pairs
                    else (np.zeros(n + 1, dtype=np.int64), np.zeros(0, dtype=np.int64)))
    shown = ", ".join(f"{kind} {count}" for kind, count in sorted(per_kind.items()))
    print(f"artefact_v3: file adjacency: {len(pairs)} adjacent chunk pairs over {placed} of "
          f"{n} located chunks in {len(spans)} sequences ({shown or 'none'})", flush=True)
    return {"ptr": ptr, "members": members, "pairs": len(pairs), "located": placed,
            "sequences": len(spans), "per_kind": per_kind}


def _distance_block(dists: list) -> dict:
    """the locality distances of a set of rows: how many rows at each hop, the share at 0"""
    total = len(dists)
    return {"rows": total,
            "distances": {str(d): dists.count(d) for d in (0, 1, 2, 3)},
            "share_zero": round(dists.count(0) / total, 4) if total else None,
            "max": max(dists) if dists else None}


_CONCENTRATION: dict = {}


def tag_concentration(prepared: Prepared) -> np.ndarray:
    """per edge: how concentrated the tag is around this chunk in the graph — THE
    ORCHESTRATOR'S CONSTRUCTION 2026-09-13, not his ruling.

    His 09-08 13:02 gives every facet but topic as a combination: the chunk's standing in that
    facet AND "the tag's relevance to the chunk". Reading that half as cos(tag, chunk
    description) is the topic facet a second time, so it cannot separate anything the topic
    column and the description link have not already said. Here the half is read off the graph
    instead ("use the graph shape", 09-13), in the shape of his original third facet, "sphere,
    aka realm of interest" (05-07).

    One ratio for every edge, the same quantity whatever the record kind:

        numerator   = the tag's chunks that sit inside this chunk's NEIGHBOURHOOD
        denominator = the tag's chunks corpus-wide

    The neighbourhood of a chunk is the chunk itself, the members of every [:channel] group it
    hangs on, and the chunks it touches inside its file (file_adjacency). Both numerator and
    denominator count chunks, so the ratio is in (0, 1] and falls as the tag spreads anywhere
    outside the neighbourhood, product boundaries included.

    The neighbourhood's SIZE differs by record kind and is not normalised away: a Slack chunk
    hangs on a channel group (median 7 members on this graph), a document / PR / transcript
    chunk has no group and reaches only its file-adjacent neighbours (median 2). A stated
    asymmetry: a Slack chunk has more room to be concentrated in than a document chunk.

    A tag on one chunk scores 1.0. A generic tag on one chunk in each of 30 products scores
    ~1/30. A product-name tag on 126 chunks scores (its chunks inside the neighbourhood)/126.
    A ratio of two counts the graph already holds — no constant, no weight, no model."""
    hit = _CONCENTRATION.get(id(prepared))
    if hit is not None and hit[0] is prepared:
        return hit[1]
    shape = prepared.shape
    if shape is None:
        raise RuntimeError("tag_concentration needs the graph shape; it loads in prepare_over_corpus")
    adjacency = prepared.adjacency
    if adjacency is None:
        raise RuntimeError("tag_concentration needs the file adjacency; it loads in "
                           "prepare_over_corpus")
    e_tag, e_chunk = prepared.edge_tag.astype(np.int64), prepared.edge_chunk.astype(np.int64)
    print(f"artefact_v3: tag concentration over {len(e_tag)} edges "
          f"({len(np.unique(e_tag))} tags) …", flush=True)
    t0 = time.perf_counter()
    chunk_group_ptr, chunk_groups = shape["chunk_group_ptr"], shape["chunk_groups"]
    tag_chunk_ptr, tag_chunks = shape["tag_chunk_ptr"], shape["tag_chunks"]
    a_ptr, a_of = adjacency["ptr"], adjacency["members"]
    conc = np.ones(len(e_tag), dtype=np.float64)
    ptr, members = _csr(e_tag, np.arange(len(e_tag), dtype=np.int64), len(prepared.tag_names))
    tags = np.unique(e_tag).tolist()
    for seen, t in enumerate(tags):
        if (seen + 1) % 2000 == 0:
            print(f"artefact_v3: tag concentration: {seen + 1}/{len(tags)} tags "
                  f"({time.perf_counter() - t0:.0f}s)", flush=True)
        mine = np.unique(tag_chunks[tag_chunk_ptr[t]:tag_chunk_ptr[t + 1]])
        total = len(mine)
        if total == 0:
            continue
        mine_set = set(mine.tolist())
        by_group: dict = {}
        for m in mine.tolist():
            for g in chunk_groups[chunk_group_ptr[m]:chunk_group_ptr[m + 1]].tolist():
                by_group.setdefault(g, []).append(m)
        near_at: dict = {}
        for j in members[ptr[t]:ptr[t + 1]].tolist():
            c = int(e_chunk[j])
            num = near_at.get(c)
            if num is None:
                near = {c} if c in mine_set else set()
                for g in chunk_groups[chunk_group_ptr[c]:chunk_group_ptr[c + 1]].tolist():
                    near.update(by_group.get(g, []))
                for m in a_of[a_ptr[c]:a_ptr[c + 1]].tolist():
                    if m in mine_set:
                        near.add(m)
                num = near_at[c] = len(near)
            conc[j] = num / total
    print(f"artefact_v3: tag concentration: {len(conc)} edges, "
          f"{float(np.mean(conc == 1.0)) * 100:.1f}% fully concentrated, "
          f"median {float(np.median(conc)):.3f} ({time.perf_counter() - t0:.0f}s)", flush=True)
    _CONCENTRATION[id(prepared)] = (prepared, conc)
    return conc


def column_positions(values: np.ndarray, rows: Optional[np.ndarray] = None,
                     unit: Optional[np.ndarray] = None) -> np.ndarray:
    """a column read the way a facet column is read: levels by the clump rule over the named
    population, 0.0 the strongest, as a position in 0..1. Rows outside the population keep
    0.0 and are never read (the two-population rule of facet_positions).

    `unit` names what generated each value: the column is levelled once per distinct unit
    inside the population and the positions are broadcast back to the rows, so the clump
    rule's chance test counts the values the data holds and not the rows that repeat them —
    the way facet_positions levels a chunk-level statistic once per chunk (the 09-11 fix).
    Without it every row is its own unit."""
    v = np.asarray(values, dtype=np.float64)
    pos = np.zeros(len(v), dtype=np.float64)
    idx = np.arange(len(v)) if rows is None else np.flatnonzero(np.asarray(rows, dtype=bool))
    if idx.size == 0:
        return pos
    d = 1.0 - v[idx]
    if unit is None:
        lv = distance_levels(d).astype(np.float64)
    else:
        _, first, inv = np.unique(np.asarray(unit)[idx], return_index=True, return_inverse=True)
        lv = distance_levels(d[first]).astype(np.float64)[inv.ravel()]
    top = lv.max()
    pos[idx] = lv / top if top > 0 else 0.0
    return pos


def grow_region(prepared: Prepared, seeds: np.ndarray, seed_lvl: np.ndarray,
                seed_val: Optional[np.ndarray] = None) -> tuple:
    """the region the graph's shape grows around the seeds, one hop out.

    group (REGION=shape, the arm): every chunk of the same product sharing a [:channel]
    Channel node with a seed.
    The group node is a relation the graph holds between the chunk and its file — "use the
    graph shape" (2026-09-13); the hop is the unit, no number and no threshold.

    co-occurrence (REGION=shape+cooc): a chunk with a chunk→tag→chunk path to a seed through a
    tag that is not a product name (product names are scope, not evidence). Off by default —
    any threshold on how many such tags a chunk must share is a chosen number, his to rule.

    A seed sits at tag level 0 by definition of a seed, so the hop puts a grown chunk at 1;
    the caller ANDs the description side, so it enters at max(1, its own description steps).
    No weight, no count. Returns (level per chunk, -1 where the shape does not reach,
    reached-by-group mask, reached-by-co-occurrence mask, best seed value per chunk when
    `seed_val` is given — the tag end the hop carries, nan where the shape does not reach)."""
    shape = prepared.shape
    n = len(prepared.chunk_ids)
    lvl = np.full(n, -1, dtype=np.int64)
    by_group = np.zeros(n, dtype=bool)
    by_cooc = np.zeros(n, dtype=bool)
    val = np.full(n, np.nan, dtype=np.float64)
    sv = (np.zeros(seeds.size) if seed_val is None
          else np.asarray(seed_val, dtype=np.float64)).tolist()
    if shape is None or seeds.size == 0:
        return lvl, by_group, by_cooc, val
    for c, L, V in zip(seeds.tolist(), seed_lvl.tolist(), sv):
        groups = shape["chunk_groups"][shape["chunk_group_ptr"][c]:shape["chunk_group_ptr"][c + 1]]
        for g in groups.tolist():
            members = shape["group_members"][shape["group_ptr"][g]:shape["group_ptr"][g + 1]]
            for m in members.tolist():
                if m == c or shape["product"][m] != shape["product"][c]:
                    continue
                by_group[m] = True
                if lvl[m] < 0 or lvl[m] > L + 1:
                    lvl[m] = L + 1
                if np.isnan(val[m]) or val[m] < V:
                    val[m] = V
    if REGION == "shape+cooc":
        not_product = ~shape["product_tag"]
        for c, L, V in zip(seeds.tolist(), seed_lvl.tolist(), sv):
            tags = shape["chunk_tags"][shape["chunk_tag_ptr"][c]:shape["chunk_tag_ptr"][c + 1]]
            tags = tags[not_product[tags]]
            if tags.size == 0:
                continue
            reach = np.concatenate([shape["tag_chunks"][shape["tag_chunk_ptr"][t]:shape["tag_chunk_ptr"][t + 1]]
                                    for t in tags.tolist()])
            for m in np.unique(reach).tolist():
                if m == c:
                    continue
                by_cooc[m] = True
                if lvl[m] < 0 or lvl[m] > L + 1:
                    lvl[m] = L + 1
                if np.isnan(val[m]) or val[m] < V:
                    val[m] = V
    return lvl, by_group, by_cooc, val


def read_facet_file(names: list, chunk_ids: list, e_tag: np.ndarray, e_chunk: np.ndarray,
                    tag_vecs, chunk_vecs) -> tuple:
    """the five facet values per connection, off the file the source names, and what was read.

    One shape, one reader: the chunk-level statistics file (FACET_SOURCE edge | stats,
    HERB_FACET_STATS) and the per-edge file (FACET_SOURCE=file, HERB_FACET_FILE) are both
    {database, run_id, facets, edges:[{tag, chunkId, weights:[5]}]}. What differs is how the
    four non-topic columns are levelled afterwards, in facet_positions. A null or absent topic
    is the graph's cos(Tag.emb, Chunk.desc_emb); a null or absent value in any other column is
    NaN and sorts last in that column."""
    src = FACET_FILE if FACET_SOURCE == "file" else FACET_STATS
    label = "facet file" if FACET_SOURCE == "file" else "facet stats"
    if not Path(src).is_file():
        raise RuntimeError(
            f"HERB_FACET_FILE {src} does not exist" if FACET_SOURCE == "file" else
            f"HERB_FACET_STATS {src} does not exist; write it with "
            f"NEO4J_DATABASE={DATABASE} python test/graph/facet_stats.py --overlay")
    body = json.loads(Path(src).read_text(encoding="utf-8"))
    if body.get("database") != DATABASE or body.get("run_id") != RUN_ID:
        raise RuntimeError(f"{label} {src} was written on "
                           f"{body.get('database')!r}/{body.get('run_id')!r}, "
                           f"not {DATABASE!r}/{RUN_ID!r}")
    if list(body.get("facets") or []) != list(STAT_FACETS):
        raise RuntimeError(f"{label} names its facets {body.get('facets')!r}, "
                           f"not {list(STAT_FACETS)}")
    at = {(names[t], chunk_ids[c]): i for i, (t, c) in enumerate(zip(e_tag, e_chunk))}
    edge_w = np.full((len(e_tag), len(STAT_FACETS)), np.nan, dtype=np.float64)
    hit = 0
    for row in body["edges"]:
        i = at.get((row["tag"], row["chunkId"]))
        if i is not None:
            edge_w[i] = [np.nan if v is None else float(v) for v in row["weights"]]
            hit += 1
    # topic is the tag-against-description cosine and lives on the graph: an edge the
    # file does not carry, and an edge whose topic the file leaves null, still gets it
    no_row = np.isnan(edge_w[:, 0])
    if no_row.any():
        tv = _unit(np.stack(tag_vecs).astype(np.float64))
        cv = _unit(np.stack(chunk_vecs).astype(np.float64))
        j = np.flatnonzero(no_row)
        edge_w[j, 0] = np.einsum("ij,ij->i", tv[e_tag[j]], cv[e_chunk[j]])
    unanchored = int(np.isnan(edge_w[:, 1]).sum())
    overlay = {"path": str(src), "sha256": _file_sha(src), "edges": hit,
               "edges_in_file": len(body["edges"]), "unanchored": unanchored,
               "facets": list(STAT_FACETS), "method": body.get("method"),
               "per_edge": FACET_SOURCE == "file"}
    print(f"artefact_v3: {label} {Path(src).name}: {hit} of {len(e_tag)} "
          f"connections carry the five values, {unanchored} without one sort last "
          f"({overlay['sha256'][:12]})", flush=True)
    return edge_w, overlay


def prepare_over_corpus(corpus, concept_walk: bool = True) -> Prepared:
    """concept_walk=False is another arm borrowing this preparation: the concept walk's graph
    shape and file adjacency are not loaded and its knobs say nothing about that arm's run."""
    t0 = time.perf_counter()
    print(f"artefact_v3: opening {DATABASE}, loading every tag vector …", flush=True)
    drv = _driver()
    names, vecs = [], []
    with drv.session(database=DATABASE) as s:
        if FACET_SOURCE not in TEXT_SOURCES:
            five = s.run("MATCH ()-[r:HAS_TAG]->() WHERE r.run_id = $runId AND size(r.w_facets) <> 5 "
                         "RETURN count(r) AS n", runId=RUN_ID).single()["n"]
            if five:
                raise RuntimeError(f"{five} HAS_TAG edges do not carry five facet values")
            misordered = s.run("MATCH ()-[r:HAS_TAG]->() WHERE r.run_id = $runId "
                               "AND r.facets IS NOT NULL AND r.facets <> $facets "
                               "RETURN count(r) AS n", runId=RUN_ID,
                               facets=list(ALL_FACETS)).single()["n"]
            if misordered:
                raise RuntimeError(f"{misordered} HAS_TAG edges name their facets in another "
                                   f"order than {list(ALL_FACETS)}; the five numbers are read "
                                   f"by position")
        for i, rec in enumerate(s.run(_ALL_TAGS_CYPHER, runId=RUN_ID)):
            names.append(rec["name"])
            vecs.append(np.asarray(rec["emb"], dtype=np.float32))
            if (i + 1) % 4000 == 0:
                print(f"artefact_v3:   {i + 1} tags ({time.perf_counter() - t0:.0f}s)", flush=True)
    if not names:
        raise RuntimeError(f"{DATABASE!r} holds no embedded tag with a {RUN_ID!r} edge")
    print(f"artefact_v3: {len(names)} tags in memory ({time.perf_counter() - t0:.1f}s)", flush=True)

    print("artefact_v3: loading every chunk description vector …", flush=True)
    chunk_ids, chunk_vecs, chunk_rows = [], [], []
    with drv.session(database=DATABASE) as s:
        for rec in s.run(_ALL_CHUNKS_CYPHER, datasetId=DATASET_ID,
                         excludedSections=_EXCLUDED_PARAM):
            chunk_ids.append(rec["chunkId"])
            chunk_vecs.append(np.asarray(rec["emb"], dtype=np.float32))
            chunk_rows.append({"chunkId": rec["chunkId"], "locator": rec["locator"],
                               "relpath": rec["relpath"], "sha256": rec["sha256"]})
    if not chunk_ids:
        raise RuntimeError(f"{DATABASE!r} holds no chunk with a description vector inside "
                           f"dataset {DATASET_ID!r}")
    tag_at = {n: i for i, n in enumerate(names)}
    chunk_at = {c: i for i, c in enumerate(chunk_ids)}
    print(f"artefact_v3: {len(chunk_ids)} chunk descriptions in memory "
          f"({time.perf_counter() - t0:.1f}s); loading every connection …", flush=True)

    e_tag, e_chunk, e_w = [], [], []
    with drv.session(database=DATABASE) as s:
        for rec in s.run(_ALL_EDGES_CYPHER, runId=RUN_ID, datasetId=DATASET_ID,
                         excludedSections=_EXCLUDED_PARAM):
            ti, ci = tag_at.get(rec["tag"]), chunk_at.get(rec["chunkId"])
            if ti is None or ci is None:
                continue
            e_tag.append(ti)
            e_chunk.append(ci)
            e_w.append(rec["w"])
    if not e_tag:
        raise RuntimeError(f"{DATABASE!r} holds no {RUN_ID!r} connection between an embedded "
                           f"tag and a described chunk")
    print(f"artefact_v3: {len(e_tag)} connections in memory "
          f"({time.perf_counter() - t0:.1f}s)", flush=True)
    edge_w = np.asarray(e_w, dtype=np.float64)
    overlay = None
    if FACET_SOURCE in TEXT_SOURCES:
        edge_w, overlay = read_facet_file(names, chunk_ids, np.asarray(e_tag),
                                          np.asarray(e_chunk), vecs, chunk_vecs)
    if FACET_OVERLAY and FACET_SOURCE not in TEXT_SOURCES:
        body = json.loads(Path(FACET_OVERLAY).read_text(encoding="utf-8"))
        if body.get("database") != DATABASE or body.get("run_id") != RUN_ID:
            raise RuntimeError(f"overlay {FACET_OVERLAY} was weighed on "
                               f"{body.get('database')!r}/{body.get('run_id')!r}, "
                               f"not {DATABASE!r}/{RUN_ID!r}")
        if list(body.get("facets") or []) != list(ALL_FACETS):
            raise RuntimeError(f"overlay names its facets {body.get('facets')!r}, "
                               f"not {list(ALL_FACETS)}")
        at = {(names[t], chunk_ids[c]): i for i, (t, c) in enumerate(zip(e_tag, e_chunk))}
        hit = 0
        for row in body["edges"]:
            i = at.get((row["tag"], row["chunkId"]))
            if i is not None:
                edge_w[i] = row["weights"]
                hit += 1
        overlay = {"path": str(FACET_OVERLAY), "sha256": _overlay_sha(), "edges": hit,
                   "edges_in_file": len(body["edges"])}
        print(f"artefact_v3: overlay {Path(FACET_OVERLAY).name}: {hit} of {len(body['edges'])} "
              f"edges replaced in memory ({overlay['sha256'][:12]})", flush=True)
    edge_rank = np.zeros((len(e_tag), len(active_facets())), dtype=np.int32)
    edge_groups = np.ones((len(e_tag), len(active_facets())), dtype=np.int32)
    rank_overlay = None
    if RANK_OVERLAY:
        body = json.loads(Path(RANK_OVERLAY).read_text(encoding="utf-8"))
        if body.get("database") != DATABASE or body.get("run_id") != RUN_ID:
            raise RuntimeError(f"rank overlay {RANK_OVERLAY} was ordered on "
                               f"{body.get('database')!r}/{body.get('run_id')!r}, "
                               f"not {DATABASE!r}/{RUN_ID!r}")
        if list(body.get("facets") or []) != list(ALL_FACETS):
            raise RuntimeError(f"rank overlay names its facets {body.get('facets')!r}, "
                               f"not {list(ALL_FACETS)}")
        at = {(names[t], chunk_ids[c]): i for i, (t, c) in enumerate(zip(e_tag, e_chunk))}
        hit = 0
        for row in body["edges"]:
            i = at.get((row["tag"], row["chunkId"]))
            if i is not None:
                edge_rank[i] = row["rank"]
                edge_groups[i] = row["groups"]
                hit += 1
        rank_overlay = {"path": str(RANK_OVERLAY), "sha256": _file_sha(RANK_OVERLAY),
                        "edges": hit, "edges_in_file": len(body["edges"]),
                        "model": body.get("model"), "window": body.get("window"),
                        "repeat_agreement": body.get("repeat_agreement")}
        print(f"artefact_v3: rank overlay {Path(RANK_OVERLAY).name}: {hit} of "
              f"{len(body['edges'])} edges ranked in memory ({rank_overlay['sha256'][:12]})",
              flush=True)
    print(f"artefact_v3: facet source = {FACET_SOURCE}", flush=True)
    shape = None
    adjacency = None
    concept = concept_walk and SORT_MODE == "concept"
    forum = concept_walk and SORT_MODE in FORUM_MODES
    if forum:
        # the forum modes read the graph shape for one thing only: which tag names are a
        # Product node's name, so those edges are not candidates (his 09-14, names are
        # structure). No growth, no adjacency, no locality.
        print("artefact_v3: loading the graph shape (the product names the tag side drops) …",
              flush=True)
        with drv.session(database=DATABASE) as s:
            shape = load_shape(s, chunk_ids, chunk_at, np.asarray(e_tag, dtype=np.int64),
                               np.asarray(e_chunk, dtype=np.int64), names)
    if concept and (LOCALITY == "on" or TAGREL == "shape"):
        adjacency = file_adjacency(chunk_rows)
    if concept and (REGION in ("shape", "shape+cooc") or TAGREL == "shape"
                    or LOCALITY == "on" or TAGSIDE == "nonscope"):
        print("artefact_v3: loading the graph shape (product, channel groups, tag sets) …",
              flush=True)
        with drv.session(database=DATABASE) as s:
            shape = load_shape(s, chunk_ids, chunk_at, np.asarray(e_tag, dtype=np.int64),
                               np.asarray(e_chunk, dtype=np.int64), names)
    prepared = Prepared(driver=drv, tag_names=names,
                        tag_vecs=_unit(np.stack(vecs).astype(np.float64)),
                        chunk_ids=chunk_ids,
                        chunk_vecs=_unit(np.stack(chunk_vecs).astype(np.float64)),
                        chunk_rows=chunk_rows,
                        edge_tag=np.asarray(e_tag, dtype=np.int32),
                        edge_chunk=np.asarray(e_chunk, dtype=np.int32),
                        edge_w=edge_w, edge_rank=edge_rank, edge_groups=edge_groups,
                        overlay=overlay, rank_overlay=rank_overlay, facets=active_facets(),
                        shape=shape, adjacency=adjacency,
                        build_stats=BuildStats(build_time_s=0.0, models=[], model=ModelUsage()))
    if concept and FACET_SOURCE != "edge":
        # the corpus's own facet columns read no question, so they are built here and no
        # question's search_time_s carries them. Under FACET_SOURCE=edge a question levels its
        # own matrix; the concentration layer is built on first need inside a question and its
        # seconds are booked as prepare there.
        print("artefact_v3: levelling the corpus facet columns …", flush=True)
        facet_positions(prepared, None)
    if forum:
        prepared.bands = load_retrain_bands()
        with drv.session(database=DATABASE) as s:
            prepared.kinds = load_record_kinds(s, chunk_ids)
    prepared.build_stats.build_time_s = round(time.perf_counter() - t0, 1)
    print(f"artefact_v3: prepared in {prepared.build_stats.build_time_s}s", flush=True)
    return prepared


def scope_terms(gate: dict) -> tuple:
    """cypher terms for the fields the gate names (SCOPE_FIELDS: product / section / years,
    or the product alone)"""
    terms, params = [], {}
    if gate.get("product"):
        terms.append("exists { (c)-[:product]->(p:Product) WHERE p.name = $g_product }")
        params["g_product"] = gate["product"]
    if SCOPE_FIELDS == "product":
        return terms, params
    if gate.get("section"):
        terms.append("c.section = $g_section")
        params["g_section"] = gate["section"]
    if gate.get("years"):
        terms.append("any(y IN $g_years WHERE y IN coalesce(c.years, []))")
        params["g_years"] = list(gate["years"])
    return terms, params


def scope_chunks(session, gate: dict, join: str = "OR") -> tuple:
    """chunk ids the stated scope names, and the fields it was named by"""
    terms, params = scope_terms(gate)
    if not terms:
        return set(), []
    cypher = f"""
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND NOT (coalesce(c.section, "") IN $excludedSections)
  AND (c)-[:product]->()
  AND ({f" {join} ".join(terms)})
RETURN c.chunk_id AS chunkId
"""
    ids = {r["chunkId"] for r in session.run(cypher, datasetId=DATASET_ID,
                                             excludedSections=_EXCLUDED_PARAM, **params)}
    named = [k.replace("g_", "") for k in params]
    return ids, named


def connection_fit(tag_sim: np.ndarray, desc_sim: np.ndarray) -> np.ndarray:
    """fit of a connection from its two ends (FIT_RULE)"""
    if FIT_RULE == "tag":
        return tag_sim
    if FIT_RULE == "min":
        return np.minimum(tag_sim, desc_sim)
    if FIT_RULE == "midpoint":
        return 0.5 * (tag_sim + desc_sim)
    raise ValueError(f"unknown FIT_RULE {FIT_RULE!r}")


# ------------------------------------------------------------------ levels

def levels(values: np.ndarray) -> np.ndarray:
    """a facet column with no query weight to measure from: a level per basin of the values'
    own density, 0 = the highest"""
    v = np.asarray(values, dtype=np.float64)
    n = len(v)
    if n <= 1:
        return np.zeros(n, dtype=int)
    uniq = np.unique(v)
    if len(uniq) < 3 or LEVEL_RULE == "none":
        rank = {u: i for i, u in enumerate(uniq[::-1])}
        return (np.zeros(n, dtype=int) if LEVEL_RULE == "none"
                else np.array([rank[x] for x in v], dtype=int))
    kde = gaussian_kde(uniq, bw_method=KDE_BW)
    if KDE_BW_FACTOR != 1.0:
        kde.set_bandwidth(kde.factor * KDE_BW_FACTOR)
    grid = np.linspace(uniq[0], uniq[-1], KDE_GRID)
    valleys = grid[argrelmin(kde(grid))[0]]
    if len(valleys) == 0:
        return np.zeros(n, dtype=int)
    return (len(valleys) - np.searchsorted(valleys, v, side="right")).astype(int)


def levels_cos(values: np.ndarray, band: Optional[float] = None) -> np.ndarray:
    """levels of a cosine column: walking down from the top, a level ends where the value has
    fallen further than `band` (COS_NOISE when not given)"""
    band = COS_NOISE if band is None else float(band)
    v = np.asarray(values, dtype=np.float64)
    n = len(v)
    lv = np.zeros(n, dtype=int)
    if n <= 1:
        return lv
    order = np.argsort(-v, kind="stable")
    top = v[order[0]]
    cur = 0
    for idx in order:
        if top - v[idx] > band:
            cur += 1
            top = v[idx]
        lv[idx] = cur
    return lv


def _expected_empty_runs(cells: int, rows: int, run: int) -> float:
    """expected count of `run`-cell empty windows, `rows` rows iid over `cells` cells"""
    if run <= 0:
        return float("inf")
    if run >= cells:
        return 0.0
    return (cells - run + 1) * (1.0 - run / cells) ** rows


def clump_levels(values: np.ndarray, grain: float = 0.0) -> np.ndarray:
    """levels of a column: cut at the widest gap while chance would not have left it"""
    g = grain or WEIGHT_GRAIN
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return np.zeros(0, dtype=int)
    cell = np.rint(v / g).astype(np.int64)
    uniq, inv, count = np.unique(cell, return_inverse=True, return_counts=True)
    label = np.zeros(len(uniq), dtype=int)
    nxt = [0]

    def cut(lo: int, hi: int) -> None:
        if hi > lo:
            gaps = np.diff(uniq[lo:hi + 1])
            i = int(np.argmax(gaps))
            span = int(uniq[hi] - uniq[lo]) + 1
            rows = int(count[lo:hi + 1].sum())
            if _expected_empty_runs(span, rows, int(gaps[i]) - 1) < 1.0:
                cut(lo, lo + i)
                cut(lo + i + 1, hi)
                return
        label[lo:hi + 1] = nxt[0]
        nxt[0] += 1

    cut(0, len(uniq) - 1)
    return label[inv]


def distance_levels(d: np.ndarray) -> np.ndarray:
    """levels of a distance column, 0 = nearest (DIST_RULE)"""
    if DIST_RULE == "clump":
        return clump_levels(d)
    if DIST_RULE == "none":
        cell = np.rint(d / WEIGHT_GRAIN).astype(np.int64)
        return np.searchsorted(np.unique(cell), cell)
    if DIST_RANGE > 0:
        return np.floor(d / DIST_RANGE + 1e-9).astype(int)
    return levels(-d)


def facet_levels(W: np.ndarray, f: str, query_w: Optional[float],
                 facets: Optional[tuple] = None) -> np.ndarray:
    """level per edge on facet f, 0 the strongest (DIST_RULE); a missing value sorts last.

    The query weight's place inside a column is open on his record, 2026-09-13; until he rules,
    the weight is carried and the column runs strongest-first. query_w is taken and ignored."""
    facets = facets or active_facets()
    w = W[:, facets.index(f)]
    missing = np.isnan(w)
    if missing.all():
        return np.zeros(len(w), dtype=int)
    if missing.any():
        lv = np.zeros(len(w), dtype=int)
        inner = facet_levels(W[~missing], f, query_w, facets)
        lv[~missing] = inner
        lv[missing] = int(inner.max()) + 1
        return lv
    return distance_levels(1.0 - w)


def facet_order(part: dict, facets: Optional[tuple] = None) -> tuple:
    """the part's five facets, most important first. stats: the order the interpreter named
    (part["order"]); weight / rank: by the part's facet weights. Neither: the key order."""
    layout = facets or active_facets()
    order = part.get("order") if isinstance(part, dict) else None
    if isinstance(order, list) and sorted(order) == sorted(layout):
        return tuple(order)
    weights = part.get("facets") if isinstance(part, dict) else None
    if not isinstance(weights, dict) or weights == NEUTRAL_FACETS or not any(
            float(v) for v in weights.values()):
        return tuple(layout)
    return tuple(sorted(layout, key=lambda f: (-float(weights.get(f, 0.0)), layout.index(f))))


def facet_weights(part: dict, facets: Optional[tuple] = None) -> Optional[dict]:
    """the part's query-side weight per facet: how much that facet matters for this part
    ("the query part says how much each facet matters for this query", 09-06). A column's
    direction is distance from this value. Query-side and ephemeral; it never reaches the
    graph. None when the plan names no weights for the active layout, and then a column
    runs strongest first."""
    layout = facets or active_facets()
    raw = part.get("weights") if isinstance(part, dict) else None
    if not isinstance(raw, dict) or sorted(raw) != sorted(layout):
        raw = part.get("facets") if isinstance(part, dict) else None
        if not isinstance(raw, dict) or sorted(raw) != sorted(layout):
            return None
    try:
        w = {f: float(raw[f]) for f in layout}
    except (TypeError, ValueError):
        return None
    if w == NEUTRAL_FACETS or not any(w.values()):
        return None
    return w


def sort_connections(edges: list, cos: dict, order: tuple,
                     query_w: Optional[dict], facets: Optional[tuple] = None) -> tuple:
    """sorted indices of one level, and levels per facet column"""
    facets = facets or active_facets()
    if FACET_SOURCE == "rank":
        R = np.asarray([e["rank"] for e in edges], dtype=np.int64).reshape(len(edges), -1)
        lv = {f: R[:, facets.index(f)] for f in order}
    else:
        W = np.asarray([e["w"] for e in edges], dtype=np.float64)
        lv = {f: facet_levels(W, f, (query_w or {}).get(f), facets) for f in order}
    idx = sorted(range(len(edges)),
                 key=lambda i: tuple(int(lv[f][i]) for f in order)
                 + (-cos[edges[i]["tag"]], edges[i]["chunkId"]))
    return idx, {f: int(len(np.unique(lv[f]))) for f in order}


# ------------------------------------------------------------------ the interpreter (stats)

_ORDER_SYSTEM = (
    "You are given a user query and the query's parts (short phrases). For EACH part, order the "
    "five facets from the one that matters most for finding the right passages about that part "
    "in this query, to the one that matters least, and give each facet a weight between 0.0 and "
    "1.0 saying how much that facet matters for that part — 1.0 the facet decides which "
    "passages are right, 0.0 it does not matter at all. The weights follow the order: the first "
    "facet in the order carries the highest weight and the weights never rise along the order. "
    "The facets: "
    "topic — the passage is centrally about the part; "
    "temporal — what the passage says about the part hangs on when (dates, deadlines, recency, "
    "what changed); "
    "why — the passage gives the cause or purpose behind the part (because, in order to, due to); "
    "activity — something is being done, changed, decided or run regarding the part, as against "
    "the part being described or referenced; "
    "concreteness — the passage is specific about the part (figures, names, exact values, exact "
    "decisions), as against general talk. "
    "Use every facet exactly once per part, and weigh every facet of every part. "
    'Return ONLY valid JSON: {"orders":[{"t":"part","order":["topic","temporal","why","activity",'
    '"concreteness"],"weights":{"topic":1.0,"temporal":0.6,"why":0.4,"activity":0.3,'
    '"concreteness":0.1}}]}'
)


def _validate_orders(parsed: dict, weights_fatal: bool = True,
                     invalid: Optional[list] = None) -> None:
    """An order that is not a permutation of the five always raises. A weights block that
    contradicts its own order raises while weights_fatal (the first ask); after the retry the
    part is named in `invalid` instead, keeps its order and carries no weights."""

    def weights_bad(row: dict, message: str) -> None:
        if weights_fatal or invalid is None:
            raise ValueError(message)
        invalid.append(row["t"])

    rows = parsed.get("orders")
    if not isinstance(rows, list):
        raise ValueError(f"orders is not a list: {type(rows).__name__}")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("t"), str):
            raise ValueError(f"order row malformed: {row!r}")
        order = row.get("order")
        if not isinstance(order, list) or sorted(order) != sorted(STAT_FACETS):
            raise ValueError(f"order of {row['t']!r} is not a permutation of {STAT_FACETS}: {order!r}")
        weights = row.get("weights")
        if not isinstance(weights, dict) or sorted(weights) != sorted(STAT_FACETS):
            weights_bad(row, f"weights of {row['t']!r} do not name every facet: {weights!r}")
            continue
        try:
            vals = [float(weights[f]) for f in order]
        except (TypeError, ValueError):
            weights_bad(row, f"weights of {row['t']!r} are not numbers: {weights!r}")
            continue
        if any(v < 0.0 or v > 1.0 for v in vals):
            weights_bad(row, f"weights of {row['t']!r} leave 0.0–1.0: {weights!r}")
            continue
        if any(b > a for a, b in zip(vals, vals[1:])):
            weights_bad(row, f"weights of {row['t']!r} rise along its own order: {weights!r} / {order!r}")


def _interpret_order(text: str, model: str) -> tuple:
    """(plan, calls, tokens_in, tokens_out, time_s); plan = {description, parts:[{t, order,
    weights}], gate}. Pass 1 is artefact_v2's (description, parts, gate). Pass 2 names, per part,
    the facet order and how much each facet matters for that part; a part the model leaves out
    keeps the key order, carries no weights, and is listed in plan["unordered"]."""
    # pass 1 is artefact_v2's, through its own cache, so the parts are the parts every
    # earlier run of this question used; a new prompt here would re-read the question
    v2_plan, c1, in1, out1, t1 = _interpret_cached(text, model)
    description = v2_plan.get("description") or text
    gate = _parse_gate(v2_plan.get("gate"))
    raw_parts = [p["t"] for p in v2_plan.get("parts", []) if isinstance(p, dict) and p.get("t")]
    if not raw_parts or raw_parts == [description]:
        return ({"description": description, "gate": gate,
                 "parts": [{"t": description, "order": list(STAT_FACETS)}]},
                c1, in1, out1, t1)
    bad_weights: list = []
    asks = [0]

    def check(parsed: dict) -> None:
        asks[0] += 1
        del bad_weights[:]
        _validate_orders(parsed, weights_fatal=asks[0] == 1, invalid=bad_weights)

    p2, in2, out2, t2 = _chat_json(
        model, _ORDER_SYSTEM,
        f"User query: {text}\n\nParts:\n{json.dumps(raw_parts)}", 1024, validate=check)
    order_map = {_clean_tag(row["t"]).casefold(): list(row["order"]) for row in p2["orders"]}
    bad = {_clean_tag(t).casefold() for t in bad_weights}
    weight_map = {_clean_tag(row["t"]).casefold(): {f: float(row["weights"][f]) for f in STAT_FACETS}
                  for row in p2["orders"] if _clean_tag(row["t"]).casefold() not in bad}
    unordered = [t for t in raw_parts if t.casefold() not in order_map]
    parts = []
    for t in raw_parts:
        key = t.casefold()
        part = {"t": t, "order": order_map.get(key, list(STAT_FACETS))}
        if key in weight_map:
            part["weights"] = weight_map[key]
        elif key in bad:
            part["weights"] = None
            part["weights_invalid"] = True
        parts.append(part)
    plan = {"description": description, "parts": parts, "gate": gate}
    if unordered:
        plan["unordered"] = unordered
    return plan, c1 + 1, in1 + in2, out1 + out2, t1 + t2


_ORDER_SIG = hashlib.sha256("\x00".join([
    _ORDER_SYSTEM, repr(STAT_FACETS), inspect.getsource(_interpret_order),
    inspect.getsource(_validate_orders),
]).encode("utf-8")).hexdigest()


def _interpret_order_cached(text: str, model: str) -> tuple:
    h = hashlib.sha256()
    for field in (model, _ORDER_SIG, text):
        b = field.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    path = INTERP_CACHE_DIR / f"order_{h.hexdigest()}.json"
    if not FRESH_INTERP and path.is_file():
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            plan = None
        if isinstance(plan, dict) and isinstance(plan.get("parts"), list):
            return plan, 0, 0, 0, 0.0
    plan, calls, tok_in, tok_out, secs = _interpret_order(text, model)
    INTERP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=INTERP_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return plan, calls, tok_in, tok_out, secs


# ------------------------------------------------------------------ concept (the arm, 09-11)

def band_steps(values: np.ndarray, band: float) -> np.ndarray:
    """how many bands below the best value each value sits: floor((best - v) / band). The
    semiorder's unit (Tversky 1969): values within one band of each other are equal, and a
    distance counted in bands means the same on any scale the band was measured on — which is
    what the AND of a tag side and a description side needs. Chaining (levels_cos) counts a
    jump across a sparse gap as one level, however wide; measured 09-11 on the smoke
    questions' own vectors, the 20th-nearest tag sits at chained level 11 and 22 bands down."""
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return np.zeros(0, dtype=np.int64)
    return np.floor((v.max() - v) / band + 1e-12).astype(np.int64)


def _embed_passage(texts: list, usage: ModelUsage,
                   also: Optional[ModelUsage] = None) -> np.ndarray:
    """the harness's embedder on the corpus side (the passage prefix), through the arm's
    on-disk vector cache; what it cost is added to the question's usage, and to `also` when a
    second tally is handed in (the sentence embedding, which is retrieval work and stays
    inside search_time_s)."""
    mat, calls, tok_in, tok_out, secs = _embed_cached(texts, "passage")
    for u in (usage, also):
        if u is None:
            continue
        u.calls += calls
        u.tokens_in += tok_in
        u.tokens_out += tok_out
        u.time_s += secs
    return np.asarray(mat, dtype=np.float64)


_UNVERIFIABLE_KEYS = frozenset(("embed_model", "embed_revision", "corpus_sha256"))


def region_edge_stats(prepared: Prepared, in_region: np.ndarray, embed) -> tuple:
    """FACET_SOURCE=edge, THE ORCHESTRATOR'S CONSTRUCTION 2026-09-13 (not his ruling): the four
    text statistics per edge, read on the tag's own sentences inside the chunk.

    Only the region's chunks are split and embedded ("embed the entire corpus … is retarded",
    09-09), at query time, cached on disk. The tag's sentences are the nearest sentence to the
    tag's vector and every sentence within COS_NOISE of it ("NEARNESS, we cant fucking use
    explicit shit", 09-09) — the embedder's measured just-noticeable difference, on the scale
    it is applied on. STRUCK 09-13: a per-chunk band of |cos(sentence, description) −
    cos(sentence, raw question)|, a query-to-sentence spread applied tag-to-sentence.
    The statistics and their aggregation are facet_stats', imported (test/graph/sentence_facets.py).

    Returns (the question's edge matrix, what it cost, the edges that actually carry a per-edge
    value). An edge whose chunk is outside the region keeps its chunk-level value from the
    statistics file. So does an in-scope edge whose text does not resolve or whose sentence set
    holds no token — a fallback: it is not in the per-edge mask, it carries the chunk-level
    value inside the pass-1 population the caller levels, and it is counted in
    log["fallback_edges"]. topic is untouched — it is cos(tag, chunk description).

    log["cache_unverified_chunks"] counts this question's region chunks whose cache file
    predates a meta key (embed_model, embed_revision, corpus_sha256), so what produced its
    bytes was never checked against this run; the file is left as it is."""
    from graph import sentence_facets as sf
    W = prepared.edge_w.copy()
    layout = prepared.facets
    cols = [layout.index(f) for f in sf.STATS]
    e_tag, e_chunk = prepared.edge_tag, prepared.edge_chunk
    n = len(prepared.chunk_ids)
    ptr, members = _csr(e_chunk.astype(np.int64), np.arange(len(e_chunk), dtype=np.int64), n)
    todo = np.flatnonzero(in_region).tolist()
    per_edge = np.zeros(len(e_chunk), dtype=bool)
    log = {"chunks": len(todo), "cached": 0, "embedded": 0, "sentences": 0, "edges": 0,
           "unresolved": 0, "cache_unverified_chunks": 0}
    t0 = time.perf_counter()
    print(f"artefact_v3:   edge facets: {len(todo)} region chunks, reading the tag's own "
          f"sentences …", flush=True)
    for seen, c in enumerate(todo):
        idx = members[ptr[c]:ptr[c + 1]]
        if idx.size == 0:
            continue
        row = prepared.chunk_rows[c]
        cid = row["chunkId"]
        if not (sf.CACHE_ROOT / DATABASE / f"{cid}.npz").is_file():
            print(f"artefact_v3:   edge facets: embedding chunk {seen + 1}/{len(todo)} "
                  f"({cid}, {idx.size} edges)", flush=True)
        got = sf.chunk_sentences(DATABASE, cid, row["locator"], row["relpath"], embed,
                                 row.get("sha256"))
        if got is None:
            log["unresolved"] += 1
            continue
        # cached says the vectors came off the disk, not that a file existed
        vecs, rows, cached, unverified_keys = got
        if set(unverified_keys) & _UNVERIFIABLE_KEYS:
            log["cache_unverified_chunks"] += 1
        log["cached" if cached else "embedded"] += 1
        log["sentences"] += len(vecs)
        sims = prepared.tag_vecs[e_tag[idx]] @ vecs.T
        for r, j in enumerate(idx.tolist()):
            st = sf.aggregate(rows, sf.tag_sentence_mask(sims[r], COS_NOISE))
            if st is None:
                continue
            W[j, cols] = [st[f] for f in sf.STATS]
            per_edge[j] = True
            log["edges"] += 1
        if (seen + 1) % 25 == 0 or seen + 1 == len(todo):
            print(f"artefact_v3:   edge facets: {seen + 1}/{len(todo)} region chunks, "
                  f"{log['cached']} from cache, {log['embedded']} embedded, "
                  f"{log['sentences']} sentences, {log['edges']} edges "
                  f"({time.perf_counter() - t0:.0f}s)", flush=True)
    log["fallback_edges"] = int((in_region[e_chunk] & ~per_edge).sum())
    log["seconds"] = round(time.perf_counter() - t0, 1)
    print(f"artefact_v3:   edge facets: {log['edges']} edges per edge, "
          f"{log['fallback_edges']} fell back to their chunk's value inside the same "
          f"population, {log['cache_unverified_chunks']} chunks read from a cache file whose "
          f"meta could not be checked ({log['seconds']}s)", flush=True)
    return W, log, per_edge


def _retrieve_concept(session, prepared: Prepared, plan: dict, k: int, question: str,
                      keep_all: bool = False, char_budget: Optional[int] = None,
                      doc_cache: Optional[dict] = None) -> tuple:
    """His chain, link by link. Each line: his words, then what the code does.

    THE CHAIN — "it was file -> chunks -> tags. the chunks reference the files, the chunks
      contain a short description of the chunk, a relational weight of the chunk to the file,
      tags with relational values of the tags to the chunk, and then the tags have the
      facet-values too" (07-06); "the combo of query facets vs tagfacets, query tags vs tags
      and then query desc vs chunk desc" (09-02); every link "how strong/relevant is the
      connection for this specific query" (09-02).

    1. PART → TAG — "first you pick a fizzy value for fit of tags via the tag vs querytags
       embeddings … thats how you PICK the tags" (09-06). cos(part, tag), levelled at the tag
       band: fuzzy, "things can be called equal if within a certain range" (09-06).
    2. PART → CHUNK DESCRIPTION — "the chunk descriptions and the tags are supposed to work
       TOGETHER to find gold.. it's a combo" (08-11); "the matching chunks via desc should be
       an AND with the one from the tags, or the ones from the tags gets a math adjustment
       before the facetweights do their thing" (09-07). cos(part, chunk description),
       levelled at the description band. Two readings, both his words, HERB_V3_LINK2; ruled
       2026-09-11 "AND yesAND": and — the connection's level is the AND of the two: the
       worse of its two levels (the fuzzy AND is the minimum of the fits; Zadeh 1965), each
       side counted in its own bands below its best match so the two are on one scale. Two
       different measures stay two measures — never averaged ("thats different scales",
       09-10). adjust — the tag steps alone set the level, and the description steps sort
       first inside it, ahead of the facets. sum — the orchestrator's construction 09-13,
       not his ruling: the two sides' band steps added, the compensatory conjunction in the
       same unit (Salton, Fox & Wu 1983; Fox & Shaw 1994; Lee 1997). product — the
       orchestrator's construction 09-13, not his ruling: the two cosines multiplied before
       anything is counted, the connection levelled at the band of that one product scale
       (the product t-norm; a grown chunk enters at the band steps of the seed's tag cosine
       times its own description cosine, plus the one hop). strength — the orchestrator's
       construction 09-13, not his ruling: the connection is read on the chunk, its closeness
       the SUM over the parts (and the raw question under RAW_PART=on) of that part's best
       tag cosine to the chunk times that part's cosine to the chunk description, levelled at
       the band of that one scale; the chunk enters through the part whose product is
       highest, on that part's best edge, so every inside-level key is unchanged, and a grown
       chunk enters at its seed's level plus the one hop. A COUNT of parts carries nothing
       (measured 09-10 and 09-13) where this sum carries the most (09-13); whether the sum is
       fit, against his 09-10 "a chunk beeing supported by more parts, does not mean it's a
       better fit", is his to rule. Fox & Shaw 1994 (CombSUM).
    3. TAG → CHUNK — "sorting an edge mean you sort the fucking chunk, its the goddamn same"
       (09-06). The unit sorted is the HAS_TAG edge; a chunk takes the place of its first edge.
       HERB_V3_TAGSIDE=nonscope (the orchestrator's construction 09-13, not his ruling) leaves
       the edges whose tag name is a Product node's name out of the candidates: the gate
       already read the product, so that tag is structure read twice.
    4. THE PARTS — "a chunk beeing supported by more parts, does not mean it's a better fit"
       (09-10), and which part matters is measured "in the same way we decide the graph facet
       values" (09-10): rank of cos(part, query description). No count, no sum.
    5. THE FACETS — "how relevant the tag is to the chunk, according to EACH facet, and the
       query part says how much each facet matters for this query" (09-05); "the queryfacets
       is the order of sorting-prio … multi-key sort" (09-05); "how tag is facet to chunk …
       for all facets" (09-08). Per edge: topic is cos(tag, chunk description) ("how central
       is the tag to the topic of the chunk", 09-08); temporal, why, activity, concreteness
       are "the importance or weight of [the facet] in the chunk, AND the tag's relevance to
       the chunk and that combo IS the tag's [facet]" (09-08, said of temporal, ruled for all
       facets 09-08/09-09) — the chunk's statistic AND the tag's relevance to the chunk, the
       worse of the two positions.
       WHICH HALF IS THE TAG'S RELEVANCE (HERB_V3_TAGREL, shape the arm since 2026-09-13) —
       THE ORCHESTRATOR'S CONSTRUCTION, not his ruling. topic: that half is topic's position,
       cos(tag, chunk description) — kept for the on/off measurement, and it is link 3 read a
       second time, so it cannot break what the topic column and the description link already
       tie. shape: the half is the tag's concentration around the chunk in the graph
       (tag_concentration) — the tag's chunks inside this chunk's neighbourhood (the chunk,
       its [:channel] group members, its file-adjacent chunks) over the tag's chunks
       corpus-wide. One ratio for every edge whatever the record kind; the neighbourhood's
       size differs by kind (group median 7 for Slack, adjacency median 2 elsewhere), a
       stated asymmetry. "use the graph shape" (09-13), in the shape of his original third
       facet "sphere, aka realm of interest" (05-07). A ratio of two counts, levelled in its
       own column over the same population as the facet (the clump rule), once per
       (tag, chunk). CONCENTRATION ACTS WHERE THE STATISTICS ARE PER EDGE; ELSEWHERE THE AND
       IS WITH TOPIC — outside the region the four are one chunk number repeated over the
       chunk's edges, and the worse of two grains is not a comparison (the 09-13 review).
       The same position is written into all four columns, so where
       concentration is the worse half on all four the part's facet order reorders nothing;
       the share of region edges that happens on is in meta.facet_layer.concentration.
       Facet 1 is untouched in both: its key is topic's position alone, his 09-08 ruling.
       Each facet is read as its level position inside its own column (the clump rule), so a
       tie is a tie ("let clustering hand me the k", 09-06), strongest first. The interpreter
       also names how much each facet matters for the part — "thats the fucking point of
       weighting the query tags" (09-13); the weight is carried in the plan and in the trace
       and touches no key: where it sits inside a column is open on his record (09-13).
       Sorted in the part's facet order. Under FACET_SOURCE=edge the four statistics are the
       tag's own sentences' inside the chunk, read at query time for the region's chunks
       (region_edge_stats — the orchestrator's construction, 09-13, not his ruling).
       THE QUERY'S WEIGHT ON THE FACETS (HERB_V3_FACETADJ, off today) — HIS CONCEPT, 09-13:
       "thats why we have the interpreter put a value on its tags in relation to the query...
       So we can weight-adjust the facets based on that.."; 06-27: "the facet weight in
       COMBINATION with the tag's chunk relevance weight would tell how relevant the tag
       actually is in relation to the prompt"; 08-23: "the query facetweight, and that is the
       'multiplier' (not actual multiplication, i cant remember what math we decided on as
       weightadjustor here..)". Per part and per edge, the weighted mean of the edge's five
       facet positions under that part's facet weights (facet_relevance) joins the tag side of
       LINK2=strength's closeness: add — the tag cosine plus it; mul — times it. The weighted
       mean and the two joins are the orchestrator's readings, not his ruling and not chosen
       by a score; the description side, the sum over the parts, the band, the levels and the
       walk are untouched.
    6. QUERY DESCRIPTION → CHUNK DESCRIPTION — "query desc vs chunk desc" (09-02); its place
       ruled 09-10: after the facets, before the raw link strength. Levelled at the
       description band.
    7. CHUNK → FILE — "a relational weight of the chunk to the file" (07-06). On this graph
       each of the 30 products' chunks sit in exactly one of the 33 files, so the file is the
       product and is carried by scope; Chunk.relevance_to_file is the 05-13 pilot's
       model-written score (76 values, 0.05–1.0) and stays out: no model writes a number onto
       an edge (09-08).
    REGION (HERB_V3_REGION, shape the arm since 2026-09-13) — "there is 0 fucking use of the
      graph-shape here, actual none" (09-09). tags: the region is what the parts' tags reach.
      shape: the picked tags seed ("thats how you PICK the tags", 09-06) and the graph's shape
      grows the region one hop out — every chunk sharing a [:channel] Channel node with a
      seed. The group node is a relation the graph holds between the chunk and its file ("use
      the graph shape", 09-13); the hop is the unit — no weight, no count, no threshold. A
      grown chunk enters at the worse of its seed's TAG level plus one and its own description
      level, so the hop stands in for the tag side and the description side still ANDs ("AND
      yes AND", 09-11), and its own
      best-fitting edge carries it into the key, every key and band unchanged; where its own
      tags already reach it at that level or nearer, the growth adds nothing.
      shape+cooc: that growth and, beside it, the co-occurrence path — a chunk with a
      chunk→tag→chunk path to a seed through a tag that is not a product name (product names
      are scope, not evidence). Off by default: any threshold on that path is a chosen
      number, his to rule.
      THE SEEDS ARE THE PASS'S OWN, and the growth stays inside the pass's pool — the
      construction, stated. The gate joins its named fields with AND, so a gate narrower than
      a product (product + section, product + years) puts other chunks of the same product
      outside the scope pass; an out-of-scope chunk of that product never seeds or grows an
      in-scope one, and the in-scope pass is walked whole before the out-of-scope pass begins.
    SCOPE — the gate's product / section / years, all named fields together (AND), in-scope
      first (SCOPE_RULE; hard or soft is his open question). HERB_V3_SCOPE_FIELDS=product
      (the orchestrator's construction 09-13, not his ruling) gates on the named product
      alone and drops section and years from the gate. BANDS — how far rephrasing the same need moves a cosine: the raw
      question against the description, the median |difference| over tags (tag band) and over
      chunk descriptions (description band), floored at the embedder's noise (COS_NOISE). The
      raw question is that instrument only; it is not a part (not in his words).
    LOCALITY (HERB_V3_LOCALITY, on since 2026-09-13) — THE ORCHESTRATOR'S CONSTRUCTION, not
      his ruling, built on "use the graph shape" (09-13). Among the chunks the description
      band calls equal, the ones the graph holds near the part's seeds come first. Locality is
      the DISTANCE in hops to the nearest seed of that part, seeds read from the edges of the
      scope pass being walked: 1 file-adjacent to a seed (file_adjacency — consecutive
      messages of one channel, or two parts of one record), 2 sharing a [:channel] group of
      the same product with a seed (grow_region's guard), 3 neither. A seed with another seed
      adjacent or in its group is 0; a seed with none is read by the same rule as any other
      chunk. Nothing is summed: a count of paths stood here until 09-13 and is the "by amount
      of chunks a tag has" ordering he struck (09-08), as a count of parts is the one he
      struck on 09-10. Stated asymmetry, not normalised away: a chunk in no group whose kind
      is one record per chunk — the PRs mostly — is 3 unless a seed sits inside its own
      record; the graph holds no nearness for it. Whether nearness to the seeds is fit at all
      is his to rule.
    KEY per edge, inside a connection level: part rank → reached directly before reached by
      the shape's hop (the hop is provenance, not a number; the orchestrator's construction,
      09-13) → facet positions in the part's order → description-link level → locality
      distance, nearest first (LOCALITY=on) → −tag cosine → chunk id.
    """
    if char_budget is None and k <= 0:
        raise ValueError("k must be positive when no character budget is set")
    if not question.strip():
        raise ValueError("the question text is empty")
    if REGION in ("shape", "shape+cooc") and prepared.shape is None:
        raise RuntimeError(f"HERB_V3_REGION is {REGION!r} but no graph shape was loaded; "
                           f"the shape loads in prepare_over_corpus")
    if TAGREL == "shape" and (prepared.shape is None or prepared.adjacency is None):
        raise RuntimeError("HERB_V3_TAGREL is 'shape' but no graph shape or file adjacency was "
                           "loaded; both load in prepare_over_corpus")
    if LOCALITY == "on" and (prepared.shape is None or prepared.adjacency is None):
        raise RuntimeError("HERB_V3_LOCALITY is 'on' but no graph shape or file adjacency was "
                           "loaded; both load in prepare_over_corpus")
    parts = [p for p in plan["parts"] if isinstance(p, dict) and p.get("t")]
    description = plan.get("description") or question
    if not parts:
        parts = [{"t": description, "order": list(prepared.facets)}]
    probes = [description, question] + [_readable(p["t"]) for p in parts]
    qmat, calls, tok_in, tok_out, secs = _embed_cached(probes, "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)
    vecs = [_unit(np.asarray([float(x) for x in row], dtype=np.float64)) for row in qmat]
    desc_vec, raw_vec, part_vecs = vecs[0], vecs[1], vecs[2:]
    if RAW_PART == "on":
        # the raw question beside the parts, as _retrieve_combo reads it: its facet order is
        # the key order and it names no weights; the bands above are unchanged
        parts = parts + [{"t": question, "order": list(prepared.facets)}]
        part_vecs = part_vecs + [raw_vec]
    layout = prepared.facets
    e_tag, e_chunk = prepared.edge_tag, prepared.edge_chunk
    n = len(prepared.chunk_ids)

    # bands (the instrument)
    if BAND_RULE == "paraphrase":
        tag_band = float(np.median(np.abs(prepared.tag_vecs @ desc_vec - prepared.tag_vecs @ raw_vec)))
        desc_band = paraphrase_band(prepared.chunk_vecs, desc_vec, raw_vec)
    else:
        tag_band = desc_band = COS_NOISE
    # a band below what the embedder can tell apart is no band (review 09-11, P4)
    tag_band, desc_band = max(tag_band, COS_NOISE), max(desc_band, COS_NOISE)
    # LINK2=product: the two ends multiply, so the band is measured on that one scale — the
    # median over edges of how far rephrasing the same need moves the product itself
    prod_band = COS_NOISE
    if LINK2 == "product":
        if BAND_RULE == "paraphrase":
            td, tr = prepared.tag_vecs @ desc_vec, prepared.tag_vecs @ raw_vec
            cd, cr = prepared.chunk_vecs @ desc_vec, prepared.chunk_vecs @ raw_vec
            prod_band = float(np.median(np.abs(td[e_tag] * cd[e_chunk] - tr[e_tag] * cr[e_chunk])))
        prod_band = max(prod_band, COS_NOISE)

    # 6: query description → chunk description
    d2d_lvl = band_steps(prepared.chunk_vecs @ desc_vec, desc_band)

    # 4: parts by centrality
    centrality = [float(pv @ desc_vec) for pv in part_vecs]
    part_rank = {pi: r for r, pi in enumerate(sorted(range(len(parts)), key=lambda i: (-centrality[i], i)))}

    # scope — a gate that names fields but reaches no chunk of this corpus is the no-scope
    # case, never the whole corpus: the region would be every chunk (the 09-13 review)
    in_scope = np.ones(n, dtype=bool)
    scope_ids, gate_named = (set(), [])
    if SCOPE_RULE != "off":
        scope_ids, gate_named = scope_chunks(session, _parse_gate(plan.get("gate")),
                                             join=SCOPE_JOIN.upper())
        if scope_ids:
            in_scope = np.fromiter((c in scope_ids for c in prepared.chunk_ids), dtype=bool, count=n)
    scope_named = list(gate_named)
    if not in_scope.any() or not scope_ids:
        in_scope = np.ones(n, dtype=bool)
        scope_named = []
    no_scope_reason = ("scope rule off" if SCOPE_RULE == "off"
                       else "no stated scope" if not gate_named
                       else "gate matched no chunk" if not scope_named else None)
    edge_in = in_scope[e_chunk]
    passes = ([np.ones(len(e_chunk), dtype=bool)] if not scope_named
              else ([edge_in] if SCOPE_RULE == "cut" else [edge_in, ~edge_in]))
    tagside = None
    if TAGSIDE == "nonscope":
        if prepared.shape is None:
            raise RuntimeError("HERB_V3_TAGSIDE is 'nonscope' but no graph shape was loaded; "
                               "the product names load in prepare_over_corpus")
        keep = ~prepared.shape["product_tag"][e_tag]
        lost = 0
        for mi, m in enumerate(passes):
            had = np.zeros(n, dtype=bool)
            had[e_chunk[m]] = True
            passes[mi] = m & keep
            left = np.zeros(n, dtype=bool)
            left[e_chunk[passes[mi]]] = True
            if mi == 0:
                lost = int((had & ~left).sum())
        tagside = {"knob": TAGSIDE, "edges_dropped": int((~keep).sum()),
                   "product_tags": int(prepared.shape["product_tag"].sum()),
                   "chunks_without_nonproduct_edge": lost}
        print(f"artefact_v3:   tag side: {int((~keep).sum())} of {len(e_tag)} edges carry a "
              f"product name; {lost} chunks of this pool have no non-product edge left",
              flush=True)

    # the region — the scoped pool the walk ranks; FACET_SOURCE=edge reads the four
    # statistics on the tag's own sentences for these chunks only, at query time
    edge_stats = None
    W_q = None
    region_edges = None
    global _NO_SCOPE_QUESTIONS
    if FACET_SOURCE == "edge":
        if not scope_named:
            _NO_SCOPE_QUESTIONS += 1
            print(f"artefact_v3:   edge facets: {no_scope_reason}, so there is no region to read "
                  "the tag's own sentences in; the chunk-level statistics stand for this "
                  'question ("embed the entire corpus … is retarded", 09-09)', flush=True)
            edge_stats = {"chunks": 0, "reason": no_scope_reason,
                          "no_scope_questions": _NO_SCOPE_QUESTIONS}
        else:
            has_edge = np.zeros(n, dtype=bool)
            has_edge[e_chunk] = True
            in_region = in_scope & has_edge
            sent_usage = ModelUsage()
            W_q, edge_stats, region_edges = region_edge_stats(
                prepared, in_region,
                lambda texts: _embed_passage(texts, usage, sent_usage))
            edge_stats["embed_seconds"] = round(sent_usage.time_s, 1)
            edge_stats["no_scope_questions"] = _NO_SCOPE_QUESTIONS

    # 5: facet positions per edge, per part — the column's direction is the distance from the
    #    part's weight for that facet; topic, and every other facet AND topic
    ti = layout.index("topic") if "topic" in layout else None
    # the weights are carried and ignored inside a column (09-13 open), so one matrix serves
    # every part. ONE POPULATION PER SCOPE PASS (the 09-13 review): under FACET_SOURCE=edge
    # every pass-1 edge is levelled together — per-edge values where the tag's sentences
    # resolved, the chunk's own values for the fallbacks — and pass 2's edges, chunk-level
    # throughout, are levelled over themselves once per chunk. The walk reads the two in two
    # scope passes and never compares them.
    per_edge_region = FACET_SOURCE == "edge" and region_edges is not None
    # FACET_SOURCE=file carries a value per edge on every edge, so the four columns are per
    # edge for the whole pool and the concentration half applies by the same rule
    per_edge_facets = per_edge_region or FACET_SOURCE == "file"
    # concentration is inert unless the statistics are read per edge: with no per-edge region
    # the AND is topic's position everywhere (step 4), so the layer is not built at all.
    # It is built on first need and its seconds are booked as prepare, not as this question's
    # search (the 09-13 review): the ratio reads the corpus, not the question.
    prepare_s = 0.0
    conc = None
    if TAGREL == "shape" and per_edge_facets:
        t_conc = time.perf_counter()
        conc = tag_concentration(prepared)
        prepare_s += time.perf_counter() - t_conc
    # CONCENTRATION ACTS OVER EVERY PASS-1 EDGE (the 09-13 review): it is a ratio of two chunk
    # counts the graph holds for every edge, whether or not the tag's sentences resolved, so
    # the fallback edges are read by the same rule as their neighbours. Pass 2's four columns
    # are one chunk number repeated over the chunk's edges, a different grain from a per
    # (tag, chunk) ratio, so there the AND stays topic's position, as in step 4.
    # The value is generated once per (tag, neighbourhood), and the neighbourhood is the
    # chunk's: the column is levelled once per (tag, chunk) and broadcast back to the edges.
    conc_unit = (None if conc is None else
                 prepared.edge_tag.astype(np.int64) * n + prepared.edge_chunk.astype(np.int64))
    pass1 = passes[0]
    if W_q is None:
        t_cols = time.perf_counter()
        P_base = facet_positions(prepared, None)
        prepare_s += time.perf_counter() - t_cols
        # under file the four columns are per edge, so the concentration half acts on the
        # pass-1 edges exactly as it does inside a per-edge region
        rel_pos = (None if conc is None else column_positions(conc, pass1, conc_unit))
    else:
        # what generated each of the four statistics: the edge where the tag's sentences
        # resolved, the chunk where they did not — so the clump rule's chance test counts a
        # chunk-level value once and not once per edge that repeats it
        stat_unit = np.where(region_edges,
                             n + np.arange(len(e_chunk), dtype=np.int64),
                             e_chunk.astype(np.int64))
        P_base = facet_positions(prepared, None, W=W_q, rows=pass1, per_edge=True,
                                 unit=stat_unit)
        P_out = facet_positions(prepared, None, W=W_q, rows=~pass1)
        P_base = np.where(pass1[:, None], P_base, P_out)
        rel_pos = (None if conc is None else
                   column_positions(conc, pass1, conc_unit))
    conc_layer = None if conc is None else {
        "distinct": int(np.unique(np.round(conc, 6)).size),
        "share_one": round(float(np.mean(conc == 1.0)), 4),
        "median": round(float(np.median(conc)), 4)}
    if conc_layer is not None:
        # the AND writes one concentration position into all four columns, so where it is the
        # worse position on all four the facets read identically and the part's facet order
        # reorders nothing. That is the construction (one tag-relevance half for every facet,
        # his 09-08 13:02); the share it happens on is measured, not hidden.
        others = [] if ti is None else [fi for fi in range(len(layout)) if fi != ti]
        # concentration acts on the pass-1 edges, so the share is measured there
        measured = (np.zeros(len(conc), dtype=bool) if rel_pos is None else pass1)
        conc_layer["collapse_edges"] = int(measured.sum())
        conc_layer["collapse_share"] = None
        if others and measured.any() and rel_pos is not None:
            collapsed = np.all(rel_pos[:, None] >= P_base[:, others], axis=1) & measured
            conc_layer["collapse_share"] = round(float(collapsed.sum() / measured.sum()), 4)

    def positions(part: dict) -> np.ndarray:
        P = P_base
        pos = P.copy()
        if ti is not None:
            # on the pass-1 edges the other half is the tag's concentration; on pass 2, where
            # the four are chunk-level, the AND is with topic (step 4)
            other = (P[:, ti] if rel_pos is None
                     else np.where(pass1, rel_pos, P[:, ti]))
            for fi in range(len(layout)):
                if fi != ti:
                    pos[:, fi] = np.maximum(P[:, fi], other)
        return pos

    # HERB_V3_FACETADJ — HIS CONCEPT, 2026-09-13: "thats why we have the interpreter put a
    # value on its tags in relation to the query... So we can weight-adjust the facets based
    # on that.."; the weighted mean and the two joins are the orchestrator's readings of
    # "weight-adjust" (08-23 "not actual multiplication, i cant remember what math we decided
    # on as weightadjustor here.."), neither chosen by a score.
    rel = rel_eq = None
    facetadj = {"knob": FACETADJ}
    if FACETADJ != "off":
        rel = [facet_relevance(P_base, layout, facet_weights(part, layout)) for part in parts]
        # the band's two probes are the description and the raw question, neither of which
        # names facet weights, so their relevance is the five read equal
        rel_eq = facet_relevance(P_base, layout, None)
        pop = region_edges if region_edges is not None else pass1
        vals = np.concatenate([r[pop] for r in rel]) if pop.any() else np.zeros(0)
        facetadj.update(
            {"population": "region edges" if region_edges is not None else "pass-1 edges",
             "edges": int(pop.sum()), "parts": len(parts),
             "median": round(float(np.median(vals)), 4) if vals.size else None,
             "share_zero": round(float(np.mean(vals == 0.0)), 4) if vals.size else None,
             "share_one": round(float(np.mean(vals == 1.0)), 4) if vals.size else None})
        print(f"artefact_v3:   facet adjust ({FACETADJ}): rel over {facetadj['edges']} "
              f"{facetadj['population']} x {len(parts)} parts, median {facetadj['median']}, "
              f"{facetadj['share_zero']} at 0, {facetadj['share_one']} at 1", flush=True)

    # LINK2=strength: the closeness is one number on the chunk, so the band is measured on
    # that one scale — the median over chunks of how far rephrasing the same need moves the
    # closeness itself: the description as the whole probe set against the raw question as the
    # whole probe set, over the edges the tag side keeps. It is read through the same closeness
    # the walk levels, FACETADJ included, so the band stays on the scale it bands.
    strength_band = COS_NOISE
    if LINK2 == "strength":
        kept_rows = keep if TAGSIDE == "nonscope" else np.ones(len(e_chunk), dtype=bool)
        if BAND_RULE == "paraphrase":
            one = None if rel_eq is None else [rel_eq]
            s_desc = chunk_strength(prepared, [desc_vec], rows=kept_rows, comb=PARTCOMB,
                                    rel=one, adj=FACETADJ)[0]
            s_raw = chunk_strength(prepared, [raw_vec], rows=kept_rows, comb=PARTCOMB,
                                   rel=one, adj=FACETADJ)[0]
            strength_band = float(np.median(np.abs(s_desc - s_raw)))
        strength_band = max(strength_band, COS_NOISE)

    # 1 + 2: the connection level per part, the AND of the tag level and the description level
    # the distance from a chunk to the part's seeds — hops the graph holds, never a count
    if LOCALITY == "on":
        g_ptr, g_of = prepared.shape["chunk_group_ptr"], prepared.shape["chunk_groups"]
        g_owner = np.repeat(np.arange(n, dtype=np.int64), np.diff(g_ptr))
        a_ptr, a_of = prepared.adjacency["ptr"], prepared.adjacency["members"]
        a_owner = np.repeat(np.arange(n, dtype=np.int64), np.diff(a_ptr))
        prod = prepared.shape["product"] + 1     # no product is its own class
        n_prod = int(prod.max()) + 1
        gp_of = g_of * n_prod + prod[g_owner]    # group AND product — grow_region's guard
        n_gp = (len(prepared.shape["group_ptr"]) - 1) * n_prod

    def locality_of(is_seed: np.ndarray) -> np.ndarray:
        """hops to the nearest seed of this part: 1 file-adjacent to a seed, 2 sharing a
        [:channel] group of the same product with a seed (grow_region's guard), 3 neither.
        A seed with another seed adjacent or in its group is 0; a seed with none is read by
        the same rule as any other chunk, so it lands where its own neighbours put it.
        Asymmetry, stated and not normalised away: a chunk in no group whose kind is one
        record per chunk — the PRs mostly — is 3 unless a seed sits inside its own record;
        the graph holds no nearness for it."""
        seed_f = is_seed.astype(np.float64)
        adj = np.bincount(a_owner, weights=seed_f[a_of], minlength=n) > 0.5
        per_gp = np.bincount(gp_of, weights=seed_f[g_owner], minlength=n_gp)
        grouped = np.bincount(g_owner, weights=per_gp[gp_of], minlength=n)
        grouped -= seed_f * np.diff(g_ptr)       # the chunk is not its own neighbour
        grp = grouped > 0.5
        d = np.full(n, 3, dtype=np.int64)
        d[grp] = 2
        d[adj] = 1
        d[is_seed & (adj | grp)] = 0
        return d

    conn_lvl, tag_cos, part_order, log, desc_steps, edge_pos, tag_lvl = [], [], [], [], [], [], []
    desc_cos, prod_ref = [], []
    for pi, (part, vec) in enumerate(zip(parts, part_vecs)):
        ts = prepared.tag_vecs @ vec
        ds = prepared.chunk_vecs @ vec
        t_lvl = band_steps(ts, tag_band)
        d_lvl = band_steps(ds, desc_band)
        pe = ts[e_tag] * ds[e_chunk]
        desc_cos.append(ds)
        prod_ref.append(float(pe.max()) if pe.size else 0.0)
        lv = (np.maximum(t_lvl[e_tag], d_lvl[e_chunk]) if LINK2 == "and"
              else t_lvl[e_tag] + d_lvl[e_chunk] if LINK2 == "sum"
              else band_steps(pe, prod_band) if LINK2 == "product"
              else t_lvl[e_tag])
        conn_lvl.append(lv)
        tag_lvl.append(t_lvl)
        desc_steps.append(d_lvl)
        tag_cos.append(ts)
        part_order.append(facet_order(part, layout))
        edge_pos.append(positions(part))
        row = {"part": part["t"], "centrality": round(centrality[pi], 4), "rank": part_rank[pi],
               "facet_order": list(part_order[-1]),
               "facet_weights": facet_weights(part, layout),
               "tag_levels": int(t_lvl.max()) + 1,
               "desc_levels": int(d_lvl.max()) + 1, "level0_edges": int((lv == 0).sum())}
        log.append(row)

    # the walk: connection levels nearest first, all parts together, each level sorted by the key
    seen: set = set()
    rows: list = []
    walk = []
    done = False

    def key_of(pi: int, j: int, c: int, from_shape: bool) -> tuple:
        fpos = edge_pos[pi][j]
        return ((part_rank[pi], int(from_shape))
                + ((int(desc_steps[pi][c]),) if LINK2 == "adjust" else ())
                + tuple(float(fpos[layout.index(f)]) for f in part_order[pi])
                + (int(d2d_lvl[c]),)
                + ((int(locality[pi][c]),) if LOCALITY == "on" else ())
                + (-float(tag_cos[pi][e_tag[j]]), prepared.chunk_ids[c]))

    locality: list = [None] * len(parts)
    grow_lvl: list = [None] * len(parts)
    rep_edge: list = [None] * len(parts)
    grow_t0, grow_loud = time.perf_counter(), False
    strength_log: list = []
    for walk_pass, mask in enumerate(passes):
        if done:
            break
        # ONE SEED SET PER PASS (the 09-13 review): the chunks this pass's own edges reach at
        # tag level 0 — the band below the best match, his 09-06 "thats how you PICK the tags".
        # The shape grows out of that set and the distance is read to that set; growth and
        # locality are never two different sets, and both live inside the pool the pass walks.
        c_lvl = None
        if LINK2 == "strength":
            # the connection on the chunk: the sum over the parts of best tag cosine x
            # description cosine, over this pass's edges, levelled at the strength band. The
            # chunk enters through the part whose product is highest, on that part's best
            # edge, so every key inside the level is the key it already was.
            closeness, s_part, s_edge = chunk_strength(prepared, part_vecs, rows=mask,
                                                       comb=PARTCOMB, rel=rel, adj=FACETADJ)
            has_edge = np.zeros(n, dtype=bool)
            has_edge[e_chunk[mask]] = True
            c_lvl = np.full(n, -1, dtype=np.int64)
            if has_edge.any():
                c_lvl[has_edge] = band_steps(closeness[has_edge], strength_band)
            far = np.iinfo(np.int64).max
            for pi in range(len(parts)):
                lv = np.full(len(e_chunk), far, dtype=np.int64)
                take = has_edge & (s_part == pi)
                lv[s_edge[take]] = c_lvl[take]
                conn_lvl[pi] = lv
            strength_log.append({"pass": walk_pass, "chunks": int(has_edge.sum()),
                                 "levels": int(c_lvl.max()) + 1,
                                 "level0_chunks": int((c_lvl == 0).sum()),
                                 "entered_by_part": {str(pi): int((has_edge & (s_part == pi)).sum())
                                                     for pi in range(len(parts))}})
        max_level = (int(c_lvl.max()) if c_lvl is not None
                     else max(int(lv.max()) for lv in conn_lvl))
        for pi in range(len(parts)):
            t_lvl = tag_lvl[pi]
            is_seed = np.zeros(n, dtype=bool)
            is_seed[e_chunk[(t_lvl[e_tag] == 0) & mask]] = True
            seeds = np.flatnonzero(is_seed)
            if LOCALITY == "on":
                locality[pi] = locality_of(is_seed)
                log[pi].setdefault("locality", []).append(
                    {"pass": walk_pass, "seeds": int(seeds.size),
                     "distances": {str(d): int((locality[pi] == d).sum()) for d in (0, 1, 2, 3)}})
            # REGION=shape: the picked tags seed, the graph's shape grows one hop out
            rep = np.full(n, -1, dtype=np.int64)
            grown = np.full(n, -1, dtype=np.int64)
            if REGION in ("shape", "shape+cooc"):
                at = np.flatnonzero(mask)
                cos_e = tag_cos[pi][e_tag[at]]
                by_chunk = at[np.lexsort((-cos_e, e_chunk[at]))]
                first = np.ones(len(by_chunk), dtype=bool)
                first[1:] = e_chunk[by_chunk[1:]] != e_chunk[by_chunk[:-1]]
                rep[e_chunk[by_chunk[first]]] = by_chunk[first]
                # a seed hangs out at its TAG level, the band steps of its best tag inside this
                # pass, so the hop carries the tag side alone
                best_tag = np.full(n, np.iinfo(np.int64).max, dtype=np.int64)
                np.minimum.at(best_tag, e_chunk[mask], t_lvl[e_tag[mask]])
                best_tag_cos = None
                if LINK2 == "product":
                    best_tag_cos = np.full(n, 0.0)
                    np.maximum.at(best_tag_cos, e_chunk[mask], tag_cos[pi][e_tag[mask]])
                # under strength the seed hangs out at its own chunk level, and the hop puts
                # the grown chunk one level below it
                grown, by_group, by_cooc, seed_val = grow_region(
                    prepared, seeds,
                    c_lvl[seeds] if LINK2 == "strength" else best_tag[seeds],
                    None if best_tag_cos is None else best_tag_cos[seeds])
                if not grow_loud and time.perf_counter() - grow_t0 > 1.0:
                    grow_loud = True
                if grow_loud:
                    print(f"artefact_v3:   region: pass {walk_pass + 1}/{len(passes)}, part "
                          f"{pi + 1}/{len(parts)}, {seeds.size} seeds "
                          f"({time.perf_counter() - grow_t0:.0f}s)", flush=True)
                # the hop stands in for the tag side; the description side still ANDs ("AND yes
                # AND", 09-11), so a grown chunk cannot enter above its own description level
                # under sum the two sides add: a seed's tag steps are 0, the hop is 1, and
                # the grown chunk's own description steps come on top (1 + d_lvl)
                # under product the hop carries the seed's tag cosine and the grown chunk
                # brings its own description cosine: it enters at the band steps of that
                # product, plus the one hop
                if LINK2 == "product":
                    reach = grown >= 0
                    v = np.where(reach, np.nan_to_num(seed_val) * desc_cos[pi], prod_ref[pi])
                    steps = np.floor((prod_ref[pi] - v) / prod_band + 1e-12).astype(np.int64)
                    grown = np.where(reach, np.maximum(steps, 0) + 1, -1)
                elif LINK2 == "strength":
                    pass    # grow_region already put it at the seed's level + 1
                else:
                    grown = np.where(grown >= 0,
                                     (grown + desc_steps[pi]) if LINK2 == "sum"
                                     else np.maximum(grown, desc_steps[pi]), -1)
                grown[seeds] = -1   # a seed is reached by its own tags, not by the shape
                by_group[seeds] = False
                by_cooc[seeds] = False
                # only a chunk with a representative edge can enter the walk; the rest are
                # grown by the shape and carried by nothing
                has_rep = rep >= 0
                log[pi].setdefault("region", []).append(
                    {"pass": walk_pass, "seeds": int(seeds.size),
                     "grown_group_only": int((by_group & ~by_cooc & has_rep).sum()),
                     "grown_cooc_only": int((by_cooc & ~by_group & has_rep).sum()),
                     "grown_both": int((by_group & by_cooc & has_rep).sum()),
                     "grown": int(((by_group | by_cooc) & has_rep).sum()),
                     "grown_no_edge": int(((by_group | by_cooc) & ~has_rep).sum())})
            grow_lvl[pi] = grown
            rep_edge[pi] = rep
            if grown.size and grown.max() >= 0:
                max_level = max(max_level, int(grown.max()))
        for L in range(max_level + 1):
            cand = []
            at_of = [np.flatnonzero((conn_lvl[pi] == L) & mask) for pi in range(len(parts))]
            own = {int(e_chunk[j]) for at in at_of for j in at}
            for pi in range(len(parts)):
                for j in at_of[pi]:
                    cand.append((key_of(pi, int(j), int(e_chunk[j]), False), int(j), pi, False))
                # the shape's hop: a chunk hanging off a seed at this level. Its own
                # best-fitting edge carries it into the key — the hop is the unit and adds
                # no number of its own; it counts as from the shape only where no part's
                # own edges reach it at this level
                for c in np.flatnonzero(grow_lvl[pi] == L).tolist():
                    j = int(rep_edge[pi][c])
                    if j < 0 or not mask[j]:
                        continue
                    from_shape = c not in own
                    cand.append((key_of(pi, j, c, from_shape), j, pi, from_shape))
            if not cand:
                continue
            cand.sort(key=lambda x: x[0])
            fresh = 0
            grown_rows = 0
            for key, j, pi, from_shape in cand:
                c = int(e_chunk[j])
                cid = prepared.chunk_ids[c]
                if cid in seen:
                    continue
                seen.add(cid)
                fresh += 1
                grown_rows += int(from_shape)
                row = {**prepared.chunk_rows[c], "tag": prepared.tag_names[e_tag[j]], "fit": L,
                       "grown": bool(from_shape),
                       "locality": (int(locality[pi][c]) if LOCALITY == "on" else None)}
                rows.append(row)
            walk.append({"level": L, "pass": walk_pass, "edges": len(cand), "new": fresh,
                         "new_from_shape": grown_rows})
            # his rule, 2026-09-13: the region's levels are the arm's stop; the 72,000-char
            # cut is the harness's, applied after the full order
            if char_budget is None and len(rows) >= k:
                done = True
                break
    if not rows:
        raise RuntimeError("no connection of any part reaches a chunk")
    if char_budget is None and not keep_all:
        rows = rows[:k]
    selected = [{f: r[f] for f in ("chunkId", "locator", "relpath", "sha256")}
                | {"tag": r["tag"], "fit": r["fit"], "grown": r["grown"]}
                for r in rows]
    meta = {
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "sort": {"mode": "concept", "link2": LINK2, "tagside": tagside, "raw_part": RAW_PART, "tag_band": round(tag_band, 5), "desc_band": round(desc_band, 5),
                 **({"prod_band": round(prod_band, 5)} if LINK2 == "product" else {}),
                 **({"strength_band": round(strength_band, 6), "partcomb": PARTCOMB,
                     "strength": strength_log, "facetadj": FACETADJ}
                   if LINK2 == "strength" else {}),
                 "desc_link_levels": int(d2d_lvl.max()) + 1, "region": REGION,
                 "rows_from_shape": int(sum(1 for r in rows if r["grown"])),
                 "shape": (None if prepared.shape is None else
                           {key: prepared.shape[key] for key in
                            ("channels", "chunk_channel_edges", "chunks_with_channel",
                             "products", "product_tags")})},
        "parts": log,
        "walk": walk,
        "retrieved": len(selected),
        "scope": {"rule": SCOPE_RULE, "named": scope_named, "gate_named": gate_named,
                  "chunks": len(scope_ids), "join": SCOPE_JOIN, "fields": SCOPE_FIELDS},
        "facet_layer": {"source": FACET_SOURCE, "overlay": prepared.overlay,
                        "edge_stats": edge_stats,
                        # corpus-wide work this question paid for: booked as prepare, out of
                        # search_time_s (the 09-13 review)
                        "prepare_seconds": round(prepare_s, 2),
                        "tag_relevance": (TAGREL if per_edge_facets
                                          else "topic (no per-edge facet values)"),
                        "concentration": conc_layer,
                        "facetadj": facetadj,
                        "locality": ({"knob": LOCALITY} if LOCALITY == "off" else
                                     {"knob": LOCALITY,
                                      "pairs": prepared.adjacency["pairs"],
                                      "pairs_by_kind": prepared.adjacency["per_kind"],
                                      "located": prepared.adjacency["located"],
                                      "rows": [int(r["locality"]) for r in rows],
                                      "walked": _distance_block([int(r["locality"]) for r in rows])})},
        "ranking": {"chunk_ids": [r["chunkId"] for r in rows],
                    "grown": [bool(r["grown"]) for r in rows]},
    }
    return selected, usage, meta


# ------------------------------------------------ the forum modes (multirank / weighted, 09-21)
#
# Built to output/research/2026-09-21-forum/SPEC.md as SPEC-v2.md supersedes it, on his /goal of
# 2026-09-21 ("have a forum amongst the agents, build the weightend and the multiranked").
# Nothing here is chosen by a score and nothing here is his ruling except where a sentence of
# his is quoted beside it; every construction is carried into meta["unruled"] with its default.
#
# THE PICK (SPEC-v2 S2) — the tag side alone: "first you pick a fizzy value for fit of tags via
#   the tag vs querytags embeddings, right? thats how you PICK the tags, when the tags are
#   picked, how do we decide which matters for this query?" (09-06). pick level = band steps of
#   cos(part, tag) below the part's best tag, at the arm's HERB_V3_BAND rule. The 45 tags that
#   carry a Product node's name are not candidates (names are structure, 09-14). The walk opens
#   pick levels 0, 1, 2, … to the end; no k; the 72,000-character cut is the harness's (09-13).
#   The 09-11 AND is NOT the level here — under it the pools hold 0 or 1 edge (PICK-POOLS.md).
# THE POOL (SPEC-v2 S3) — every mode-key level is computed over the candidate edges of one pick
#   level of one part inside one scope pass. A chunk enters at the first edge the walk reaches
#   it on (first arrival).
# THE LEVEL RULE (SPEC-v2 S5) — steps below the pool's best, floor((max_P v - v) / delta), one
#   scale for every column. No clump rule, no chaining, no fixed grid, no cross-column maximum.
# SCOPE (SPEC-v2 S4) — the walk's two passes, in-scope first, both walked to the end; never a
#   gate, never a key ("you fucking do NOT know that information beforehand", 09-14).

def pool_steps(values: np.ndarray, band: float) -> np.ndarray:
    """the level rule of both forum modes: steps below the pool's best, 0 the strongest.

    L(x) = floor((max_P v - v(x)) / band) over the pool P (SPEC-v2 S5, the arm's own band_steps
    convention). An empty gap stays levels: a pool whose second value sits 20 bands below its
    best gives that value level 20, which is what chaining would fold to 1.
    NaN (SPEC-v2 S5): a NaN never enters max_P, takes the pool's worst level + 1, and an
    all-NaN column is one level."""
    v = np.asarray(values, dtype=np.float64).ravel()
    lv = np.zeros(v.size, dtype=np.int64)
    if v.size == 0:
        return lv
    if not (band > 0):
        raise ValueError(f"the band must be positive, got {band!r}")
    ok = ~np.isnan(v)
    if not ok.any():
        return lv                      # an all-NaN column is one level
    if not np.isfinite(band):
        # an infinite band is no band: the column vanishes and cannot order anything, so a
        # missing value is not demoted either — every row of the pool is level 0
        return lv
    lv[ok] = np.floor((v[ok].max() - v[ok]) / band + 1e-12).astype(np.int64)
    if not ok.all():
        lv[~ok] = int(lv[ok].max()) + 1
    return lv


def weighted_g(S: np.ndarray, w: np.ndarray, beta: np.ndarray) -> tuple:
    """g(e) = sum_f w_f * b_f * (s_f(e) - median_f(P)) over the four columns (SPEC-v2 §3).

    The median is the stated origin: with one weight vector over a pool it changes no order,
    and it makes the value defined if the weights ever become per tag. A NaN term is dropped
    and counted; an edge whose four terms are all NaN is NaN.
    Returns (g, dropped terms, all-NaN rows)."""
    S = np.asarray(S, dtype=np.float64)
    if S.ndim != 2:
        raise ValueError(f"S must be [m, facets], got {S.shape}")
    m, nf = S.shape
    g = np.zeros(m, dtype=np.float64)
    used = np.zeros(m, dtype=np.int64)
    dropped = 0
    for f in range(nf):
        col = S[:, f]
        ok = ~np.isnan(col)
        dropped += int((~ok).sum())
        if not ok.any():
            continue
        g[ok] += float(w[f]) * float(beta[f]) * (col[ok] - float(np.median(col[ok])))
        used[ok] += 1
    allnan = used == 0
    g = np.where(allnan, np.nan, g)
    return g, dropped, int(allnan.sum())


def bounded_r(topic: np.ndarray, g: np.ndarray, delta_topic: float) -> np.ndarray:
    """the bounded adjust (SPEC-v2 §3, HERB_V3_ADJUST=bounded):
    r(e) = cos_topic(e) + delta_topic * (g(e) - min_P g) / (max_P g - min_P g).

    "the 'main weight' on a tag, is the topic one, and the others adjust that weight depending
    on the relevance of a facet to the query" (his, 09-18). The most the facets can move an edge
    is topic's own band, so a topic difference wider than the band is never overturned. The
    second term is 0 when the pool's g is constant or NaN."""
    t = np.asarray(topic, dtype=np.float64).ravel()
    gg = np.asarray(g, dtype=np.float64).ravel()
    add = np.zeros(t.size, dtype=np.float64)
    ok = ~np.isnan(gg)
    if ok.any() and np.isfinite(delta_topic) and delta_topic > 0:
        lo, hi = float(gg[ok].min()), float(gg[ok].max())
        if hi > lo:
            add[ok] = delta_topic * (gg[ok] - lo) / (hi - lo)
    return t + add


def roc_weights(n: int) -> list:
    """rank-order centroid weights for n ranked places (Barron & Barrett 1996): the centroid of
    every weight vector consistent with the stated order, so the order alone gives the
    magnitudes and no number is chosen."""
    return [sum(1.0 / k for k in range(i + 1, n + 1)) / n for i in range(n)]


def part_facet_weights(part: dict, layout: tuple) -> tuple:
    """the four non-topic weights for one part, and where they came from (HERB_V3_W).

    cached: the order interpreter's own per-part weights — NOT his 09-14 per-tag object, which
    would cost a querytagger prompt rewrite and one model call per question. Topic's cached
    weight is unused: topic is not an addend."""
    four = tuple(f for f in layout if f != "topic")
    if W_RULE == "equal":
        return {f: 1.0 for f in four}, "equal"
    if W_RULE == "zero":
        return {f: 0.0 for f in four}, "zero"
    if W_RULE == "roc":
        order = [f for f in facet_order(part, layout) if f != "topic"]
        roc = roc_weights(len(order))
        return {f: roc[i] for i, f in enumerate(order)}, "roc"
    cached = facet_weights(part, layout)
    if cached is None:
        return {f: 1.0 for f in four}, "equal (the part carries no cached weights)"
    return {f: float(cached[f]) for f in four}, "cached"


def load_record_kinds(session, chunk_ids: list) -> list:
    """the record kind of every chunk, read off the Kind node the graph hangs it on. REPORTED,
    never a key and never normalised away: whether a facet column that reads as a record kind
    is fit is his to rule (SPEC §8.10)."""
    at = {c: i for i, c in enumerate(chunk_ids)}
    kinds = [None] * len(chunk_ids)
    for rec in session.run("MATCH (c:Chunk)-[:kind]->(k:Kind) "
                           "RETURN c.chunk_id AS chunkId, k.name AS kind"):
        i = at.get(rec["chunkId"])
        if i is not None:
            kinds[i] = rec["kind"]
    return kinds


_BANDS: dict = {}


_BAND_MODULE = None


def _bootstrap_module():
    """the band's estimator and its pair samplers, loaded BY FILE PATH from the module the
    bootstrap run reads them from (`bootstrap_band.py`, which `bootstrap_scores.py`
    re-exports), so the arm reproduces that run's BANDS.md exactly.

    Loaded by path on purpose: `test/graph/facet_pairs/` holds `data.py`, `model.py`,
    `train.py` and `evaluate.py`, and putting it on the front of sys.path would shadow those
    names for the whole process. The module imports numpy and nothing else, so no torch is
    pulled into the arm."""
    global _BAND_MODULE
    if _BAND_MODULE is None:
        import importlib.util as _util
        path = _ROOT / "test" / "graph" / "facet_pairs" / "bootstrap_band.py"
        if not path.is_file():
            raise RuntimeError(f"the band's estimator is read from {path}, which does not exist")
        spec = _util.spec_from_file_location("herb_bootstrap_band", path)
        mod = _util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _BAND_MODULE = mod
    return _BAND_MODULE


def load_retrain_bands() -> dict:
    """the band of the four head columns, from the stored bootstrap score matrices.

    SPEC-v2 S6: ONE pooled band for the four — two independent retrain sets disagree on which
    column is the tightest, so a per-column band would be reading noise. The band is
    `flip_gap` at rate 0.05 on grid 0.01 (bootstrap_scores.py): the smallest score difference
    whose sign survives refitting the round-1 head on resampled judgements in more than 95% of
    24 draws. The pairs are the fixed-seed same-chunk sample — two tags of one chunk, which is
    the comparison the pool actually makes.
    Nothing here reads the known topic values, the questions or any gold."""
    key = (BOOTSTRAP_NPZ, BAND_PAIR_SAMPLE, BAND_PAIR_SEED)
    if key in _BANDS:
        return _BANDS[key]
    if not Path(BOOTSTRAP_NPZ).is_file():
        raise RuntimeError(
            f"the forum modes level the four columns at the retrain band and "
            f"{BOOTSTRAP_NPZ} does not exist; write it with "
            f"python test/graph/facet_pairs/bootstrap_scores.py --draws 24")
    t0 = time.perf_counter()
    print(f"artefact_v3: reading the retrain band from {Path(BOOTSTRAP_NPZ).name} …", flush=True)
    BS = _bootstrap_module()
    z = np.load(BOOTSTRAP_NPZ, allow_pickle=True)
    scores = np.asarray(z["scores"])              # [edges, four columns, draws]
    edge_ids = [str(e) for e in z["edge_ids"]]
    facets = [str(f) for f in z["facets"]]
    n_edges, n_col, draws = scores.shape
    pairs = BS.sample_same_chunk_pairs(edge_ids, BAND_PAIR_SAMPLE, BAND_PAIR_SEED)
    stacked = np.concatenate([scores[:, i, :] for i in range(n_col)], axis=0)
    pooled_pairs = np.concatenate([pairs + i * n_edges for i in range(n_col)], axis=0)
    pooled = BS.flip_gap(stacked, pooled_pairs, BAND_FLIP_RATE, BAND_FLIP_GRID)
    del stacked, pooled_pairs
    bands = {"npz": BOOTSTRAP_NPZ, "sha256": _file_sha(BOOTSTRAP_NPZ), "draws": int(draws),
             "edges": int(n_edges), "columns": facets,
             "pair_sample": "same chunk, two tags of one chunk",
             "pairs": int(pairs.shape[0]), "pair_seed": BAND_PAIR_SEED,
             "flip_rate": BAND_FLIP_RATE, "grid": BAND_FLIP_GRID,
             "facet_band": (None if pooled["gap"] is None else float(pooled["gap"])),
             "estimator": "flip_gap over the stored bootstrap retrains (bootstrap_band.py, "
                          "the module bootstrap_scores re-exports; local mode, window 2000, "
                          "rate 0.05, grid 0.01, the crossing read off the isotonic "
                          "non-increasing fit of the local curve)",
             "mode": "local", "window": 2000,
             "seconds": round(time.perf_counter() - t0, 1),
             "_scores": scores, "_pairs": pairs, "_gflip": {}}
    if bands["facet_band"] is None:
        raise RuntimeError("flip_gap found no gap below the flip rate for the four columns; "
                           "the band cannot be read from this bootstrap file")
    print(f"artefact_v3:   pooled retrain band {bands['facet_band']:.2f} over "
          f"{bands['pairs']} same-chunk pairs x {draws} draws "
          f"({bands['seconds']}s)", flush=True)
    _BANDS[key] = bands
    return bands


def g_band_of(bands: dict, weights: dict, betas: dict, layout: tuple) -> Optional[float]:
    """the retrain band of g itself for one weight vector (SPEC-v2 S6), cached per vector"""
    four = tuple(f for f in layout if f != "topic")
    vec = tuple(round(float(weights[f]) * float(betas[f]), 6) for f in four)
    if all(v == 0.0 for v in vec):
        return None
    hit = bands["_gflip"].get(vec)
    if hit is not None:
        return hit
    BS = _bootstrap_module()
    cols = [bands["columns"].index(f) for f in four]
    n_edges, _, draws = bands["_scores"].shape
    v = np.zeros((n_edges, draws), dtype=np.float32)
    for i, c in enumerate(cols):
        if vec[i]:
            v += np.float32(vec[i]) * bands["_scores"][:, c, :]
    gap = BS.flip_gap(v, bands["_pairs"], BAND_FLIP_RATE, BAND_FLIP_GRID)["gap"]
    gap = None if gap is None else float(gap)
    bands["_gflip"][vec] = gap
    return gap


def mode_key_columns(mode: str, topic: np.ndarray, S: np.ndarray, order: tuple,
                     layout: tuple, *, topic_band: float, facet_band: float,
                     weights: Optional[dict] = None, betas: Optional[dict] = None,
                     adjust: str = "bounded", g_band: Optional[float] = None,
                     topic_key: str = "ordered", r_band: float = COS_NOISE) -> tuple:
    """the one key that differs between the two modes, as level columns over one pool.

    multirank (SPEC §2) — "the queryfacets is the order of sorting-prio based on facets for
      tags, so, if facet 1 is most important for a tag from query, that is sorting order 1 …
      like.. multi-key sort or multi-level sorting" (his, 09-05): the five facet levels as a
      tuple in the part's own facet order. topic is the graph cosine cos(Tag.emb,
      Chunk.desc_emb) at the topic band; the four head columns at the pooled retrain band.
    weighted (SPEC-v2 §3) — "the 'main weight' on a tag, is the topic one, and the others
      adjust that weight depending on the relevance of a facet to the query" (his, 09-18):
      bounded — one column, the steps of r = topic + delta_topic * g's place in the pool's g
      range; level — two columns, topic's level and then g's.

    Returns (columns, names, info)."""
    topic = np.asarray(topic, dtype=np.float64).ravel()
    S = np.asarray(S, dtype=np.float64)
    four = tuple(f for f in layout if f != "topic")
    info: dict = {}
    if mode == "multirank":
        cols_by_name = {"topic": pool_steps(topic, topic_band)}
        for i, f in enumerate(four):
            cols_by_name[f] = pool_steps(S[:, i], facet_band)
        names = list(order)
        if topic_key == "first":
            names = ["topic"] + [f for f in names if f != "topic"]
        return [cols_by_name[f] for f in names], names, info
    if mode != "weighted":
        raise ValueError(f"mode_key_columns knows multirank and weighted, not {mode!r}")
    w = np.asarray([float((weights or {}).get(f, 0.0)) for f in four])
    b = np.asarray([float((betas or {}).get(f, 1.0)) for f in four])
    g, dropped, allnan = weighted_g(S, w, b)
    info = {"g_terms_dropped": dropped, "g_all_nan_rows": allnan}
    if adjust == "bounded":
        delta = topic_band if np.isfinite(topic_band) else 0.0
        r = bounded_r(topic, g, delta)
        return [pool_steps(r, r_band)], ["adjusted topic"], info
    if adjust != "level":
        raise ValueError(f"HERB_V3_ADJUST knows bounded and level, not {adjust!r}")
    lv_g = (np.zeros(g.size, dtype=np.int64) if not g_band
            else pool_steps(g, g_band))
    return [pool_steps(topic, topic_band), lv_g], ["topic", "g"], info


def pool_key_tuples(part_rank: int, columns: list, names: list, link2: np.ndarray,
                    link6: np.ndarray, tag_cos: np.ndarray, chunk_ids: list,
                    desc_place: str = "after") -> tuple:
    """the full key of SPEC-v2's "Full key", per edge of one pool, and the name of every place
    in it: part rank -> mode key -> link 2 -> link 6 -> -tag cosine -> chunk id, or with the two
    description links ahead of the mode key under HERB_V3_DESC_PLACE=before.

    Levels per item, then a plain tuple sort: no banded pairwise comparator anywhere."""
    m = len(chunk_ids)
    desc = [("link2", np.asarray(link2, dtype=np.int64)),
            ("link6", np.asarray(link6, dtype=np.int64))]
    mode = list(zip(names, [np.asarray(c, dtype=np.int64) for c in columns]))
    middle = (mode + desc) if desc_place == "after" else (desc + mode)
    key_names = ["part rank"] + [n for n, _ in middle] + ["tag cosine", "chunk id"]
    keys = []
    for i in range(m):
        keys.append((part_rank,) + tuple(int(c[i]) for _, c in middle)
                    + (-float(tag_cos[i]), chunk_ids[i]))
    return keys, key_names


def _unruled_block() -> list:
    """every construction these modes stand on, with the default in force. SPEC-v2: everything
    tagged [construction] goes here verbatim; none of it is his ruling."""
    rows = [
        {"item": "the pick", "default": "tag side alone at the HERB_V3_BAND rule",
         "text": "his 09-06 'thats how you PICK the tags' (tag side alone) against his 09-11 "
                 "'AND yes / AND' (tag side AND description side; the question it answered is "
                 "not in the record). These modes follow 09-06 because under the AND the pools "
                 "are empty. His to rule."},
        {"item": "topic's band", "default": f"{TOPIC_BAND} ({_topic_band_value():g})",
         "text": "0.028 is 14x the embedder's own noise; it is the description's "
                 "write-to-write noise from the 09-18 pilot (Haiku re-writing 24 chunks), an "
                 "operation the arm never performs; inside one chunk all tags share one stored "
                 "description, so that noise is common-mode there. It is also the number that "
                 "decides how often the facets act. On 09-07 he rejected 0.002 as the fuzz and "
                 "named kNN/clustering instead, which this data cannot supply. His to rule."},
        {"item": "the fuzz as clustering", "default": "a band, not a k",
         "text": "'let clustering hand me the k' / 'the FUZZ can be knn' cannot be honoured: "
                 "measured, the tag-fit list has no clusters; the pick is a band (the "
                 "paraphrase band)."},
        {"item": "one pooled facet band", "default": "flip_gap over the four columns' pairs",
         "text": "Per-column bands are not used: two independent retrain sets disagree on the "
                 "column ordering. His to rule."},
        {"item": "the level rule", "default": "steps below the pool's best",
         "text": "floor((max_P v - v) / delta) on every column; the orchestrator's, chosen on "
                 "menu-invariance and on keeping an empty gap as levels, not on any score."},
        {"item": "part centrality as the first key", "default": "cos(part, query description)",
         "text": "part centrality as the first key comes from his question, not from an answer "
                 "of his."},
        {"item": "the description's place", "default": DESC_PLACE,
         "text": "description after or before the facet block. In region-sized pools the five "
                 "facet keys leave 0.0-0.6% of pairs tied, so under 'after' the description "
                 "link decides almost nothing - against his 09-20 alarm that the descriptions "
                 "are 'the strongest \"correct signal\" in the arm' (an alarm, not a ruling). "
                 "His to rule."},
        {"item": "a chunk stands at its first arrival",
         "default": "first edge the walk reaches it on",
         "text": "the arm's first-arrival rule, not a minimum over the chunk's edges."},
        {"item": "record kind", "default": "reported, never normalised",
         "text": "in the pools the walk compares, ordering by temporal first is largely an "
                 "ordering by record kind; the per-column eta^2 by kind is reported and "
                 "nothing is normalised. His to rule."},
    ]
    if SORT_MODE == "multirank":
        rows.append({"item": "topic's place in the key", "default": TOPIC_KEY,
                     "text": "topic wherever the query part puts it ('ordered') against topic "
                             "forced to the front ('first'); 27 of the 44 10smoke parts are "
                             "topic-first in the cached order. His to rule."})
    if SORT_MODE == "weighted":
        rows += [
            {"item": "the adjust", "default": ADJUST,
             "text": ("in this variant the facets only order what topic calls equal - a "
                      "tie-break, not an adjust." if ADJUST == "level" else
                      "the facets ADJUST topic, and the most they can move an edge is topic's "
                      "own band delta_topic - a topic difference larger than that is never "
                      "overturned. His 08-23 leaves the operator open ('not actual "
                      "multiplication, i cant remember what math we decided on as "
                      "weightadjustor here..'). His to rule.")},
            {"item": "the weights", "default": W_RULE,
             "text": "the part's cached facet weights are the order interpreter's, NOT his "
                     "09-14 per-tag object; that object costs a querytagger prompt rewrite and "
                     "10 model calls for 10smoke / 100 for gold100. Measured: the cached "
                     "weights are non-increasing along the order with the first weight 1.0 on "
                     "43 of 43 parts - a forced shape on the order, not an independent "
                     "magnitude. His to rule."},
            {"item": "the calibration slopes", "default": f"beta {BETA_RULE}",
             "text": "beta enters only through the ratios of the four, which are separated by "
                     "at most ~2.2 SE and mostly under 1 SE - below the fit's resolution."},
        ]
    return rows


def _topic_band_value() -> float:
    return (float("inf") if TOPIC_BAND == "inf"
            else TOPIC_WRITE_BAND if TOPIC_BAND == "write" else COS_NOISE)


def _eta_sq(values: np.ndarray, groups) -> Optional[float]:
    """the share of a column's variance that record kind alone explains, over the walked pools.
    Reported, never acted on. `groups` is one label per value (any sequence)."""
    v = np.asarray(values, dtype=np.float64)
    ok = ~np.isnan(v)
    if ok.sum() < 2:
        return None
    v = v[ok]
    _, code = np.unique(np.asarray(groups, dtype=object)[ok], return_inverse=True)
    code = code.ravel()
    total = float(((v - v.mean()) ** 2).sum())
    if total <= 0:
        return None
    counts = np.bincount(code)
    sums = np.bincount(code, weights=v)
    means = sums / np.maximum(counts, 1)
    between = float((counts * (means - v.mean()) ** 2).sum())
    return round(between / total, 4)


def _dist_block(sizes: list) -> dict:
    if not sizes:
        return {"n": 0}
    a = np.asarray(sizes, dtype=np.float64)
    return {"n": int(a.size), "min": int(a.min()), "median": float(np.median(a)),
            "mean": round(float(a.mean()), 2), "p90": float(np.percentile(a, 90)),
            "max": int(a.max()), "share_of_one": round(float(np.mean(a <= 1)), 4)}


def _decided_by(keys: list, passes: list, levels: list, key_names: list) -> list:
    """which place in the key first separates each adjacent pair of delivered rows. Entry 0 is
    None (no pair before the first row). `key_names` is one name list per row: under multirank
    the facet places carry the NAME OF THAT PART'S ORDER, so a row is named by its own part."""
    out: list = [None]
    for i in range(1, len(keys)):
        if passes[i] != passes[i - 1]:
            out.append("scope pass")
            continue
        if levels[i] != levels[i - 1]:
            out.append("pick level")
            continue
        a, b = keys[i - 1], keys[i]
        names = key_names[i]
        name = "tie (order of arrival)"
        for p, (x, y) in enumerate(zip(a, b)):
            if x != y:
                name = names[p] if p < len(names) else f"key[{p}]"
                break
        out.append(name)
    return out


def _tally(names: list) -> dict:
    out: dict = {}
    for n in names:
        if n is None:
            continue
        out[n] = out.get(n, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _retrieve_forum(session, prepared: Prepared, plan: dict, k: int, question: str,
                    keep_all: bool = False, char_budget: Optional[int] = None,
                    doc_cache: Optional[dict] = None) -> tuple:
    """HERB_V3_SORT=multirank and HERB_V3_SORT=weighted — the two forum modes, SPEC-v2.

    The chain, in order: the cached plan's parts (the raw question is the band's instrument
    only, never a part) -> the pick, tag side alone, levelled at the band -> the pool, one pick
    level of one part inside one scope pass -> the key: part rank, the mode key, link 2, link 6,
    -tag cosine, chunk id -> first arrival -> both scope passes walked to the end. The stop is
    the levels running out; the 72,000-character cut is the harness's (his 09-13)."""
    if SORT_MODE not in FORUM_MODES:
        raise RuntimeError(f"_retrieve_forum was called under HERB_V3_SORT={SORT_MODE!r}")
    if char_budget is None and k <= 0:
        raise ValueError("k must be positive when no character budget is set")
    if not question.strip():
        raise ValueError("the question text is empty")
    if FACET_SOURCE != "file":
        raise RuntimeError(f"HERB_V3_SORT={SORT_MODE} reads the five values per edge off an "
                           f"overlay; HERB_FACET_SOURCE is {FACET_SOURCE!r}")
    if prepared.shape is None:
        raise RuntimeError("the forum modes drop the product-name tags from the candidates and "
                           "no graph shape was loaded; it loads in prepare_over_corpus")
    bands = prepared.bands
    if bands is None:
        bands = load_retrain_bands()
    layout = prepared.facets
    four = tuple(f for f in layout if f != "topic")
    four_cols = [layout.index(f) for f in four]
    e_tag, e_chunk = prepared.edge_tag, prepared.edge_chunk
    n = len(prepared.chunk_ids)

    parts = [p for p in plan["parts"] if isinstance(p, dict) and p.get("t")]
    description = plan.get("description") or question
    if not parts:
        parts = [{"t": description, "order": list(layout)}]
    probes = [description, question] + [_readable(p["t"]) for p in parts]
    qmat, calls, tok_in, tok_out, secs = _embed_cached(probes, "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)
    vecs = [_unit(np.asarray([float(x) for x in row], dtype=np.float64)) for row in qmat]
    desc_vec, raw_vec, part_vecs = vecs[0], vecs[1], vecs[2:]

    # the bands (the instruments). delta_pick and the description band are the arm's own
    # HERB_V3_BAND rule; topic's and the four columns' are SPEC-v2 S6.
    if BAND_RULE == "paraphrase":
        tag_band = float(np.median(np.abs(prepared.tag_vecs @ desc_vec
                                          - prepared.tag_vecs @ raw_vec)))
        desc_band = paraphrase_band(prepared.chunk_vecs, desc_vec, raw_vec)
    else:
        tag_band = desc_band = COS_NOISE
    tag_band, desc_band = max(tag_band, COS_NOISE), max(desc_band, COS_NOISE)
    topic_band = _topic_band_value()
    facet_band = float("inf") if FACET_BAND_RULE == "inf" else float(bands["facet_band"])
    r_band = float("inf") if TOPIC_BAND == "inf" else COS_NOISE
    # JSON has no infinity: an unbanded column is written as a null value with the rule that
    # made it so, never as float("inf")
    def _bv(x):
        return None if not np.isfinite(x) else round(float(x), 6)

    band_block = {
        "pick (delta_pick)": {"value": _bv(tag_band), "rule": BAND_RULE,
                              "estimator": ("the per-question median over tags of |cos(tag, "
                                            "query description) - cos(tag, raw question)|, "
                                            "floored at COS_NOISE"
                                            if BAND_RULE == "paraphrase"
                                            else "COS_NOISE, the embedder's measured JND"),
                              "date": "2026-09-10" if BAND_RULE == "paraphrase" else "2026-09-06"},
        "description": {"value": _bv(desc_band), "rule": BAND_RULE,
                        "used_by": "link 2 (part -> chunk description) and link 6 (query "
                                   "description -> chunk description)",
                        "estimator": ("the per-question median over chunk descriptions of "
                                      "|cos(chunk, query description) - cos(chunk, raw "
                                      "question)|, floored at COS_NOISE"
                                      if BAND_RULE == "paraphrase"
                                      else "COS_NOISE, the embedder's measured JND"),
                        "date": "2026-09-10" if BAND_RULE == "paraphrase" else "2026-09-06"},
        "topic": {"value": _bv(topic_band), "rule": TOPIC_BAND,
                  "estimator": ("the median |dcos| between two independent writes of a chunk "
                                "description, 18,209 units" if TOPIC_BAND == "write"
                                else "COS_NOISE, the embedder's measured JND"
                                if TOPIC_BAND == "noise" else "no band (the key vanishes)"),
                  "date": "2026-09-18" if TOPIC_BAND == "write" else "2026-09-06"},
        "facets (pooled)": {"value": _bv(facet_band), "rule": FACET_BAND_RULE,
                            "estimator": (bands["estimator"] if FACET_BAND_RULE != "inf"
                                          else "no band (the four columns vanish)"),
                            "pairs": bands["pairs"], "pair_seed": bands["pair_seed"],
                            "draws": bands["draws"], "date": "2026-09-21"},
        "mode key (weighted, bounded)": {
            "value": _bv(r_band),
            "rule": "COS_NOISE" if np.isfinite(r_band) else TOPIC_BAND,
            "estimator": ("the embedder's measured JND, the scale r is on"
                          if np.isfinite(r_band) else "no band (the mode key vanishes)"),
            "date": "2026-09-06"},
    }
    print(f"artefact_v3:   bands: pick {tag_band:.5f}, description {desc_band:.5f}, topic "
          f"{topic_band}, facets {facet_band}", flush=True)

    # scope: two passes, in-scope first, both walked to the end. Never a gate, never a key.
    in_scope = np.ones(n, dtype=bool)
    scope_ids, gate_named = (set(), [])
    if SCOPE_RULE != "off":
        scope_ids, gate_named = scope_chunks(session, _parse_gate(plan.get("gate")),
                                             join=SCOPE_JOIN.upper())
        if scope_ids:
            in_scope = np.fromiter((c in scope_ids for c in prepared.chunk_ids),
                                   dtype=bool, count=n)
    scope_named = list(gate_named)
    if not in_scope.any() or not scope_ids:
        in_scope = np.ones(n, dtype=bool)
        scope_named = []
    edge_in = in_scope[e_chunk]
    passes = ([np.ones(len(e_chunk), dtype=bool)] if not scope_named
              else ([edge_in] if SCOPE_RULE == "cut" else [edge_in, ~edge_in]))
    # the tag side: a tag that is a Product node's name is structure, not a candidate (09-14)
    is_product_tag = prepared.shape["product_tag"]
    keep = ~is_product_tag[e_tag]
    lost = 0
    for mi, m in enumerate(passes):
        had = np.zeros(n, dtype=bool)
        had[e_chunk[m]] = True
        passes[mi] = m & keep
        left = np.zeros(n, dtype=bool)
        left[e_chunk[passes[mi]]] = True
        if mi == 0:
            lost = int((had & ~left).sum())
    tagside = {"knob": "nonscope", "edges_dropped": int((~keep).sum()),
               "product_tags": int(is_product_tag.sum()),
               "chunks_without_nonproduct_edge": lost}

    # link 6's cosine (levelled inside each pool), and the parts by centrality
    d2d_cos = prepared.chunk_vecs @ desc_vec
    centrality = [float(pv @ desc_vec) for pv in part_vecs]
    part_rank = {pi: r for r, pi in
                 enumerate(sorted(range(len(parts)), key=lambda i: (-centrality[i], i)))}

    betas = ({f: BETA[f] for f in four} if BETA_RULE == "on" else {f: 1.0 for f in four})
    # THE PICK'S BEST IS THE BEST CANDIDATE TAG (SPEC-v2 S2): the 45 product-name tags are not
    # candidates, so one of them being nearest must not push every real tag a level down.
    candidate_tag = ~is_product_tag
    prepare_s = 0.0
    pick_lvl, tag_cos_of, desc_cos_of, orders, weights_of, gband_of, log = [], [], [], [], [], [], []
    for pi, (part, vec) in enumerate(zip(parts, part_vecs)):
        ts = prepared.tag_vecs @ vec
        ds = prepared.chunk_vecs @ vec
        best = float(ts[candidate_tag].max())
        pick_lvl.append(np.floor((best - ts) / tag_band + 1e-12).astype(np.int64))
        tag_cos_of.append(ts)
        desc_cos_of.append(ds)
        orders.append(facet_order(part, layout))
        w, src = part_facet_weights(part, layout)
        weights_of.append(w)
        # the retrain band of g reads the corpus's stored matrices, not this question: its
        # seconds are booked as prepare, out of search_time_s (the 09-13 review's channel)
        t_g = time.perf_counter()
        gb = (g_band_of(bands, w, betas, layout)
              if SORT_MODE == "weighted" and ADJUST == "level" else None)
        prepare_s += time.perf_counter() - t_g
        gband_of.append(gb)
        log.append({"part": part["t"], "centrality": round(centrality[pi], 4),
                    "rank": part_rank[pi], "facet_order": list(orders[-1]),
                    "pick_levels": int(pick_lvl[-1][candidate_tag].max()) + 1,
                    "facet_weights": ({f: round(float(w[f]), 4) for f in four}
                                      if SORT_MODE == "weighted" else
                                      facet_weights(part, layout)),
                    "weights_source": src if SORT_MODE == "weighted" else None,
                    "g_band": gb,
                    "g_band_reason": (
                        None if SORT_MODE != "weighted" else
                        "g is levelled at its own retrain band" if ADJUST == "level" else
                        "HERB_V3_ADJUST=bounded reads g's place in the pool's range, not its "
                        "level, so g has no band of its own here")})

    # the walk: scope pass -> pick level -> the key inside one (part, pick level) pool
    seen: set = set()
    rows: list = []
    walk: list = []
    pool_sizes: list = []
    pool_sizes_delivering: list = []
    walked_edges: list = []
    g_dropped = g_allnan = 0
    key_names: dict = {}        # per part: the name of every place in that part's key
    done = False
    walk_t0, walk_loud = time.perf_counter(), 0.0
    for walk_pass, mask in enumerate(passes):
        if done:
            break
        at_all = np.flatnonzero(mask)
        if at_all.size == 0:
            continue
        per_part = []
        for pi in range(len(parts)):
            lv = pick_lvl[pi][e_tag[at_all]]
            o = np.argsort(lv, kind="stable")
            per_part.append((at_all[o], lv[o]))
        every_level = sorted({int(x) for _, lv in per_part for x in np.unique(lv)})
        for li, L in enumerate(every_level):
            if time.perf_counter() - walk_loud > 2.0:
                walk_loud = time.perf_counter()
                print(f"artefact_v3:   {SORT_MODE}: pass {walk_pass + 1}/{len(passes)}, pick "
                      f"level {li + 1}/{len(every_level)}, {len(rows)} chunks ordered "
                      f"({walk_loud - walk_t0:.0f}s)", flush=True)
            cand: list = []
            for pi in range(len(parts)):
                idx, lv = per_part[pi]
                lo = int(np.searchsorted(lv, L, side="left"))
                hi = int(np.searchsorted(lv, L, side="right"))
                if hi <= lo:
                    continue
                j = idx[lo:hi]
                c = e_chunk[j]
                cols, names, info = mode_key_columns(
                    SORT_MODE, prepared.edge_w[j, layout.index("topic")],
                    prepared.edge_w[np.ix_(j, four_cols)], orders[pi], layout,
                    topic_band=topic_band, facet_band=facet_band, weights=weights_of[pi],
                    betas=betas, adjust=ADJUST, g_band=gband_of[pi], topic_key=TOPIC_KEY,
                    r_band=r_band)
                g_dropped += int(info.get("g_terms_dropped", 0))
                g_allnan += int(info.get("g_all_nan_rows", 0))
                keys, kn = pool_key_tuples(
                    part_rank[pi], cols, names,
                    # link 2 is a chunk-DESCRIPTION cosine, so it is levelled at the
                    # description band — the band link 6 and the concept walk's description
                    # side use. SPEC-v2's "at delta_pick" named the tag side's band for a
                    # description number; that was a slip, corrected on review 09-21.
                    pool_steps(desc_cos_of[pi][c], desc_band),    # link 2
                    pool_steps(d2d_cos[c], desc_band),            # link 6
                    tag_cos_of[pi][e_tag[j]],
                    [prepared.chunk_ids[int(x)] for x in c], DESC_PLACE)
                key_names[pi] = kn
                pool_sizes.append(int(j.size))
                walked_edges.append(j)
                cand.extend((keys[i], int(j[i]), pi, L, walk_pass) for i in range(j.size))
            if not cand:
                continue
            cand.sort(key=lambda x: x[0])
            fresh = 0
            pools_delivering: set = set()
            for key, jj, pi, lvl, wp in cand:
                c = int(e_chunk[jj])
                cid = prepared.chunk_ids[c]
                if cid in seen:
                    continue
                seen.add(cid)
                fresh += 1
                pools_delivering.add(pi)
                rows.append({**prepared.chunk_rows[c], "tag": prepared.tag_names[e_tag[jj]],
                             "fit": lvl, "pass": wp, "part": pi, "key": key})
            for pi in pools_delivering:
                idx, lv = per_part[pi]
                pool_sizes_delivering.append(
                    int(np.searchsorted(lv, L, side="right") - np.searchsorted(lv, L, side="left")))
            walk.append({"level": L, "pass": walk_pass, "edges": len(cand), "new": fresh})
            if char_budget is None and len(rows) >= k:
                done = True
                break
    if not rows:
        raise RuntimeError("no candidate connection of any part reaches a chunk")
    if char_budget is None and not keep_all:
        rows = rows[:k]
    selected = [{f: r[f] for f in ("chunkId", "locator", "relpath", "sha256")}
                | {"tag": r["tag"], "fit": r["fit"]} for r in rows]

    # what the run has to show: the pools the mode key was read in, what decided each adjacent
    # delivered pair, and how much of each column record kind alone explains
    decided = _decided_by([r["key"] for r in rows], [r["pass"] for r in rows],
                          [r["fit"] for r in rows],
                          [key_names.get(r["part"], []) for r in rows])
    kind_of = (None if prepared.kinds is None else
               np.asarray([x if x is not None else "?" for x in prepared.kinds], dtype=object))
    kind_eta = None
    if walked_edges and kind_of is not None:
        W = np.concatenate(walked_edges)
        groups = kind_of[e_chunk[W]]
        kind_eta = {"edges": int(W.size), "kinds": int(np.unique(groups).size)}
        for f in layout:
            kind_eta[f] = _eta_sq(prepared.edge_w[W, layout.index(f)], groups)
    # SPEC §5: of the adjacent delivered pairs the MODE KEY decided, how many are between
    # chunks of different record kinds. Reported, never normalised — his to rule.
    mode_names = set()
    for kn in key_names.values():
        mode_names.update(n for n in kn if n not in
                          ("part rank", "link2", "link6", "tag cosine", "chunk id"))
    at_of_chunk = {c: i for i, c in enumerate(prepared.chunk_ids)}
    by_mode = cross = 0
    for i in range(1, len(rows)):
        if decided[i] not in mode_names:
            continue
        by_mode += 1
        if kind_of is not None:
            a = kind_of[at_of_chunk[rows[i - 1]["chunkId"]]]
            b = kind_of[at_of_chunk[rows[i]["chunkId"]]]
            cross += int(a != b)
    mode_cross_kind = {"mode_key_decisions": by_mode,
                       "between_different_kinds": (None if kind_of is None else cross),
                       "share": (None if kind_of is None or not by_mode
                                 else round(cross / by_mode, 4))}
    meta = {
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "sort": {"mode": SORT_MODE, "pick": "tag side alone, at the band (SPEC-v2 S2)",
                 "band_rule": BAND_RULE, "bands": band_block, "tagside": tagside,
                 "desc_place": DESC_PLACE, "region": REGION, "locality": LOCALITY,
                 **({"topic_key": TOPIC_KEY} if SORT_MODE == "multirank" else
                    {"adjust": ADJUST, "w": W_RULE, "beta": BETA_RULE,
                     "betas": {f: betas[f] for f in four},
                     "g_terms_dropped": g_dropped, "g_all_nan_rows": g_allnan})},
        "parts": log,
        "walk": walk,
        "retrieved": len(selected),
        "scope": {"rule": SCOPE_RULE, "named": scope_named, "gate_named": gate_named,
                  "chunks": len(scope_ids), "join": SCOPE_JOIN, "fields": SCOPE_FIELDS,
                  "passes": len(passes)},
        "facet_layer": {"source": FACET_SOURCE, "overlay": prepared.overlay,
                        # corpus-wide work this question paid for (the retrain band of g for
                        # its weight vectors): booked as prepare, out of search_time_s
                        "prepare_seconds": round(prepare_s, 2),
                        "retrain_band": {key: val for key, val in bands.items()
                                         if not key.startswith("_")}},
        "keys": {"names": {str(pi): kn for pi, kn in sorted(key_names.items())},
                 "decided_by_row": decided,
                 "decided_by": _tally(decided[1:]),
                 "pools": _dist_block(pool_sizes),
                 "pools_delivering": _dist_block(pool_sizes_delivering),
                 "pool_sizes": pool_sizes,
                 "pool_membership": "one (part, pick level, scope pass). An already-delivered "
                                    "chunk's edge stays in every later pool it belongs to and "
                                    "can be that pool's best, so it sets the levels of the "
                                    "rows around it although it is delivered only once "
                                    "(SPEC-v2 S3 as written; the orchestrator's reading, "
                                    "his to rule)",
                 "mode_key_across_record_kinds": mode_cross_kind,
                 "kind_eta_squared": kind_eta},
        "unruled": _unruled_block(),
        "ranking": {"chunk_ids": [r["chunkId"] for r in rows],
                    "pick_level": [int(r["fit"]) for r in rows],
                    "pass": [int(r["pass"]) for r in rows],
                    "part": [int(r["part"]) for r in rows]},
    }
    print(f"artefact_v3:   {SORT_MODE}: {len(rows)} chunks ordered over {len(pool_sizes)} pools "
          f"(median pool {meta['keys']['pools'].get('median')}), keys deciding: "
          f"{meta['keys']['decided_by']}", flush=True)
    return selected, usage, meta


# ------------------------------------------------------------------ combo (09-11, selected on gold)

_FACET_POS: dict = {}


def facet_positions(prepared: Prepared, query_w: Optional[dict] = None,
                    W: Optional[np.ndarray] = None, rows: Optional[np.ndarray] = None,
                    per_edge: bool = False, unit: Optional[np.ndarray] = None) -> np.ndarray:
    """per edge and facet: the edge's level in that facet's own column (clump rule, 0 the
    strongest, missing values last), divided by the column's last level — a position in 0..1
    that means the same thing in every facet. query_w is the part's facet weights
    (facet_weights); it is carried and ignored while its place inside a column is unruled
    (2026-09-13), so every part reads one matrix.

    W replaces prepared.edge_w for this call (FACET_SOURCE=edge hands in the question's own
    per-edge values) and is never cached: it is a question's matrix, not the corpus's.
    `rows` is the edge mask naming the population a column is levelled over — every edge when
    it is not given; an edge outside it keeps position 0.0 and is never read. `per_edge` says
    the four statistics are read per edge in that population (FACET_SOURCE=edge inside the
    region). An edge of that population whose tag's sentences did not resolve carries its
    chunk's value instead: it is filled from any anchored edge of its chunk before the
    levelling, and only a chunk with no anchored edge at all stays missing and lands last.
    `unit` then names what generated each value — the edge where the value is the edge's, the
    chunk where it is the chunk's — and the column is levelled once per unit and broadcast
    back, so the clump rule's chance test counts the values the data holds and not the edges
    that repeat them. Without `per_edge` each of the four is one chunk number repeated over
    the chunk's edges (~12.9 of them) and is levelled once per chunk, by the same rule.
    Both readings are the 09-09 text statistics', FACET_SOURCE edge | stats. Under
    FACET_SOURCE=file the file carries a value per edge, so every column — topic and the four
    — is levelled over the edges themselves and nothing is collapsed onto a chunk.

    ONE POPULATION PER SCOPE PASS (the 09-13 review): under FACET_SOURCE=edge the caller levels
    every pass-1 edge together — the region's per-edge values and, for the fallbacks, their
    chunk's own values — and levels pass 2's edges, chunk-level throughout, over themselves.
    The walk compares edges only inside its own scope pass, never across the two."""
    settings = (FACET_SOURCE, DIST_RULE, FACET_KEY, WEIGHT_GRAIN, DIST_RANGE, LEVEL_RULE,
                KDE_BW, KDE_BW_FACTOR, KDE_GRID, tuple(prepared.facets), prepared.edge_w.shape)
    cacheable = W is None and rows is None and not per_edge and unit is None
    if cacheable:
        hit = _FACET_POS.get(id(prepared))
        if hit is not None and hit[0] is prepared and hit[1] == settings:
            return hit[2]
    W = prepared.edge_w if W is None else W
    P = np.zeros(W.shape, dtype=np.float64)
    idx = (np.arange(W.shape[0]) if rows is None
           else np.flatnonzero(np.asarray(rows, dtype=bool)))
    if idx.size == 0:
        return P
    Ws = W[idx].copy()
    e_chunk = prepared.edge_chunk[idx]
    chunks = np.unique(e_chunk)
    if per_edge and FACET_SOURCE in STATS_SOURCES:
        # an edge whose tag's sentences did not resolve takes its chunk's value from any
        # anchored edge of that chunk — the fill the per-chunk branch does — so it is read by
        # the same rule as its neighbours instead of landing last on all four columns
        span = int(chunks.max()) + 1
        for fi, f in enumerate(prepared.facets):
            if f == "topic":
                continue
            col = Ws[:, fi]
            miss = np.isnan(col)
            if not miss.any() or miss.all():
                continue
            fill = np.full(span, np.nan)
            fill[e_chunk[~miss]] = col[~miss]
            col[miss] = fill[e_chunk[miss]]
    for fi, f in enumerate(prepared.facets):
        qw = None if query_w is None else query_w.get(f)
        if FACET_SOURCE in STATS_SOURCES and not per_edge and f != "topic":
            per = np.full((int(chunks.max()) + 1, Ws.shape[1]), np.nan)
            # the chunk takes the value of any anchored edge (they agree — the statistic is the
            # chunk's); writing every edge would let an unanchored one land last and sink the
            # chunk on all four columns (review 09-13)
            anchored = ~np.isnan(Ws[:, fi])
            per[e_chunk[anchored], fi] = Ws[anchored, fi]
            lv_c = np.zeros(per.shape[0])
            lv_c[chunks] = facet_levels(per[chunks], f, qw, prepared.facets)
            lv = lv_c[e_chunk]
        elif unit is not None and FACET_SOURCE in STATS_SOURCES and f != "topic":
            u = np.asarray(unit)[idx]
            _, first, inv = np.unique(u, return_index=True, return_inverse=True)
            lv = facet_levels(Ws[first], f, qw, prepared.facets).astype(np.float64)[inv.ravel()]
        else:
            lv = facet_levels(Ws, f, qw, prepared.facets).astype(np.float64)
        top = lv.max()
        P[idx, fi] = lv / top if top > 0 else 0.0
    if cacheable:
        _FACET_POS[id(prepared)] = (prepared, settings, P)
    return P


def facet_relevance(P: np.ndarray, layout: tuple, weights: Optional[dict]) -> np.ndarray:
    """HERB_V3_FACETADJ: per edge, how relevant the tag is to the chunk for THIS part — the
    edge's five facet values weighted by what the part says each facet is worth. "the facet
    weight in COMBINATION with the tag's chunk relevance weight would tell how relevant the
    tag actually is in relation to the prompt" (06-27); "So we can weight-adjust the facets
    based on that.." (09-13).

    P is facet_positions' matrix — every facet already a level position 0..1 inside its own
    column (the clump rule), so the five are commensurate; here it is read the other way up,
    1.0 the strongest, because this is a relevance and not a sort key. The weights are the
    part's (facet_weights); a part that names none reads the five equal. A weighted MEAN: rel
    stays in [0, 1] whatever the weights sum to, so no part's weight magnitude changes the
    scale the strength is levelled on."""
    w = np.ones(len(layout), dtype=np.float64)
    if weights is not None:
        w = np.asarray([float(weights.get(f, 0.0)) for f in layout], dtype=np.float64)
        if not w.sum():
            w = np.ones(len(layout), dtype=np.float64)
    return (1.0 - P) @ w / w.sum()


def chunk_strength(prepared: Prepared, part_vecs: list,
                   rows: Optional[np.ndarray] = None, comb: str = "product",
                   rel: Optional[list] = None, adj: str = "off") -> tuple:
    """his chain on one chunk. Per part: the chunk's best tag cosine (the query→tag→chunk link)
    and the part's cosine to the chunk description (the query→chunk link), combined by `comb`
    — "product" (they multiply) or "sum" (they add, both being cosines of the same part
    against the same chunk; HERB_V3_PARTCOMB). Summed over parts,
    because a part's evidence is evidence, not a vote — a count of parts was measured 09-10 not
    to help (0.419 against 0.449), the sum of strengths was (0.257 max-over-parts → 0.375).
    `rel` and `adj` are HERB_V3_FACETADJ: per part, the edge's facet relevance to that part
    (facet_relevance, full-length over the prepared edges), joined onto the tag side of that
    part before the chunk's best edge is taken — add: tag cosine + rel; mul: tag cosine x rel.
    The description side, the combination and the sum over parts are untouched.
    `rows` reads one edge set only (a scope pass, TAGSIDE's kept edges); the edge indices
    returned are the prepared edges' own.
    Returns (strength per chunk, the part that contributed most, that part's best edge)."""
    e_tag, e_chunk = prepared.edge_tag, prepared.edge_chunk
    at = None
    if rows is not None:
        at = np.flatnonzero(rows)
        e_tag, e_chunk = e_tag[at], e_chunk[at]
    n = len(prepared.chunk_ids)
    total = np.zeros(n)
    best_part = np.zeros(n, dtype=np.int64)
    best_val = np.full(n, -np.inf)
    best_edge = np.zeros(n, dtype=np.int64)
    for pi, vec in enumerate(part_vecs):
        tag_sims = prepared.tag_vecs @ vec
        desc_sims = prepared.chunk_vecs @ vec
        edge_cos = tag_sims[e_tag]
        if adj != "off" and rel is not None:
            r = np.asarray(rel[pi], dtype=np.float64)
            r = r if at is None else r[at]
            edge_cos = edge_cos + r if adj == "add" else edge_cos * r
        top = np.full(n, -np.inf)
        np.maximum.at(top, e_chunk, edge_cos)
        reached = np.isfinite(top)
        contrib = (np.where(reached, top, 0.0) * desc_sims if comb == "product"
                   else np.where(reached, top + desc_sims, 0.0))
        total += contrib
        take = contrib > best_val
        if take.any():
            best_val = np.where(take, contrib, best_val)
            best_part = np.where(take, pi, best_part)
        # the edge that carried this part on each chunk
        at_top = np.flatnonzero(edge_cos >= top[e_chunk] - 1e-12)
        for j in at_top:
            c = e_chunk[j]
            if best_part[c] == pi:
                best_edge[c] = j if at is None else at[j]
    return total, best_part, best_edge


def _retrieve_combo(session, prepared: Prepared, plan: dict, k: int, question: str,
                    keep_all: bool = False, char_budget: Optional[int] = None,
                    doc_cache: Optional[dict] = None) -> tuple:
    if char_budget is None and k <= 0:
        raise ValueError("k must be positive when no character budget is set")
    if not question.strip():
        raise ValueError("the question text is empty")
    parts = [p for p in plan["parts"] if isinstance(p, dict) and p.get("t")]
    description = plan.get("description") or question
    probes = [description, question] + [_readable(p["t"]) for p in parts]
    qmat, calls, tok_in, tok_out, secs = _embed_cached(probes, "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)
    vecs = [_unit(np.asarray([float(x) for x in row], dtype=np.float64)) for row in qmat]
    desc_vec, raw_vec = vecs[0], vecs[1]
    # the raw question probes beside the parts: measured 09-09 to carry 4–13 of every
    # question's rows, and 09-10 to be worth 0.12 of recall when it reaches
    part_vecs = vecs[2:] + [raw_vec]
    part_list = parts + [{"t": question, "order": list(prepared.facets)}]
    layout = prepared.facets
    n = len(prepared.chunk_ids)

    strength, best_part, best_edge = chunk_strength(prepared, part_vecs)
    d2d = prepared.chunk_vecs @ desc_vec
    band = (paraphrase_band(prepared.chunk_vecs, desc_vec, raw_vec)
            if BAND_RULE == "paraphrase" else COS_NOISE)
    # a band below what the embedder can tell apart is no band: when the description equals
    # the question the paraphrase spread is 0 (review 09-11, P4), and the floor is the noise
    band = max(band, COS_NOISE)
    # the strength's own band: the same rephrasing spread, carried onto this scale by the
    # description end of the product (the tag end is unchanged by a rephrasing of the need);
    # read on chunks both ends reach positively
    ok = (d2d > 0) & (strength > 0)
    s_band = band * float(np.median(strength[ok] / d2d[ok])) if ok.any() else band
    lvl = levels_cos(strength, s_band)
    d2d_lvl = levels_cos(d2d, band) if "desc2desc" in COMBO_KEYS else np.zeros(n, dtype=int)
    part_order = [facet_order(p, layout) for p in part_list]

    part_qw = [facet_weights(p, layout) for p in part_list]
    P = facet_positions(prepared) if "facets" in COMBO_KEYS else None
    def facet_key(c: int) -> tuple:
        if P is None:
            return ()
        pi = int(best_part[c])
        order = part_order[pi]
        pos = P[best_edge[c]]
        return tuple(float(pos[layout.index(f)]) for f in order)

    in_scope = np.ones(n, dtype=bool)
    scope_ids, scope_named = (set(), [])
    if SCOPE_RULE != "off":
        scope_ids, scope_named = scope_chunks(session, _parse_gate(plan.get("gate")))
        if scope_ids:
            in_scope = np.fromiter((c in scope_ids for c in prepared.chunk_ids),
                                   dtype=bool, count=n)
    if not in_scope.any():
        in_scope = np.ones(n, dtype=bool)
        scope_named = []

    reached = np.flatnonzero(strength > 0)
    if not len(reached):
        raise RuntimeError("no tag of any part reaches a chunk")
    order = sorted(reached.tolist(),
                   key=lambda c: ((0 if in_scope[c] else 1) if scope_named and SCOPE_RULE == "ahead" else 0,
                                  int(lvl[c]),
                                  facet_key(c),
                                  int(d2d_lvl[c]),
                                  -float(strength[c]),
                                  prepared.chunk_ids[c]))
    if scope_named and SCOPE_RULE == "cut":
        order = [c for c in order if in_scope[c]]

    rows = [{**prepared.chunk_rows[c], "tag": prepared.tag_names[prepared.edge_tag[best_edge[c]]],
             "fit": int(lvl[c])} for c in order]
    # his rule, 2026-09-13: the full ranked order goes out; the harness cuts at 72,000 chars
    if char_budget is None and not keep_all:
        rows = rows[:k]

    selected = [{f: r[f] for f in ("chunkId", "locator", "relpath", "sha256")} | {"tag": r["tag"], "fit": r["fit"]}
                for r in rows]
    meta = {
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "sort": {"mode": "combo", "keys": list(COMBO_KEYS), "band_rule": BAND_RULE,
                 "band": round(band, 5), "strength_band": round(s_band, 6),
                 "strength_levels": int(lvl.max()) + 1},
        "parts": [{"part": p["t"], "facet_order": list(part_order[i]),
                   "facet_weights": part_qw[i],
                   "chunks_led": int((best_part[reached] == i).sum())}
                  for i, p in enumerate(part_list)],
        "retrieved": len(selected),
        "connections": {"chunks": int(len(reached))},
        "scope": {"rule": SCOPE_RULE, "named": scope_named, "chunks": len(scope_ids),
                  "chunks_in_scope": int(in_scope.sum()) if scope_named else None},
        "facet_layer": {"source": FACET_SOURCE, "overlay": prepared.overlay},
        "ranking": {"chunk_ids": [r["chunkId"] for r in rows]},
    }
    return selected, usage, meta


# ------------------------------------------------------------------ the chain (09-10 first build)

def paraphrase_band(chunk_vecs: np.ndarray, desc_vec: np.ndarray, raw_vec: np.ndarray) -> float:
    """how far rephrasing the same need moves a chunk's cosine: the median over chunks of
    |cos(chunk, description) − cos(chunk, raw question)|"""
    d = chunk_vecs @ desc_vec
    r = chunk_vecs @ raw_vec
    return float(np.median(np.abs(d - r)))


def _retrieve_chain(session, prepared: Prepared, plan: dict, k: int, question: str,
                    keep_all: bool = False, char_budget: Optional[int] = None,
                    doc_cache: Optional[dict] = None) -> tuple:
    if char_budget is None and k <= 0:
        raise ValueError("k must be positive when no character budget is set")
    if not question.strip():
        raise ValueError("the question text is empty")
    parts = [p for p in plan["parts"] if isinstance(p, dict) and p.get("t")]
    description = plan.get("description") or question
    probes = [description, question] + [_readable(p["t"]) for p in parts]
    qmat, calls, tok_in, tok_out, secs = _embed_cached(probes, "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)
    vecs = [_unit(np.asarray([float(x) for x in row], dtype=np.float64)) for row in qmat]
    desc_vec, raw_vec, part_vecs = vecs[0], vecs[1], vecs[2:]
    layout = prepared.facets
    e_tag, e_chunk = prepared.edge_tag, prepared.edge_chunk

    band = paraphrase_band(prepared.chunk_vecs, desc_vec, raw_vec) if BAND_RULE == "paraphrase" else COS_NOISE
    # the whole-question link: query description against every chunk description, levelled
    desc_link = prepared.chunk_vecs @ desc_vec
    desc_level_chunk = levels_cos(desc_link, band)
    # the parts by centrality: cosine to the description, most central first
    centrality = [float(pv @ desc_vec) for pv in part_vecs]
    part_rank = {pi: r for r, pi in enumerate(sorted(range(len(parts)), key=lambda i: (-centrality[i], i)))}

    part_fit, part_cos, part_order, part_qw, level_log = [], [], [], [], []
    for pi, (part, vec) in enumerate(zip(parts, part_vecs)):
        tag_sims = prepared.tag_vecs @ vec
        desc_sims = prepared.chunk_vecs @ vec
        conn = connection_fit(tag_sims[e_tag], desc_sims[e_chunk])
        fit = levels_cos(conn, band)
        part_fit.append(fit)
        part_cos.append({n: float(x) for n, x in zip(prepared.tag_names, tag_sims)})
        part_order.append(facet_order(part, layout))
        part_qw.append(facet_weights(part, layout))
        level_log.append({"part": part["t"], "centrality": round(centrality[pi], 4),
                          "rank": part_rank[pi], "fit_levels": int(fit.max()) + 1,
                          "nearest_level": int((fit == 0).sum()),
                          "facet_order": list(part_order[-1]),
                          "facet_weights": part_qw[-1]})

    reached: set = set()
    payload: dict = {}
    out_rows: list = []
    walk = []

    def open_level(L: int, mask: np.ndarray, walk_pass: int) -> None:
        rows, keys = [], []
        for pi in range(len(parts)):
            at = np.flatnonzero((part_fit[pi] == L) & mask)
            if at.size == 0:
                continue
            edges = [{"tag": prepared.tag_names[e_tag[j]], **prepared.chunk_rows[e_chunk[j]],
                      "w": prepared.edge_w[j], "ci": int(e_chunk[j])} for j in at]
            W = np.asarray([e["w"] for e in edges], dtype=np.float64)
            lv = ({f: facet_levels(W, f, (part_qw[pi] or {}).get(f), layout)
                   for f in part_order[pi]}
                  if "facets" in CHAIN_KEYS else {})
            for i, e in enumerate(edges):
                key = ((part_rank[pi] if "part" in CHAIN_KEYS else 0,)
                       + tuple(int(lv[f][i]) for f in part_order[pi] if f in lv)
                       + ((int(desc_level_chunk[e["ci"]]) if "desc" in CHAIN_KEYS else 0),
                          -part_cos[pi][e["tag"]], e["chunkId"]))
                rows.append((pi, e))
                keys.append(key)
        if not rows:
            return
        order = sorted(range(len(rows)), key=lambda i: keys[i])
        fresh = 0
        for i in order:
            pi, e = rows[i]
            cid = e["chunkId"]
            if cid not in reached:
                fresh += 1
                reached.add(cid)
            out_rows.append({"chunkId": cid, "locator": e["locator"], "relpath": e["relpath"],
                             "sha256": e["sha256"], "tag": e["tag"], "fit": L, "part": parts[pi]["t"]})
            payload.setdefault(cid, {f: e[f] for f in ("chunkId", "locator", "relpath", "sha256")})
        walk.append({"fit_level": L, "pass": walk_pass, "rows": len(rows), "new": fresh,
                     "parts": sorted({parts[pi]["t"] for pi, _ in rows})})

    def merged() -> list:
        out, seen = [], set()
        for r in out_rows:
            if r["chunkId"] not in seen:
                seen.add(r["chunkId"])
                out.append(r)
        return out

    def enough() -> bool:
        # his rule, 2026-09-13: under a character budget the arm opens every level of the
        # region and stops on its own levels; the 72,000-char cut is the harness's, after
        if char_budget is not None:
            return False
        return len(reached) >= k

    in_scope = np.ones(len(e_chunk), dtype=bool)
    scope_ids, scope_named = (set(), [])
    if SCOPE_RULE != "off":
        scope_ids, scope_named = scope_chunks(session, _parse_gate(plan.get("gate")))
        if scope_ids:
            chunk_ok = np.fromiter((c in scope_ids for c in prepared.chunk_ids),
                                   dtype=bool, count=len(prepared.chunk_ids))
            in_scope = chunk_ok[e_chunk]
    if not in_scope.any():
        in_scope = np.ones(len(e_chunk), dtype=bool)
        scope_named = []
    every = np.ones(len(e_chunk), dtype=bool)
    passes = [every] if not scope_named else ([in_scope] if SCOPE_RULE == "cut" else [in_scope, ~in_scope])

    max_level = max(int(f.max()) for f in part_fit)
    for walk_pass, mask in enumerate(passes):
        if walk_pass and enough():
            break
        for L in range(max_level + 1):
            if L >= MIN_LEVELS and enough():
                break
            open_level(L, mask, walk_pass)
    if not reached:
        raise RuntimeError("no tag of any part reaches a chunk")

    rows = merged()
    if char_budget is None and not keep_all:
        rows = rows[:k]
    selected = [{**payload[row["chunkId"]], "tag": row["tag"], "fit": row["fit"]} for row in rows]
    meta = {
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "sort": {"mode": SORT_MODE, "keys": list(CHAIN_KEYS), "band_rule": BAND_RULE,
                 "band": round(band, 5), "desc_link_levels": int(desc_level_chunk.max()) + 1},
        "parts": level_log,
        "walk": walk,
        "retrieved": len(selected),
        "connections": {"chunks": len(reached), "rows": len(out_rows)},
        "scope": {"rule": SCOPE_RULE, "named": scope_named, "chunks": len(scope_ids),
                  "connections_in_scope": int(in_scope.sum()) if scope_named else None},
        "facet_layer": {"source": FACET_SOURCE, "overlay": prepared.overlay},
        "ranking": {"chunk_ids": [row["chunkId"] for row in rows]},
    }
    return selected, usage, meta


# ------------------------------------------------------------------ the 09-07 walk (HERB_V3_SORT=v3)

def _retrieve(session, prepared: Prepared, plan: dict, k: int, question: str,
              keep_all: bool = False, char_budget: Optional[int] = None,
              doc_cache: Optional[dict] = None) -> tuple:
    if char_budget is None and k <= 0:
        raise ValueError("k must be positive when no character budget is set")
    if RAW_QUESTION and not question.strip():
        raise ValueError("HERB_RAW_QUESTION is on and the question text is empty")

    parts = list(plan["parts"])
    probes = [_readable(p["t"]) for p in parts]
    if RAW_QUESTION:
        parts.append({"t": question, "facets": dict(NEUTRAL_FACETS), "order": list(prepared.facets)})
        probes.append(question)
    qmat, calls, tok_in, tok_out, secs = _embed_cached(probes, "query")
    usage = ModelUsage(calls=calls, tokens_in=tok_in, tokens_out=tok_out, time_s=secs)

    e_tag, e_chunk = prepared.edge_tag, prepared.edge_chunk
    layout = prepared.facets
    part_fit, part_cos, part_order, part_qw, level_log = [], [], [], [], []
    for part, row in zip(parts, qmat):
        vec = _unit(np.asarray([float(x) for x in row], dtype=np.float64))
        tag_sims = prepared.tag_vecs @ vec
        desc_sims = prepared.chunk_vecs @ vec
        conn = connection_fit(tag_sims[e_tag], desc_sims[e_chunk])
        fit = levels_cos(conn)
        part_fit.append(fit)
        part_cos.append({n: float(x) for n, x in zip(prepared.tag_names, tag_sims)})
        part_order.append(facet_order(part, layout))
        part_qw.append(facet_weights(part, layout))
        top = np.argsort(-conn, kind="stable")[:6]
        level_log.append({"part": part["t"], "fit_levels": int(fit.max()) + 1,
                          "nearest_level": int((fit == 0).sum()),
                          "fit_rule": FIT_RULE,
                          "facet_order": list(part_order[-1]),
                          "facet_weights": part_qw[-1],
                          "nearest": [{"tag": prepared.tag_names[e_tag[j]],
                                       "chunk": prepared.chunk_ids[e_chunk[j]],
                                       "tag_cos": round(float(tag_sims[e_tag[j]]), 4),
                                       "desc_cos": round(float(desc_sims[e_chunk[j]]), 4)}
                                      for j in top]})

    reached: set = set()
    payload: dict = {}
    walk = []
    part_rows = [[] for _ in parts]

    def open_fit_level(pi: int, L: int, mask: np.ndarray, walk_pass: int) -> None:
        at = np.flatnonzero((part_fit[pi] == L) & mask)
        if at.size == 0:
            return
        edges = [{"tag": prepared.tag_names[e_tag[j]],
                  **prepared.chunk_rows[e_chunk[j]],
                  "w": prepared.edge_w[j],
                  "rank": (prepared.edge_rank[j] if prepared.edge_rank is not None
                           else np.zeros(len(layout), dtype=np.int64))} for j in at]
        fresh = 0
        idx, level_counts = sort_connections(edges, part_cos[pi], part_order[pi], part_qw[pi], layout)
        for j in idx:
            row = edges[j]
            cid = row["chunkId"]
            if cid not in reached:
                fresh += 1
                reached.add(cid)
            part_rows[pi].append({"chunkId": cid, "locator": row["locator"],
                                  "relpath": row["relpath"], "sha256": row["sha256"],
                                  "tag": row["tag"], "fit": L})
            payload.setdefault(cid, {f: row[f] for f in ("chunkId", "locator", "relpath", "sha256")})
        walk.append({"part": parts[pi]["t"], "fit_level": L, "pass": walk_pass,
                     "tags": int(len(np.unique(e_tag[at]))),
                     "rows": len(edges), "new": fresh, "facet_levels": level_counts})

    def merged() -> list:
        out: list = []
        seen: set = set()
        longest = max((len(r) for r in part_rows), default=0)
        for r in range(longest):
            for pr in part_rows:
                if r < len(pr) and pr[r]["chunkId"] not in seen:
                    seen.add(pr[r]["chunkId"])
                    out.append(pr[r])
        return out

    def enough() -> bool:
        # his rule, 2026-09-13: under a character budget the arm opens every level of the
        # region and stops on its own levels; the 72,000-char cut is the harness's, after
        if char_budget is not None:
            return False
        return len(reached) >= k

    in_scope = np.ones(len(e_chunk), dtype=bool)
    scope_ids, scope_named = (set(), [])
    if SCOPE_RULE != "off":
        scope_ids, scope_named = scope_chunks(session, _parse_gate(plan.get("gate")))
        if scope_ids:
            chunk_ok = np.fromiter((c in scope_ids for c in prepared.chunk_ids),
                                   dtype=bool, count=len(prepared.chunk_ids))
            in_scope = chunk_ok[e_chunk]
    if not in_scope.any():
        in_scope = np.ones(len(e_chunk), dtype=bool)
        scope_named = []
    every = np.ones(len(e_chunk), dtype=bool)
    if not scope_named:
        passes = [every]
    elif SCOPE_RULE == "cut":
        passes = [in_scope]
    else:
        passes = [in_scope, ~in_scope]

    widening = sorted((L, pi) for pi in range(len(parts))
                      for L in range(1, int(part_fit[pi].max()) + 1))
    for walk_pass, mask in enumerate(passes):
        if walk_pass and enough():
            break
        for pi in range(len(parts)):
            open_fit_level(pi, 0, mask, walk_pass)
        for L, pi in widening:
            if L >= MIN_LEVELS and enough():
                break
            open_fit_level(pi, L, mask, walk_pass)
    if not reached:
        raise RuntimeError("no tag of any part reaches a chunk")

    rows = merged()
    if not keep_all:
        rows = rows[:k]
    selected = [{**payload[row["chunkId"]], "tag": row["tag"], "fit": row["fit"]} for row in rows]

    meta = {
        "plan": {key: val for key, val in plan.items() if not key.startswith("_")},
        "parts": level_log,
        "walk": walk,
        "retrieved": len(selected),
        "connections": {"chunks": len(reached), "rows_per_part": [len(r) for r in part_rows]},
        "scope": {"rule": SCOPE_RULE, "named": scope_named, "chunks": len(scope_ids),
                  "connections_in_scope": int(in_scope.sum()) if scope_named else None},
        "facet_layer": {"source": FACET_SOURCE, "overlay": prepared.overlay,
                        "rank_overlay": prepared.rank_overlay, "facet_key": FACET_KEY,
                        "dist_rule": DIST_RULE, "weight_grain": WEIGHT_GRAIN},
        "ranking": {"chunk_ids": [row["chunkId"] for row in rows]},
    }
    return selected, usage, meta


def answer_one_question(question, prepared: Prepared, generate, k: int = 50,
                        char_budget: Optional[int] = None) -> ArmOutput:
    qid, text = _qid_text(question)
    chat.reset_timing()
    t0 = time.perf_counter()
    if FACET_SOURCE in TEXT_SOURCES:
        plan, interp_calls, interp_in, interp_out, interp_time = _interpret_order_cached(text, INTERPRET_MODEL)
    else:
        plan, interp_calls, interp_in, interp_out, interp_time = _interpret_cached(text, INTERPRET_MODEL)
    for part in plan.get("parts", []):
        if isinstance(part, dict) and part.get("weights_invalid"):
            print(f"artefact_v3: !! question {qid}: part {part['t']!r} — the interpreter's weights "
                  "contradicted its own order after the retry; the order stands, the weights are "
                  "dropped", flush=True)
    doc_cache: dict = {}
    retrieve = {"concept": _retrieve_concept, "combo": _retrieve_combo,
                "chain": _retrieve_chain, "multirank": _retrieve_forum,
                "weighted": _retrieve_forum}.get(SORT_MODE, _retrieve)
    with prepared.driver.session(database=DATABASE) as session:
        rows, ground_usage, meta = retrieve(session, prepared, plan, k, text,
                                            keep_all=char_budget is not None,
                                            char_budget=char_budget, doc_cache=doc_cache)
    meta["interpreter"] = {"model": INTERPRET_MODEL, "backend": "claude-cli"}
    retrieve_wall = time.perf_counter() - t0

    rev_calls = rev_in = rev_out = 0
    rev_time = 0.0
    if char_budget is not None:
        contexts, chunk_id_lists, context_ids, meta["char_budget"] = _budget_contexts(
            rows, char_budget, doc_cache)
    else:
        contexts, context_ids, chunk_id_lists = [], [], []
        seen: set = set()
        for row in rows:
            chunk_text, ids = _resolve_chunk(row, doc_cache)
            contexts.append(chunk_text)
            chunk_id_lists.append(ids)
            for aid in ids:
                if aid not in seen:
                    seen.add(aid)
                    context_ids.append(aid)
        if NO_REVIEW:
            kept, review_log = len(contexts), []
        else:
            kept, review_log, rev_calls, rev_in, rev_out, rev_time = _sufficient_cut(text, contexts)
        contexts = contexts[:kept]
        chunk_id_lists = chunk_id_lists[:kept]
        seen = set()
        context_ids = []
        for ids in chunk_id_lists:
            for aid in ids:
                if aid not in seen:
                    seen.add(aid)
                    context_ids.append(aid)
        meta["review"] = {"kept": kept, "rounds": review_log}
    # the delivered rows are the credited cut; the walked rows are every row the walk ordered
    loc_block = meta.get("facet_layer", {}).get("locality") or {}
    if loc_block.get("knob") == "on":
        credited = (meta["char_budget"]["kept"] if char_budget is not None else kept)
        loc_block["delivered"] = _distance_block(loc_block["rows"][:credited])
    key_block = meta.get("keys")
    if key_block and key_block.get("decided_by_row") is not None:
        credited = (meta["char_budget"]["kept"] if char_budget is not None else kept)
        key_block["delivered_rows"] = credited
        key_block["decided_by_delivered"] = _tally(key_block["decided_by_row"][1:credited])
    meta["returned"] = len(contexts)
    meta["chunk_ids"] = chunk_id_lists

    # the sentence embedding is retrieval work, not a model leg taken out of it: its seconds
    # are booked in usage and stay inside search_time_s (09-13)
    sent_s = float(((meta.get("facet_layer") or {}).get("edge_stats") or {}).get(
        "embed_seconds") or 0.0)
    # corpus-wide layers a question built on first need are prepare, not this question's search
    prep_s = float((meta.get("facet_layer") or {}).get("prepare_seconds") or 0.0)
    prepared.build_stats.build_time_s = round(prepared.build_stats.build_time_s + prep_s, 1)
    search_time_s = max(0.0, retrieve_wall - interp_time - ground_usage.time_s + sent_s - prep_s)
    retrieval_usage = ModelUsage(
        calls=interp_calls + ground_usage.calls + rev_calls,
        tokens_in=interp_in + ground_usage.tokens_in + rev_in,
        tokens_out=interp_out + ground_usage.tokens_out + rev_out,
        time_s=interp_time + ground_usage.time_s + rev_time,
        **chat.take_timing())

    if generate is None:
        answer, gen = "", ModelUsage()
    else:
        g0 = time.perf_counter()
        result = generate(text, contexts)
        answer, gen = unpack_generation(result, time.perf_counter() - g0)

    return ArmOutput(answer=answer, contexts=contexts, context_ids=context_ids,
                     search_time_s=search_time_s, generator=gen,
                     retrieval=retrieval_usage, meta=meta)
