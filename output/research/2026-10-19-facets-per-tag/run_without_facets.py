"""The control for the per-tag facets: the same hundred, the same cached first-call answers, the
facets' weights set to zero, so what the facets do is told apart from what the new first call's
tags do. No model call (run it with --flag HERB_V4_OFFLINE=on); the arm is not changed, the zero
is put in from outside, in this process only.

    .venv/Scripts/python.exe output/research/2026-10-19-facets-per-tag/run_without_facets.py \
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

_influenced = WK.influenced_edge_values


def without_facets(layer, cosines, weights, close_spread=None):
    """Every edge's weight with every facet weight zero: the tag's closeness as it is."""
    return _influenced(layer, cosines, np.zeros_like(np.asarray(weights, dtype=np.float64)),
                       close_spread)


WK.influenced_edge_values = without_facets
sys.path.insert(0, str(ROOT / 'prod'))
import run  # noqa: E402

if __name__ == '__main__':
    run.main()
