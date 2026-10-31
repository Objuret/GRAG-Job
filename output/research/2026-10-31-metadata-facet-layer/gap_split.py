import sys
import numpy as np
sys.path.insert(0, r"C:\Coding\exjobbet\GRAG-Job\test\graph\facet_pairs")
import bootstrap_band as BB
z = np.load(r"C:\Coding\exjobbet\GRAG-Job\output\facet_pairs\rounds\round1\metadata_pool\bootstrap\scores_b24.npz")
S, ids = z["scores"], [str(e) for e in z["edge_ids"]]
N_OLD, N = 61018, len(ids)
facets = [str(f) for f in z["facets"]]
def gaps(any_pairs, same_pairs):
    out = {}
    for i, f in enumerate(facets):
        out[f] = BB.flip_gap(S[:, i, :], any_pairs)["gap"]
    stacked = np.concatenate([S[:, i, :] for i in range(4)], axis=0)
    pooled = np.concatenate([same_pairs + i * N for i in range(4)], axis=0)
    out["pooled_same_chunk"] = BB.flip_gap(stacked, pooled)["gap"]
    return out
any_new = BB.sample_any_pairs(N, 200000, 20260921)
same_new = BB.sample_same_chunk_pairs(ids, 200000, 20260922)
any_old = BB.sample_any_pairs(N_OLD, 200000, 20260921)
same_old = BB.sample_same_chunk_pairs(ids[:N_OLD], 200000, 20260922)
both_old_any = any_new[(any_new < N_OLD).all(axis=1)]
both_old_same = same_new[(same_new < N_OLD).all(axis=1)]
print("pairs touching a new edge: any", int((any_new >= N_OLD).any(axis=1).sum()), "same_chunk", int((same_new >= N_OLD).any(axis=1).sum()))
print("(a) pairs drawn over the 61,018 stored indices:", gaps(any_old, same_old))
print("(b) pairs drawn over 61,592, only pairs of two stored edges:", gaps(both_old_any, both_old_same))
print("(c) pairs drawn over 61,592, all (the new BANDS.md):", gaps(any_new, same_new))
