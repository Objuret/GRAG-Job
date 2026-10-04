"""Live coefficient overrides, isolated from the frozen matrix implementation."""
import time
import numpy as np
import facet_retrieval_lab as L

DEFAULT_COEFFICIENTS = np.array([1., .25, .25, .25, .25])


def coefficients(raw, policy):
    value = np.asarray(DEFAULT_COEFFICIENTS if raw is None else raw, dtype=float)
    if value.shape != (5,) or not np.isfinite(value).all() or (value < 0).any() or not value.any():
        raise ValueError('Five finite nonnegative coefficients required, with at least one positive')
    if policy['facet'] != 'separate_facet_sum' and not np.array_equal(value, DEFAULT_COEFFICIENTS):
        raise ValueError('Coefficient overrides require separate_facet_sum')
    return value


class WeightedLab(L.Lab):
    def weighted_retrieve(self, case, policy, beta):
        if np.array_equal(beta, DEFAULT_COEFFICIENTS):
            return self.retrieve(case, policy)
        key = tuple(policy[k] for k in ('match', 'topology', 'graph_join'))
        original = case['families'][key + ('separate_facet_streams',)]
        combined = np.sum(original * (beta / DEFAULT_COEFFICIENTS)[:, None], axis=0, keepdims=True)
        # Isolate both scores and rank caches from every other request/comparison.
        changed = {**case, 'families': {key + ('separate_facet_sum',): combined}, 'depth_cache': {}}
        return self.retrieve(changed, policy)

    def replay(self, payload):
        started = time.perf_counter()
        with self.lock:
            case = self.case(payload['case_id'])
            policy = self.validate(payload.get('policy', {}))
            old_policy = self.validate(payload.get('compare_policy', L.DEFAULT))
            beta = coefficients(payload.get('coefficients'), policy)
            old_beta = coefficients(payload.get('compare_coefficients'), old_policy)
            new = self.weighted_retrieve(case, policy, beta)
            old = self.weighted_retrieve(case, old_policy, old_beta)
            def positions(values):
                return {int(c): i + 1 for i, c in enumerate(values)}
            new_rank, old_rank = positions(new['before']), positions(old['before'])
            new_pos, old_pos = positions(new['order']), positions(old['order'])
            new_full, old_full = set(new['full']), set(old['full'])
            gold = set(self.gold['questions'][case['meta']['question_id']])
            linked = {cid: len(set(self.units[cid]['artifact_ids']) & gold) for cid in self.ids}
            movements = [{'chunk_id': cid, 'old_rank': old_rank.get(i), 'new_rank': new_rank.get(i),
                'old_position': old_pos.get(i), 'new_position': new_pos.get(i),
                'gold_pointer_count': linked[cid], 'old_delivered': cid in old_full,
                'new_delivered': cid in new_full, 'score': float(new['score'][i]),
                'old_score': float(old['score'][i]), 'in_area': bool(case['area_mask'][i]) if case['area_mask'] is not None else None,
                'nomination_depth': int(new['nomination'][i]) if new['nomination'][i] <= self.n else None,
                'recovered_depth': int(new['recovered'][i]) if new['recovered'][i] <= self.n else None,
                'stream_contributions': [float(x) for x in new['streams'][:, i]]}
                for i, cid in enumerate(self.ids)]
            movements.sort(key=lambda r: (r['new_position'] is None, r['new_position'] or self.n + 1))
            return {'case_id': payload['case_id'], 'policy': policy, 'comparison_policy': old_policy,
                'coefficients': beta.tolist(), 'compare_coefficients': old_beta.tolist(),
                'summary': self.evaluate(case, new), 'comparison_summary': self.evaluate(case, old),
                'movements': movements, 'gold_pointers': [{'artifact_id': aid,
                    'chunk_ids': list(self.gold['artifacts'][aid]), 'old_credited': aid in old['credit'],
                    'new_credited': aid in new['credit']} for aid in sorted(gold)],
                'timing_ms': round(1000 * (time.perf_counter() - started), 1),
                'score_parity_error': case['score_parity_error'], 'mode': 'cached_retrieval_no_model_calls',
                'note': 'Custom coefficients are exploratory score multipliers, not relevance probabilities. Leaderboard settings include their recorded coefficients. ID metrics are not exhaustive relevance judgments.'}
