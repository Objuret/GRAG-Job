"""Cross-check of the regex extraction: every corpus identifier value found as a whole token in
the references, by kind, against the identifiers the regexes extracted. Counts only."""
import pickle
import re
from collections import Counter

from common import corpus_identifiers, question_set, questions, reference

SCR = "C:/Users/jocke/AppData/Local/Temp/claude/c--Coding-exjobbet-GRAG-Job/9c164e78-008e-41e9-85f3-58c55027a64c/scratchpad/exact_check"
per_q = pickle.load(open(f"{SCR}/ref_identifiers.pkl", "rb"))
qs = questions()
ids = question_set()
refs = {i: reference(qs[i]) for i, _ in ids}
kinds = corpus_identifiers()
BEFORE = r"(?<![A-Za-z0-9_])"
AFTER_ID = r"(?![A-Za-z0-9_])"
AFTER_URL = r"(?![A-Za-z0-9_\-])(?![/?#.%=&~+:@][A-Za-z0-9_\-])"

found = {i: set() for i in refs}
per_kind = Counter()
for k, vals in kinds.items():
    after = AFTER_URL if "link" in k else AFTER_ID
    for i, r in refs.items():
        for v in vals:
            if v in r and re.search(BEFORE + re.escape(v) + after, r):
                found[i].add(v)
                per_kind[k] += 1
print("corpus values found as whole tokens in the references, by kind:", dict(per_kind))
agree = sum(1 for i in refs if found[i] == set(per_q[i]))
print("questions where the dictionary set equals the regex set:", agree, "of", len(refs))
print("identifiers found by the dictionary only:", sum(len(found[i] - set(per_q[i])) for i in refs),
      "| by the regexes only:", sum(len(set(per_q[i]) - found[i]) for i in refs))
