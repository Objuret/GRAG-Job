"""The standard normalizers on the two numbers a chunk gets (from its tags, from its
description), on the made-up question's arrays (`structure_last_arrays.npz`): where the lowest,
the middle, the top-10% point, the top-1% point, the 4th best and the best chunk land under each.
No model call, no benchmark file, nothing uses the 72,000 cut. Run from the repo root."""
import pathlib
import sys
import warnings

import numpy as np
from scipy import stats
from sklearn.preprocessing import (MinMaxScaler, PowerTransformer, QuantileTransformer,
                                   RobustScaler, StandardScaler)

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')
HERE = pathlib.Path('output/research/2026-10-07-structure-last')
A = np.load(HERE / 'structure_last_arrays.npz')
nums = (('from the tags', A['tags'].astype(float)),
        ('from the description', A['text'].astype(float)))
N = nums[0][1].size


def col(v):
    return v.reshape(-1, 1)


def points(v):
    s = np.sort(v)
    return {'lowest': s[0], 'middle': np.median(v), 'top 10%': np.percentile(v, 90),
            'top 1%': np.percentile(v, 99), '4th best': s[-4], 'best': s[-1]}


def run(label, f, bounded):
    print(f'\n{label}' + ('' if bounded else '   (not a 0-1 scale)'))
    for name, v in nums:
        out = f(v)
        fixed = {'lowest': np.argmin(v), 'best': np.argmax(v), '4th best': np.argsort(v)[-4]}
        row = {k: out[fixed.get(k, np.argmin(np.abs(v - raw)))] for k, raw in points(v).items()}
        print(f'  {name:22s} ' + '  '.join(f'{k} {val:6.3f}' for k, val in row.items())
              + f'   skew {stats.skew(out):+.2f}')


def smallest_largest(v):
    return MinMaxScaler().fit_transform(col(v)).ravel()


def by_order(v):
    return QuantileTransformer(n_quantiles=N, output_distribution='uniform').fit_transform(col(v)).ravel()


def bell(v):
    fitted = PowerTransformer(method='yeo-johnson', standardize=True).fit(col(v))
    bell.bend = float(fitted.lambdas_[0])
    return stats.norm.cdf(fitted.transform(col(v)).ravel())


print('the raw numbers:')
for name, v in nums:
    print(f'  {name:22s} ' + '  '.join(f'{k} {val:6.2f}' for k, val in points(v).items())
          + f'   skew {stats.skew(v):+.2f}')
run('1. smallest to 0, largest to 1 (MinMaxScaler)', smallest_largest, True)
run('2. average and spread (StandardScaler)',
    lambda v: StandardScaler().fit_transform(col(v)).ravel(), False)
run('3. middle and the middle half\'s width (RobustScaler)',
    lambda v: RobustScaler().fit_transform(col(v)).ravel(), False)
run('4. by order: the fraction of chunks below it (QuantileTransformer, uniform)', by_order, True)
run('5. bent to a bell shape, then its place under the bell (PowerTransformer Yeo-Johnson, '
    'then the bell\'s 0-1)', bell, True)
for name, v in nums:
    bell(v)
    print(f'     the bend fitted from the data for {name}: {bell.bend:+.2f} (1 = no bend)')
print('\nafter each one, does 0.9 mean the same on both numbers? chunks at or above 0.9:')
for label, f in (('1. smallest/largest', smallest_largest), ('4. by order', by_order),
                 ('5. bell', bell)):
    print(f'  {label:22s} ' + '; '.join(f'{name}: {int((f(v) >= 0.9).sum())}' for name, v in nums))
