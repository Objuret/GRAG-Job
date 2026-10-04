"""Explicit area-first variant of the frozen joint-facet arm.

Same interpretation, local embeddings, facet scores, structural resolver and
serialized budget. Only the structural nomination schedule differs. It is an
experimental candidate, not a silently changed joint-arm default.
"""
from pathlib import Path

from arms import artefact_facet_joint as joint
from arms.artefact_facet_joint import answer_one_question


SMOKE_PROVENANCE_PATHS = (*joint.SMOKE_PROVENANCE_PATHS, 'test/arms/artefact_facet_area.py')
SMOKE_MODEL_CONFIG = {**joint.SMOKE_MODEL_CONFIG, 'scope_scheduling': 'area_first'}


def prepare_over_corpus(corpus):
    prepared = joint.prepare_over_corpus(corpus, scope_scheduling='area_first')
    # The variant wrapper is part of the executed source, not an ambient flag.
    path = Path(__file__)
    prepared.provenance['source_sha256'][str(path.relative_to(joint.ROOT))] = joint._sha(path.read_bytes())
    return prepared
