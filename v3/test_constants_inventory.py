"""The constants inventory in `v3/CONSTANTS.md` against the source it describes.

`check_constants.py` at the repo root re-reads every row that names a module-level
symbol, resolves the assignment with `ast`, and compares the value the table records
against the value the code carries. This drives that check from the suite, so a
default that moves while the table keeps the old number fails a test run rather than
waiting for a reader to notice. The counts section is held the same way: the
provenance tally printed in the document must be the tally of the document's own rows.

Rows naming no module-level symbol — a bare literal in a function, a Cypher constant,
a docstring claim — are outside what the parser can reach and are skipped here, as
the checker reports them UNCHECKED.
"""
import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "check_constants.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_constants", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load_checker()
DOC_TEXT = cc.DOC.read_text(encoding="utf-8")
ROWS = cc.parse_rows(DOC_TEXT)


class InventoryReachTests(unittest.TestCase):
    def test_the_inventory_and_its_checker_are_both_present(self):
        self.assertTrue(CHECKER.is_file(), f"no checker at {CHECKER}")
        self.assertTrue(cc.DOC.is_file(), f"no inventory at {cc.DOC}")

    def test_the_table_parses_into_rows(self):
        self.assertGreater(len(ROWS), 250, "the inventory table parsed to almost nothing")

    def test_every_row_carries_a_provenance_class(self):
        unclassed = [r["constant"] for r in ROWS if cc.provenance_of(r["provenance"]) is None]
        self.assertEqual(unclassed, [], "rows with no provenance class")


class SourceAgreementTests(unittest.TestCase):
    """Each row naming a module-level symbol, against that symbol in the source."""

    def _defects(self):
        out = []
        for row in ROWS:
            target = cc.where_target(row["where"])
            if target is None:
                continue
            rel, symbol = target
            syms = cc.module_symbols(rel)
            if syms is None:
                out.append(f"{row['constant']}: no parseable source at v3/{rel}")
                continue
            if symbol not in syms:
                out.append(f"{row['constant']}: {symbol} is not assigned at "
                           f"module level in v3/{rel}")
                continue
            claim = cc.value_claim(row["value"])
            if claim is None:
                continue          # prose value, symbol verified
            status, detail = cc.check_value(claim, syms[symbol], syms)
            if status == cc.MISMATCH:
                out.append(f"{row['constant']} ({rel} · {symbol}): {detail}")
        return out

    def test_no_recorded_value_has_drifted_from_the_code(self):
        self.assertEqual(self._defects(), [],
                         "v3/CONSTANTS.md disagrees with the source it describes")

    def test_the_check_reaches_most_of_the_table(self):
        reached = sum(1 for r in ROWS if cc.where_target(r["where"]) is not None)
        self.assertGreater(reached, len(ROWS) // 3,
                           "the checker reaches too few rows to be worth running")


class CountsSectionTests(unittest.TestCase):
    """The Counts section against the rows it claims to count."""

    @staticmethod
    def _declared_classes():
        found = {}
        for line in DOC_TEXT.splitlines():
            m = re.fullmatch(r"\|\s*([a-z-]+)\s*\|\s*(\d+)\s*\|", line.strip())
            if m and m.group(1) in cc.PROVENANCE:
                found[m.group(1)] = int(m.group(2))
        return found

    def _actual_classes(self):
        tally = {name: 0 for name in cc.PROVENANCE}
        for row in ROWS:
            name = cc.provenance_of(row["provenance"])
            if name is not None:
                tally[name] += 1
        return tally

    def test_the_declared_total_is_the_row_count(self):
        m = re.search(r"\*\*Total rows:\s*(\d+)\*\*", DOC_TEXT)
        self.assertIsNotNone(m, "the Counts section states no total")
        self.assertEqual(int(m.group(1)), len(ROWS))

    def test_the_declared_split_is_the_row_split(self):
        declared = self._declared_classes()
        self.assertEqual(set(declared), set(cc.PROVENANCE),
                         "the Counts table does not list every provenance class")
        self.assertEqual(declared, self._actual_classes())

    def test_the_classes_sum_to_the_total(self):
        self.assertEqual(sum(self._declared_classes().values()), len(ROWS))


class CheckerRunTests(unittest.TestCase):
    def test_the_checker_exits_clean(self):
        done = subprocess.run([sys.executable, str(CHECKER)],
                              capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(done.returncode, 0,
                         f"python check_constants.py failed:\n{done.stdout[-2000:]}")


if __name__ == "__main__":
    unittest.main()
