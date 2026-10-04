"""Write-once, content-free evidence for the fixed-program smoke preflight."""
import hashlib
import json
from pathlib import Path

import facet_program_arm_parity as parity
import facet_program_smoke_input_audit as input_audit


ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'output/research/2026-09-24-real-gold-smoke/preflight-evidence.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source=[
        ROOT/'tools/facet_program_preflight_record.py',
        ROOT/'tools/facet_program_arm_parity.py',
        ROOT/'tools/facet_program_smoke_input_audit.py',
        ROOT/'test/arms/artefact_facet_program.py',
        ROOT/'output/research/2026-09-24-real-gold-smoke/selected-program.json',
        ROOT/'output/research/2026-09-22-retrieval-matrix/inputs/cases_manifest.json',
        ROOT/'data/10smoke.jsonl',
    ]
    before={str(path.relative_to(ROOT)):sha(path) for path in source}
    checks={'captured_numeric':parity.check(delivery_case='case_001'),
            'smoke10_raw_input':input_audit.audit()}
    after={str(path.relative_to(ROOT)):sha(path) for path in source}
    if before!=after:raise RuntimeError('Preflight inputs changed during verification')
    if checks['captured_numeric']['numeric_full_order_cases']!=95:raise RuntimeError('Incomplete order parity')
    raw=checks['smoke10_raw_input']
    expected=['raw_scope_different','full_order_different_from_saved_scope',
              'first_72k_full_chunks_different','interpreter_source_record_different',
              'weights_different_from_saved_numeric']
    if any(raw[key]!=0 for key in expected) or raw['cache_status']!={'generate_ok':10,'score_ok':10}:
        raise RuntimeError('Smoke10 input parity not established')
    record={'schema_version':1,'kind':'fixed_program_preflight',
            'program_id':'tag_frontier_best-macro-recall_query_only_queries_all',
            'checks':checks,'input_sha256':after,
            'limitations':['Captured numeric matrices used for order parity; fresh embedding vectors are checked after generation.',
                           'One representative actual 72k source delivery was compared before generation.'],
            'question_text_exported':False,'interpretation_text_exported':False,
            'source_text_exported':False,'gold_read':False,'model_calls':0}
    DEST.parent.mkdir(parents=True,exist_ok=True)
    with DEST.open('x',encoding='utf-8') as stream:
        json.dump(record,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps({'preflight_evidence':str(DEST.relative_to(ROOT)),
                      'captured_numeric_cases':95,'smoke10_cache_success':10,
                      'smoke10_input_differences':0,'model_calls':0,'gold_read':False}))


if __name__=='__main__':main()
