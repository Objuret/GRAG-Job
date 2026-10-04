"""The pairwise facet ranker: a scalar per (tag, chunk, facet) fitted to comparisons.

The judge never writes a number. It answers "which of these two edges is more X", and the
modules here turn those answers into one ordering per facet over every graph edge:

    model.py        PairRanker — ONE encoder pass an edge, five scalar heads
    data.py         the comparison set from the answer files, and the three hash splits
    train.py        Davidson (1970) Bradley-Terry-with-ties on the judge's comparisons only
    evaluate.py     held-out agreement per facet and pair type, and the frozen stop rules
    score_all.py    every edge, five scores, resumable, shardable across machines
    acquire.py      the next round's pairs, from training chunks only
    diagnostics.py  ties, order flips, repeat flips, cycles, comparison-graph connectivity
    map_topic.py    AFTER scoring: the judge-derived scales read into topic's numbers

The known numeric topic values are read in `map_topic.py` and nowhere else. Fitting a topic
scale to them would make that mapping circular (his correction, 2026-09-18).

Nothing here calls a model API, writes to the graph, or reads gold.
"""
