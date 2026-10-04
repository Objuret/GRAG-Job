"""Length-only posthoc audit of the fixed ten-answer RAGAS context inputs.

Loads private source/benchmark text mechanically, emits only aggregate counts.
No retrieval, model call, answer inspection, or metric retuning occurs.
"""
from collections import Counter
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'output/k=chars/artefact_facet_program_v2__10smoke__cb72000__20260924T001226294548Z'
CORPUS=ROOT/'data/corpus/Salesforce__HERB'
ARTIFACT_TYPES=('slack','documents','meeting_transcripts','meeting_chats','urls','prs')


def string_leaves(value):
    parts=[]
    def walk(item):
        if isinstance(item,str):parts.append(item)
        elif isinstance(item,dict):
            for child in item.values():walk(child)
        elif isinstance(item,list):
            for child in item:walk(child)
    walk(value)
    return ' '.join(parts).strip()


def run():
    outputs={row['id']:row for row in
             (json.loads(line) for line in (RUN/'arm_outputs.jsonl').open(encoding='utf-8'))}
    selected={row['id'] for row in
              (json.loads(line) for line in (ROOT/'data/10smoke.jsonl').open(encoding='utf-8'))}
    if set(outputs)!=selected or len(outputs)!=10:raise ValueError('Fixed ten answers missing')
    citations={row['id']:row['citations'] for row in
               (json.loads(line) for line in (ROOT/'data/questions.jsonl').open(encoding='utf-8'))
               if row['id'] in selected}
    if set(citations)!=selected:raise ValueError('Fixed ten citations missing')
    wanted={str(aid) for ids in citations.values() for aid in ids}
    refs={}
    for path in sorted((CORPUS/'products').glob('*.json')):
        doc=json.loads(path.read_text(encoding='utf-8'))
        for kind in ARTIFACT_TYPES:
            for record in doc.get(kind,[]) or []:
                aid=record.get('id')
                if aid is not None and aid in wanted and aid not in refs:
                    refs[aid]=len(string_leaves(record))
    counts=Counter()
    counts['questions']=10
    for qid,out in outputs.items():
        ref_lens=[refs[str(aid)] for aid in citations[qid] if str(aid) in refs]
        context_lens=[len(text) for text in out['contexts']]
        if not ref_lens or not context_lens:raise ValueError('Empty RAGAS context input')
        counts['retrieved_contexts']+=len(context_lens)
        counts['reference_contexts']+=len(ref_lens)
        counts['all_context_reference_pairs']+=len(context_lens)*len(ref_lens)
        # For normalized Levenshtein, similarity <= min(lengths)/max(lengths).
        def cap(a,b):return min(a,b)/max(a,b) if max(a,b) else 1.0
        counts['retrieved_contexts_cannot_pass_precision_by_length']+=sum(
            not any(cap(a,b)>=0.5 for b in ref_lens) for a in context_lens)
        counts['reference_contexts_cannot_pass_recall_by_length']+=sum(
            not any(cap(a,b)>0.5 for a in context_lens) for b in ref_lens)
        counts['all_pairs_cannot_pass_precision_by_length']+=sum(
            cap(a,b)<0.5 for a in context_lens for b in ref_lens)
        counts['all_pairs_cannot_pass_recall_by_length']+=sum(
            cap(a,b)<=0.5 for a in context_lens for b in ref_lens)
        full=out['meta']['char_budget']['kept']
        for i in range(full):
            aids={str(aid) for aid in out['meta']['chunk_ids'][i]}
            for aid in aids & {str(v) for v in citations[qid]}:
                if aid not in refs:continue
                counts['gold_id_linked_full_chunk_pairs']+=1
                bound=cap(context_lens[i],refs[aid])
                counts['gold_id_linked_pairs_cannot_pass_precision_by_length']+=bound<0.5
                counts['gold_id_linked_pairs_cannot_pass_recall_by_length']+=bound<=0.5
    return {'counts':dict(counts),'unit':'delivered context versus full gold artifact',
            'bound':'similarity <= min(lengths)/max(lengths)',
            'model_calls':0,'raw_text_exported':False,'gold_answers_read':False}


if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
