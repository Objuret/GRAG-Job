"""The control for the facets as ranks against ranks: the same build and the same cached first-call
answers, every named facet taken as not mattering, so each query tag's chunks stand by closeness
alone and what the facets do is told apart from the rest. No model call (run it with
--flag HERB_V4_OFFLINE=on); the arm is not changed, the facets are left out from outside, in this
process only.

    .venv/Scripts/python.exe output/research/2026-10-19-facet-ranks/run_without_facets.py \
        --arm artefact_v4 --set gold --char-budget 72000 --workers 6 --retrieval-only \
        --flag HERB_V4_OFFLINE=on --out output/k=chars/<folder>_without_facets
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT / 'prod', ROOT / 'test'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from artefact import v4_walk as WK  # noqa: E402

_places = WK.facet_relative_places


def without_facets(layer, cosines, facet_of, inside):
    """Each query tag's chunks by closeness alone."""
    return _places(layer, cosines, np.full(len(facet_of), -1, dtype=np.int64), inside)


WK.facet_relative_places = without_facets
import run  # noqa: E402

if __name__ == '__main__':
    run.main()
