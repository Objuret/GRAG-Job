"""Mark every setting of a grouped weights-cross run against his dated sentences.

Reads a completed (or partial) retrieval_harness_fast run, recomputes the
per-setting means the same way `report` does, and writes
`report.flagged.json` and `report.flagged.md` beside the shards. Each setting
carries one mark per factor and one for the coefficient vector:

  his      a dated sentence of his supports this value
  open     no sentence of his either way (the orchestrator's note says what it is)
  against  a dated sentence of his stands against it
  gold     the value was chosen on the gold (his 09-11 sentence stands against choosing it)
  tension  an inference from a sentence of his stands against it; the inference is the orchestrator's

`fits` is a derived filter, not a judgement: true when no factor is marked
against or gold; a tension mark does not set it false and is listed in
`tension_by`. `against_by` lists which factors set it false. The marks are
the stats; the sentences are quoted in `citations`. Nothing here decides.

Constructions present in every row that no factor can flag are listed under
`in_every_row`. This file touches nothing under the run except the two report files.
"""
from __future__ import annotations

import argparse
import contextlib
import json
from pathlib import Path
import sys

import numpy as np

with contextlib.redirect_stdout(sys.stderr):
    import retrieval_harness as H
    import retrieval_harness_fast as RF
    import facet_retrieval_lab as L

CITATIONS = {
    'chain-09-02': '"the combo of query facets vs tagfacets, query tags vs tags and then query desc vs chunk desc" (2026-09-02)',
    'sort-tags-09-06': '"you are sorting the fucking tags.." (2026-09-06)',
    'pick-09-06': '"first you pick a fizzy value for fit of tags via the tag vs querytags embeddings, right? thats how you PICK the tags" (2026-09-06)',
    'five-facets-09-06': '"let the fact that there is 5 facets do the work" (2026-09-06)',
    'order-from-query-09-06': '"if facet 1 is most important for a tag from query, that is sorting order 1" (2026-09-06)',
    'topic-main-09-18': '"my thinking is that the \\"main weight\\" on a tag, is the topic one, and the others adjust that weight depending on the relevance of a facet to the query" (2026-09-18)',
    'weights-adjust-09-13': '"that\'s why we have the interpretor put a value on its tags in relation to the query... So we can weight-adjust the facets based on that.." (2026-09-13)',
    'both-09-20': '"both" (2026-09-20), asked whether the ranked layer serves the multi-key sort or the adjust',
    'and-09-11': '"AND yes AND" (2026-09-11), on link 2 in the walk: the connection\'s level is the worse of tag steps and description steps',
    'tryhard-09-11': '"you are tryharding on \\"getting the best score\\" when the actual fucking best score, is given when this is CONSTRUCTED CORRECTLY" (2026-09-11)',
    'no-numbers-07-15': '"i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something" (2026-07-15)',
    'no-shape-09-09': '"there is 0 fucking use of the graph-shape here, actual none" (2026-09-09)',
    'grouped-stronger-09-14': 'a reached chunk under a named node is stronger, a reached chunk in a group with other reached chunks is stronger — his "Yes, exactly" (2026-09-14) to that reading',
    'not-beforehand-09-14': '"Products chunks? That\'s you determining something before it even is a thing, you fucking do NOT know that information beforehand." (2026-09-14)',
    'scope-from-graph-09-14': '"i think this is impossible without overfitting and perhaps we use logic instead using the actual graphshape after we have gotten a chunk pool? I dislike naming scope from the query" · "Yup. Sounds good." (2026-09-14)',
    'areas-09-14': '"the point is finding the areas, and let the chunks fill in the content, so don\'t have to dig too deep before" (2026-09-14)',
    'desc-key-09-10': '"i think i agree, enough to atleast build it first" (2026-09-10) — the description link as its own key after the facets, a provisional go',
    'every-link-09-02': '"the wohle point of the facets, weights and all weights of the tags-chunks-files-query, are about \\"how strong/relevant is the connection for this specific query\\"" (2026-09-02)',
    'files-unsaid': 'Not said by him yet: how the sorted tags carry their chunks and files (CLAUDE.md)',
    'ranks-09-20': '"ok, i am ready to use ranking instead of actual weights, one can convert ranks to weights" (2026-09-20)',
}

# (mark, citation key, the orchestrator's note on what the value does in the code)
MARKS = {
    'match': {
        'tag_only': ('his', 'chain-09-02', 'query tag vs graph tag picks the edge; the tag→chunk link is the edge\'s own facet values; nearest to the chain as he stated it'),
        'minimum': ('open', 'and-09-11', 'min(cos(query tag, graph tag), cos(query tag, chunk description)): the worse of two, an analogy to his link-2 AND (which joined walk levels, not cosines); the analogy is the orchestrator\'s; measured out 09-13 as a veto'),
        'maximum': ('open', None, 'max of the same two cosines; the only value where a chunk can be admitted on the unnamed join alone, the query tag never meeting a graph tag (his 09-06 pick bypassed rather than joined)'),
        'product': ('gold', 'tryhard-09-11', 'cos(query tag, graph tag) × cos(query tag, chunk description): combo\'s form, kept non-default because it was chosen on the gold'),
        'description_only': ('against', 'pick-09-06', 'the pick is deleted: the query tag never meets a graph tag; the edges and their facet values still carry the score'),
    },
    'facet': {
        'separate_facet_sum': ('his', 'topic-main-09-18', 'per facet: edge value × the querytagger\'s weight for that facet, best edge per facet, summed with a fixed β per facet; topic is one channel among five, β says how much each adjusts'),
        'same_path_sum': ('open', 'weights-adjust-09-13', 'one dot product per edge of the querytagger\'s weights and the edge\'s five values (the four non-topic divided by 4), best edge per chunk; the weights act, but as one number per edge'),
        'topic_only': ('against', 'five-facets-09-06', 'the four facets are switched off'),
        'separate_facet_streams': ('open', 'both-09-20', 'the five channels kept apart for a multi-key sort; not in the coefficient cross'),
    },
    'topology': {
        'none': ('against', 'no-shape-09-09', 'no graph shape enters the score'),
        'adjacency': ('his', 'grouped-stronger-09-14', 'a file-adjacent neighbour lends half its direct score × the chunk\'s description cosine; the 0.5 is a chosen constant (07-15)'),
        'groups': ('his', 'grouped-stronger-09-14', 'the best other member of the chunk\'s (product, channel) group lends half its direct score × the chunk\'s description cosine; the 0.5 is a chosen constant (07-15)'),
        'both': ('his', 'grouped-stronger-09-14', 'the larger of the adjacency and group offers; the 0.5 is a chosen constant (07-15)'),
    },
    'graph_join': {
        'union': ('his', 'grouped-stronger-09-14', 'max(direct, graph): the shape strengthens, cuts nothing'),
        'intersection': ('tension', 'not-beforehand-09-14', 'min(direct, graph): a chunk with no graph support loses its direct support — an inference from his sentence on deciding before knowing, the inference is the orchestrator\'s'),
        'graph_only': ('tension', 'not-beforehand-09-14', 'direct support dropped; only graph paths score — the same inference'),
    },
    'description': {
        'multiply': ('open', 'chain-09-02', 'the link is present: score × cos(query description, chunk description); the join is combo\'s, not his; his ruled form (own key after the facets, 09-10) is not among the four values'),
        'independent_union': ('open', 'chain-09-02', 'the link is present: a chunk\'s depth is the better of its score depth and its description depth; the join is not his'),
        'independent_intersection': ('open', 'chain-09-02', 'the link is present: a chunk\'s depth is the worse of its score depth and its description depth; the join is not his'),
        'off': ('against', 'chain-09-02', 'the query-description-vs-chunk-description link is dropped'),
    },
    'scope': {
        'equal_depth': ('his', 'scope-from-graph-09-14', 'the area is read off the structural landing; an in-area chunk takes its within-area depth, an outside chunk keeps its global depth; nothing cut'),
        'area_first': ('open', 'areas-09-14', 'every in-area chunk before every outside chunk; nothing cut, the area dominates the order; whether that is "areas first" as he meant it is his to say'),
        'all': ('open', 'areas-09-14', 'the landing is ignored even when the question names something'),
        'area_only': ('against', 'not-beforehand-09-14', 'outside chunks are cut'),
    },
    'recovery': {
        'on': ('open', 'files-unsaid', 'a chunk takes the best depth of its exact record\'s other ranged chunks: the file link acting, with no query-relative strength on it (08-31 wants one)'),
        'off': ('open', 'files-unsaid', 'no record recovery; the file link is absent'),
    },
}

IN_EVERY_ROW = [
    'winners = combined.max(axis=1): a chunk\'s score per facet is its BEST query tag\'s contribution, a max over the query side (facet_operator_matrix.py). No sentence of his chooses max; the arm\'s best measured walk (09-13) used the sum over parts.',
    'Graph offers carry a fixed 0.5 and a fixed /4 in the same-path alignment (facet_operator_matrix.py): chosen numbers, his 07-15.',
    'Every coefficient vector β is five chosen numbers, the default [1, .25, .25, .25, .25] included; `topic_largest` marks the vectors where topic is a largest coefficient (his 09-18).',
    'The multi-key sort half of his 09-20 "both" is not in this run: the coefficient cross covers separate_facet_sum only, and the historical lex: policies use one fixed global facet order, not the query\'s (his 09-06).',
    'match=tag_only is his three links only under topology=none: every graph offer is scaled by cos(query tag, chunk description) on the receiving chunk (_graph_primitives), so with any shape the join he never named comes back through the graph. The factor set cannot express his chain plus the shape without it.',
    'The fits family sits on the tag side; the 09-13 measurements say the tag side is the weak instrument on this corpus (tag cosine max over parts 0.257 vs description cosine alone 0.375 on the ten smoke questions), so the fits list is expected to sit below the overall top.',
    'The lab ranks in score space (competition ranks); artefact_v3 ranks in band levels. No setting here is a knob combination of the arm.',
    'The edge facet values are topic = cos(tag, chunk description) plus the round-1 pairwise layer (Opus choices → ranker), midrank-transformed per column (his 09-20 "ranking instead of actual weights"). The querytagger\'s per-tag per-facet weights are u.',
]


def mark_policy(policy):
    marks, against_by, tension_by = {}, [], []
    for factor, table in MARKS.items():
        value = policy[factor]
        if factor == 'facet' and value.startswith('lex:'):
            mark, cite, note = ('against', 'order-from-query-09-06', 'a fixed global facet order, not the query\'s')
        else:
            mark, cite, note = table[value]
        marks[factor] = {'value': value, 'mark': mark, 'citation': cite, 'note': note}
        if mark in ('against', 'gold'):
            against_by.append(factor)
        elif mark == 'tension':
            tension_by.append(factor)
    return marks, against_by, tension_by


def flag_run(name, metric='recall_id', top=25):
    out, plan = RF.load_plan(name)
    H.verify_sources(plan)
    complete = RF.verify_completed(out, plan)
    sums, counts, cases_done = RF.load_means(out, plan, complete)
    P, W = len(plan['policies']), len(plan['coefficients'])
    eligible = cases_done == len(plan['cases'])
    means = np.divide(sums, counts, out=np.full_like(sums, np.nan), where=counts > 0)
    mi = RF.METRICS.index(metric)
    betas = np.asarray(plan['coefficients'])
    topic_largest = betas[:, 0] >= betas[:, 1:].max(axis=1)
    policy_marks = [mark_policy(p) for p in plan['policies']]
    fits_policy = np.asarray([not a for _, a, _ in policy_marks])
    score = means[:, :, mi].copy()
    score[~eligible, :] = np.nan

    def rows(mask, limit):
        flat = np.where(mask & np.isfinite(score), score, -np.inf).ravel()
        order = np.argsort(-flat, kind='stable')[:limit]
        result = []
        for idx in order:
            if not np.isfinite(flat[idx]) or flat[idx] == -np.inf:
                break
            pi, wi = divmod(int(idx), W)
            marks, against_by, tension_by = policy_marks[pi]
            result.append({'policy_index': pi, 'coefficient_index': wi, 'policy': plan['policies'][pi],
                           'coefficients': plan['coefficients'][wi],
                           **{k: (None if not np.isfinite(means[pi, wi, j]) else float(means[pi, wi, j])) for j, k in enumerate(RF.METRICS)},
                           'fits': not against_by, 'against_by': against_by, 'tension_by': tension_by, 'topic_largest': bool(topic_largest[wi]),
                           'marks': {f: m['mark'] for f, m in marks.items()}})
        return result

    def best_under(label, policy_mask, coef_mask=None):
        m = score.copy()
        m[~policy_mask, :] = np.nan
        if coef_mask is not None:
            m[:, ~coef_mask] = np.nan
        n = int(np.isfinite(m).sum())
        if not n:
            return {'slice': label, 'settings': 0}
        pi, wi = divmod(int(np.nanargmax(m)), W)
        return {'slice': label, 'settings': n, 'recall_id': float(m[pi, wi]),
                'precision_id': None if not np.isfinite(means[pi, wi, 1]) else float(means[pi, wi, 1]),
                'policy': plan['policies'][pi], 'coefficients': plan['coefficients'][wi]}

    def sel(**kw):
        return np.asarray([all(p[k] == v for k, v in kw.items()) for p in plan['policies']])

    default_beta = np.asarray([np.array_equal(b, [1, .25, .25, .25, .25]) for b in betas])
    no_tension = np.asarray([not a and not t for _, a, t in policy_marks])
    slices = [
        best_under('overall', np.ones(P, bool)),
        best_under('default β [1,.25,.25,.25,.25]', np.ones(P, bool), default_beta),
        best_under('topic a largest coefficient', np.ones(P, bool), topic_largest),
        best_under('topic coefficient 0', np.ones(P, bool), betas[:, 0] == 0),
        best_under('fits (no against, no gold)', fits_policy),
        best_under('fits and no tension', no_tension),
        best_under('fits, no tension, topic largest', no_tension, topic_largest),
        best_under('match=tag_only (his chain)', sel(match='tag_only')),
        best_under('match=tag_only, topology=none (his chain, no shape)', sel(match='tag_only', topology='none')),
        best_under('match=product (chosen on gold)', sel(match='product')),
        best_under('match=minimum (the AND analogy)', sel(match='minimum')),
        best_under('match=maximum', sel(match='maximum')),
        best_under('match=description_only', sel(match='description_only')),
        best_under('graph_join=union', sel(graph_join='union')),
        best_under('topology=none', sel(topology='none')),
        best_under('scope=equal_depth', sel(scope='equal_depth')),
        best_under('scope=area_first', sel(scope='area_first')),
        best_under('scope=area_only', sel(scope='area_only')),
        best_under('scope=all (no landing)', sel(scope='all')),
        best_under('description=multiply', sel(description='multiply')),
        best_under('description=off', sel(description='off')),
        best_under('recovery=on', sel(recovery='on')),
        best_under('recovery=off', sel(recovery='off')),
    ]
    top_value = float(np.nanmax(score))
    spread = {'settings_within_0.005_of_top': int((score >= top_value - 0.005).sum()),
              'settings_within_0.01_of_top': int((score >= top_value - 0.01).sum()),
              'mean_over_settings': float(np.nanmean(score)), 'median_over_settings': float(np.nanmedian(score))}

    all_mask = np.ones((P, W), dtype=bool)
    fits_mask = fits_policy[:, None] & np.ones((1, W), dtype=bool)
    fits_topic_mask = fits_mask & topic_largest[None, :]
    counts_summary = {
        'settings': int(P * W), 'fully_covered_settings': int(eligible.sum() * W),
        'policies_fits': int(fits_policy.sum()), 'settings_fits': int(fits_policy.sum() * W),
        'settings_fits_topic_largest': int(fits_policy.sum() * topic_largest.sum()),
        'coefficient_vectors_topic_largest': int(topic_largest.sum()),
        'policies_by_against_factor': {f: int(sum(f in a for _, a, _ in policy_marks)) for f in MARKS},
        'policies_by_tension_factor': {f: int(sum(f in t for _, _, t in policy_marks)) for f in MARKS},
    }
    report = {'run': name, 'metric': metric, 'status': 'complete' if len(complete) == plan['expected_shards'] else 'partial',
              'cases': len(plan['cases']), 'counts': counts_summary,
              'mark_legend': {'his': 'a dated sentence of his supports the value', 'open': 'no sentence either way',
                              'against': 'a dated sentence stands against it', 'gold': 'chosen on the gold (his 09-11 stands against choosing it)',
                              'tension': "an inference of the orchestrator's from a sentence of his stands against it; does not set fits false",
                              'fits': 'derived: no factor marked against or gold; against_by names the factors; tension_by is listed beside it'},
              'in_every_row': IN_EVERY_ROW, 'best_under_each_mark': slices, 'spread': spread,
              'top_overall': rows(all_mask, top), 'top_fits': rows(fits_mask, top), 'top_fits_topic_largest': rows(fits_topic_mask, top),
              'factor_marks': {f: {v: {'mark': m, 'citation': c, 'note': n} for v, (m, c, n) in t.items()} for f, t in MARKS.items()},
              'citations': CITATIONS,
              'selection_note': 'Every list is a maximum over many settings scored on the same 95 questions; the fits list over ' + str(counts_summary['settings_fits']) + '. The pick is on the gold. Nothing here is decided.'}
    H.atomic_json(out / 'report.flagged.json', report)
    (out / 'report.flagged.md').write_text(markdown(report), encoding='utf-8')
    return report


def markdown(report):
    def table(rows_):
        head = '| # | recall_id | precision_id | fits | against_by | tension_by | topic_largest | match | topology | join | description | scope | recovery | β |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n'
        body = ''
        for i, r in enumerate(rows_, 1):
            p = r['policy']
            body += f"| {i} | {r['recall_id']:.5f} | {r['precision_id']:.5f} | {'yes' if r['fits'] else 'no'} | {','.join(r['against_by']) or '-'} | {','.join(r['tension_by']) or '-'} | {'yes' if r['topic_largest'] else 'no'} | {p['match']} | {p['topology']} | {p['graph_join']} | {p['description']} | {p['scope']} | {p['recovery']} | {r['coefficients']} |\n"
        return head + body
    c = report['counts']
    text = f"# {report['run']} — {report['metric']} over {report['cases']} questions ({report['status']})\n\n"
    text += f"Settings {c['settings']}, fully covered {c['fully_covered_settings']}. Policies with no factor against or gold: {c['policies_fits']}; settings fits {c['settings_fits']}; of those with topic a largest coefficient {c['settings_fits_topic_largest']}.\n\n"
    text += "In every row:\n" + ''.join(f"- {s}\n" for s in report['in_every_row']) + '\n'
    text += f"{report['selection_note']}\n\n"
    s = report['spread']
    text += f"Spread: {s['settings_within_0.005_of_top']} settings within 0.005 of the top, {s['settings_within_0.01_of_top']} within 0.01; mean over all settings {s['mean_over_settings']:.4f}, median {s['median_over_settings']:.4f}.\n\n"
    text += "## Best setting under each mark\n\n| slice | settings | recall_id | precision_id | match | topology | join | description | scope | recovery | β |\n|---|---|---|---|---|---|---|---|---|---|---|\n"
    for r in report['best_under_each_mark']:
        if not r['settings']:
            text += f"| {r['slice']} | 0 | | | | | | | | | |\n"
            continue
        p = r['policy']
        text += f"| {r['slice']} | {r['settings']} | {r['recall_id']:.5f} | {r['precision_id']:.5f} | {p['match']} | {p['topology']} | {p['graph_join']} | {p['description']} | {p['scope']} | {p['recovery']} | {r['coefficients']} |\n"
    text += "\n## Top overall\n\n" + table(report['top_overall']) + '\n'
    text += "## Top with fits (no factor against or gold)\n\n" + table(report['top_fits']) + '\n'
    text += "## Top with fits and topic a largest coefficient\n\n" + table(report['top_fits_topic_largest']) + '\n'
    text += "## Marks per factor value\n\n| factor | value | mark | his sentence | what the value does |\n|---|---|---|---|---|\n"
    for f, t in report['factor_marks'].items():
        for v, m in t.items():
            cite = report['citations'].get(m['citation'], '-') if m['citation'] else '-'
            text += f"| {f} | {v} | {m['mark']} | {cite} | {m['note']} |\n"
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', required=True)
    parser.add_argument('--metric', choices=RF.METRICS, default='recall_id')
    parser.add_argument('--top', type=int, default=25)
    args = parser.parse_args()
    report = flag_run(args.run, args.metric, args.top)
    print(json.dumps({'run': report['run'], 'status': report['status'], 'counts': report['counts'],
                      'top_overall': report['top_overall'][:3], 'top_fits': report['top_fits'][:3]}, indent=2))


if __name__ == '__main__':
    main()
