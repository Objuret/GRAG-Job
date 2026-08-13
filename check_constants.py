"""check_constants.py — hold `v3/CONSTANTS.md` to the source it describes.

The inventory records, per row, a file, a symbol and the symbol's value. This
reads every row back, parses the named source file with `ast`, resolves the
module-level assignment, and compares the value the table records against the
value the code actually carries. A default that drifts while the table keeps the
old number is the failure this exists to catch; a symbol that disappeared is the
easy half.

    python check_constants.py            # verify every row, exit 1 on a defect
    python check_constants.py --counts   # recount the provenance classes
    python check_constants.py -v         # list every row, not just the defects

Rows that name no symbol — a bare literal inside a function, a Cypher constant,
a docstring claim — are reported UNCHECKED and counted apart. They are honest
gaps in what a parser can reach, not failures.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
DOC = REPO / "v3" / "CONSTANTS.md"
SRC_ROOT = REPO / "v3"

OK = "OK"
MISMATCH = "VALUE MISMATCH"
MISSING = "SYMBOL MISSING"
UNPARSEABLE = "UNPARSEABLE"
UNCHECKED = "UNCHECKED"

PROVENANCE = ("unknown", "derived", "borrowed", "user-specified", "swept")


class Unknown:
    """A value this parser cannot derive from the source expression."""

    def __repr__(self) -> str:
        return "<unresolvable>"


UNRESOLVED = Unknown()


# --- the document ------------------------------------------------------------

def parse_rows(text: str) -> list:
    """Every table row -> {constant, value, where, provenance}. Header and
    separator rows drop; a row with fewer than five cells is not an inventory
    row."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line[1:-1])]
        if len(cells) != 5:
            continue
        if cells[0] in ("constant", "provenance") or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append({"constant": cells[0], "value": cells[1],
                     "where": cells[2], "provenance": cells[4]})
    return rows


def where_target(cell: str):
    """(relative source path, symbol) for a row that names a module-level
    symbol, else None. Two backticked parts and an identifier second part is
    the symbol form; anything else locates a bare literal."""
    parts = re.findall(r"`([^`]+)`", cell)
    if len(parts) == 2 and parts[1].isidentifier():
        return parts[0], parts[1]
    return None


def value_claim(cell: str):
    """The machine-readable value a row claims, or None when the cell is prose.
    A claim is the whole cell wrapped in one pair of backticks; a `\\|` inside it
    is the table's escape for a literal pipe."""
    cell = cell.strip()
    m = re.fullmatch(r"`([^`]*)`", cell)
    if not m:
        return None
    return m.group(1).replace("\\|", "|")


def provenance_of(cell: str):
    for name in PROVENANCE:
        if f"**{name}**" in cell:
            return name
    return None


# --- the source --------------------------------------------------------------

_MODULES: dict = {}


def module_symbols(rel: str):
    """{name: value-expression node} for every module-level assignment in
    `rel`, in file order. None when the file does not exist or does not parse."""
    if rel in _MODULES:
        return _MODULES[rel]
    path = SRC_ROOT / rel
    table = None
    if path.is_file() and path.suffix == ".py":
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            tree = None
        if tree is not None:
            table = {}
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    targets = [node.target]
                else:
                    continue
                for t in targets:
                    if isinstance(t, ast.Name):
                        table[t.id] = node.value
    _MODULES[rel] = table
    return table


def _dotted(node):
    """'os.environ.get' for an attribute/name call target, else ''."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _path_join(left, right):
    if isinstance(left, str) and isinstance(right, str):
        return f"{left}/{right}" if left else right
    if isinstance(right, str):
        return right          # an unresolvable root: keep the literal suffix
    return UNRESOLVED


def resolve(node, syms: dict, depth: int = 0):
    """The value of one expression, resolving module constants, environment
    defaults, path joins and simple arithmetic. UNRESOLVED when the expression
    reaches beyond that."""
    if node is None or depth > 24:
        return UNRESOLVED

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        target = syms.get(node.id)
        return resolve(target, syms, depth + 1) if target is not None else UNRESOLVED

    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        items = [resolve(e, syms, depth + 1) for e in node.elts]
        if any(isinstance(i, Unknown) for i in items):
            return UNRESOLVED
        if isinstance(node, ast.Set):
            return set(items)
        return tuple(items) if isinstance(node, ast.Tuple) else list(items)

    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            rk = resolve(k, syms, depth + 1)
            rv = resolve(v, syms, depth + 1)
            if isinstance(rk, Unknown) or isinstance(rv, Unknown):
                return UNRESOLVED
            out[rk] = rv
        return out

    if isinstance(node, ast.BinOp):
        left = resolve(node.left, syms, depth + 1)
        right = resolve(node.right, syms, depth + 1)
        if isinstance(node.op, ast.Div):
            if (isinstance(left, (int, float)) and isinstance(right, (int, float))
                    and not isinstance(left, bool) and not isinstance(right, bool)):
                return left / right if right else UNRESOLVED
            return _path_join(left, right)
        if isinstance(left, Unknown) or isinstance(right, Unknown):
            return UNRESOLVED
        try:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Pow):
                return left ** right
            if isinstance(node.op, ast.LShift):
                return left << right
        except Exception:
            return UNRESOLVED
        return UNRESOLVED

    if isinstance(node, ast.Compare):
        left = resolve(node.left, syms, depth + 1)
        for op, comparator in zip(node.ops, node.comparators):
            right = resolve(comparator, syms, depth + 1)
            if isinstance(right, Unknown):
                return UNRESOLVED
            try:
                if isinstance(op, ast.Eq):
                    result = left == right
                elif isinstance(op, ast.NotEq):
                    result = left != right
                elif isinstance(op, ast.In):
                    result = left in right
                elif isinstance(op, ast.NotIn):
                    result = left not in right
                else:
                    return UNRESOLVED
            except Exception:
                return UNRESOLVED
            if not result:
                return False
            left = right
        return True

    if isinstance(node, ast.Call):
        name = _dotted(node.func)
        args = node.args
        if name in ("os.environ.get", "environ.get"):
            if len(args) >= 2:
                return resolve(args[1], syms, depth + 1)
            return None
        if name in ("_env_float", "_env_int", "_env_bool", "_env_str") and len(args) >= 2:
            value = resolve(args[1], syms, depth + 1)
            if isinstance(value, Unknown):
                return UNRESOLVED
            if name == "_env_float":
                return float(value)
            if name == "_env_int":
                return int(value)
            if name == "_env_bool":
                return bool(value)
            return value
        if name in ("float", "int", "str", "list", "tuple", "set", "sorted", "len",
                    "Path", "max", "min") and args:
            values = [resolve(a, syms, depth + 1) for a in args]
            if any(isinstance(v, Unknown) for v in values):
                return UNRESOLVED
            try:
                if name == "float":
                    return float(values[0])
                if name == "int":
                    return int(values[0])
                if name == "str":
                    return str(values[0])
                if name == "list":
                    return list(values[0])
                if name == "tuple":
                    return tuple(values[0])
                if name == "set":
                    return set(values[0])
                if name == "sorted":
                    return sorted(values[0])
                if name == "len":
                    return len(values[0])
                if name == "Path":
                    return str(values[0])
                if name == "max":
                    return max(values) if len(values) > 1 else max(values[0])
                if name == "min":
                    return min(values) if len(values) > 1 else min(values[0])
            except Exception:
                return UNRESOLVED
        if args and (name.endswith("compile")
                     or (isinstance(node.func, ast.Attribute)
                         and node.func.attr == "compile")):
            return resolve(args[0], syms, depth + 1)
        return UNRESOLVED

    return UNRESOLVED


def size_of(node, syms: dict):
    """The element count of a collection expression, read structurally so a
    collection of unresolvable elements still yields its length. None when the
    expression is not a sized collection."""
    if isinstance(node, ast.Dict):
        return len(node.keys)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return len(node.elts)
    if isinstance(node, (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        if len(node.generators) == 1 and not node.generators[0].ifs:
            return size_of(node.generators[0].iter, syms)
        return None
    if isinstance(node, ast.Call):
        name = _dotted(node.func)
        if name in ("list", "tuple", "set", "sorted", "enumerate", "reversed") and node.args:
            inner = size_of(node.args[0], syms)
            if inner is not None:
                return inner
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = size_of(node.left, syms), size_of(node.right, syms)
        if a is not None and b is not None:
            return a + b
    if isinstance(node, ast.Name):
        target = syms.get(node.id)
        if target is not None:
            return size_of(target, syms)
    value = resolve(node, syms)
    if isinstance(value, (str, bytes)) or isinstance(value, Unknown):
        return None
    try:
        return len(value)
    except TypeError:
        return None


# --- comparison ---------------------------------------------------------------

def _same(claimed, actual) -> bool:
    if isinstance(claimed, bool) or isinstance(actual, bool):
        return claimed is actual
    if isinstance(claimed, (int, float)) and isinstance(actual, (int, float)):
        return float(claimed) == float(actual)
    if isinstance(claimed, str) and isinstance(actual, (int, float)):
        try:
            return float(claimed) == float(actual)
        except ValueError:
            return False
    if isinstance(actual, str) and isinstance(claimed, (int, float)):
        try:
            return float(actual) == float(claimed)
        except ValueError:
            return False
    if isinstance(claimed, (list, tuple)) and isinstance(actual, (list, tuple)):
        return list(claimed) == list(actual)
    if isinstance(claimed, (set, frozenset)) and isinstance(actual, (set, frozenset)):
        return set(claimed) == set(actual)
    return claimed == actual


def check_value(claim: str, node, syms: dict):
    """(status, detail) for one row's value claim against its assignment."""
    actual = resolve(node, syms)

    count = re.match(r"^(\d+)\s+\S", claim)
    if count:
        size = size_of(node, syms)
        if size is None:
            return UNPARSEABLE, "code expression is not a sized collection"
        want = int(count.group(1))
        if size == want:
            return OK, ""
        return MISMATCH, f"table says {want} items, code has {size}"

    if claim in ("off", "on"):
        if isinstance(actual, bool):
            return (OK, "") if actual is (claim == "on") else (
                MISMATCH, f"table says {claim}, code defaults {'on' if actual else 'off'}")
        return UNPARSEABLE, "code expression does not resolve to a flag"

    try:
        claimed = ast.literal_eval(claim)
    except (ValueError, SyntaxError):
        claimed = claim if isinstance(actual, str) else None

    if claimed is None:
        return UNPARSEABLE, "table value is not machine-readable"
    if isinstance(actual, Unknown):
        return UNPARSEABLE, "code expression does not resolve to a value"
    if _same(claimed, actual):
        return OK, ""
    return MISMATCH, f"table says {claimed!r}, code says {actual!r}"


# --- run ----------------------------------------------------------------------

def main() -> int:
    print("check_constants: reading v3/CONSTANTS.md against v3/ source …", flush=True)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--counts", action="store_true",
                    help="print the provenance tally and exit")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print every row, not only the defects")
    args = ap.parse_args()

    if not DOC.is_file():
        print(f"  no inventory at {DOC}", flush=True)
        return 1
    rows = parse_rows(DOC.read_text(encoding="utf-8"))
    print(f"  {len(rows)} rows", flush=True)

    if args.counts:
        tally = {name: 0 for name in PROVENANCE}
        unclassed = 0
        for row in rows:
            name = provenance_of(row["provenance"])
            if name is None:
                unclassed += 1
                print(f"  no provenance class: {row['constant']}", flush=True)
            else:
                tally[name] += 1
        print(f"\ntotal rows: {len(rows)}", flush=True)
        for name in PROVENANCE:
            print(f"  {name:<16} {tally[name]}", flush=True)
        if unclassed:
            print(f"  unclassified     {unclassed}", flush=True)
        return 1 if unclassed else 0

    results = []
    for i, row in enumerate(rows, 1):
        if i % 40 == 0:
            print(f"  … {i}/{len(rows)}", flush=True)
        target = where_target(row["where"])
        if target is None:
            results.append((row, UNCHECKED, "no module-level symbol named"))
            continue
        rel, symbol = target
        syms = module_symbols(rel)
        if syms is None:
            results.append((row, MISSING, f"no parseable source at v3/{rel}"))
            continue
        if symbol not in syms:
            results.append((row, MISSING, f"{symbol} is not assigned at module level in v3/{rel}"))
            continue
        claim = value_claim(row["value"])
        if claim is None:
            results.append((row, UNPARSEABLE, "table value is prose, symbol exists"))
            continue
        status, detail = check_value(claim, syms[symbol], syms)
        results.append((row, status, detail))

    tally = {OK: 0, MISMATCH: 0, MISSING: 0, UNPARSEABLE: 0, UNCHECKED: 0}
    for row, status, detail in results:
        tally[status] += 1
        if status in (MISMATCH, MISSING) or args.verbose:
            where = row["where"].replace("`", "")
            line = f"  {status:<14} {row['constant']:<38} {where}"
            print(line + (f"\n                 {detail}" if detail and status != OK else ""),
                  flush=True)

    print(f"\n{len(rows)} rows: {tally[OK]} ok, {tally[MISMATCH]} value mismatch, "
          f"{tally[MISSING]} symbol missing, {tally[UNPARSEABLE]} value unchecked, "
          f"{tally[UNCHECKED]} unchecked (no symbol)", flush=True)
    return 1 if (tally[MISMATCH] or tally[MISSING]) else 0


if __name__ == "__main__":
    sys.exit(main())
