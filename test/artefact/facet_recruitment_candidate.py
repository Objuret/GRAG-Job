"""Disposable frontier nomination followed by exact-record context recovery.

Scores and nomination ranks remain untouched. Context recovery inherits the
earliest supported member depth only within an overlapping/touching character
range component of the same record endpoint. This is not a new relevance score.
"""
from collections import defaultdict
import hashlib
import json

from artefact.facet_need_frontier import merge_frontiers


_RECORD_FIELDS = ("parent_ref", "id", "index", "field", "section")


def _components(chunks):
    records = defaultdict(list)
    ranged = set()
    for chunk in chunks:
        locator = chunk["locator"]
        loc = json.loads(locator) if isinstance(locator, str) else locator
        if not isinstance(loc, dict):
            raise ValueError("locator must be an object or a JSON object")
        if "char_range" not in loc:
            continue
        if not chunk["relpath"] or any(loc.get(k) is None for k in _RECORD_FIELDS):
            raise ValueError("ranged chunks require a complete exact-record identity")
        bounds = loc["char_range"]
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise ValueError("char_range must contain start and end")
        start, end = bounds
        if type(start) is not int or type(end) is not int or not 0 <= start < end:
            raise ValueError("char_range must be a positive half-open integer interval")
        key = (chunk["relpath"],) + tuple(loc[k] for k in _RECORD_FIELDS)
        try:
            records[key].append((start, end, chunk["chunkId"]))
        except TypeError as exc:
            raise ValueError("record identity values must be hashable") from exc
        ranged.add(chunk["chunkId"])
    components = []
    # Canonical ordering also handles differing scalar types in record IDs.
    for key, intervals in sorted(records.items(), key=lambda item: json.dumps(item[0], sort_keys=True)):
        current, right, pieces = [], -1, []
        for start, end, cid in sorted(intervals):
            if current and start > right:
                pieces.append(current)
                current = []
            current.append((start, end, cid))
            right = max(right, end) if len(current) > 1 else end
        if current:
            pieces.append(current)
        for part in pieces:
            payload = {
                "record": dict(zip(("relpath",) + _RECORD_FIELDS, key)),
                "members": [{"chunk_id": cid, "char_range": [start, end]}
                            for start, end, cid in part],
            }
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            components.append({"component_id": digest, **payload})
    return components, ranged, len(records)


def recruit_with_record_context(*, chunk_rows, stream_ids, stream_scores,
                                source_character_budget=None):
    """Return original nominations and recovered whole-frontier source context.

    Rows must align with score columns and provide chunkId, locator, relpath and
    source_text. ``None`` selects every supported recovered frontier. An explicit
    nonnegative integer budget selects only a prefix of complete frontiers; it
    never skips an oversized frontier to admit a cheaper later one. Cost is the
    sum of Python source-text character lengths per unique chunk, including
    repeated overlap. This is not token or production-serialization accounting.

    ``context_added`` means context advanced original nomination depth, including
    recovery of an unsupported sibling. Original stream ranks and scores are
    not imputed to that sibling; they remain solely in ``nomination``.
    Within a recovered frontier, original nominations precede advanced context.
    This keeps a later serving prefix cut from spending its budget on recovered
    siblings before the evidence that nominated that frontier.
    """
    chunks = list(chunk_rows)
    nomination = merge_frontiers([chunk["chunkId"] for chunk in chunks], stream_ids, stream_scores)
    return recover_from_nomination(chunk_rows=chunks, nomination=nomination,
                                   source_character_budget=source_character_budget)


def recover_from_nomination(*, chunk_rows, nomination, source_character_budget=None):
    """Recover exact-record context after an explicitly supplied ordinal schedule.

    Nomination depths are positive ordinal positions, never replacement relevance
    scores. The nomination must cover each chunk exactly once, including entries
    with no support (depth None). Original nomination metadata is preserved.
    """
    if source_character_budget is not None and (
        type(source_character_budget) is not int or source_character_budget < 0
    ):
        raise ValueError("source_character_budget must be None or a nonnegative integer")
    chunks = list(chunk_rows)
    ids = [chunk["chunkId"] for chunk in chunks]
    nominated = [row["chunk_id"] for row in nomination["rows"]]
    if len(set(ids)) != len(ids) or len(nominated) != len(ids) or set(nominated) != set(ids):
        raise ValueError("nomination must cover every unique chunk exactly once")
    if any(row["depth"] is not None and (type(row["depth"]) is not int or row["depth"] < 1)
           for row in nomination["rows"]):
        raise ValueError("nomination depth must be a positive integer or None")
    for chunk in chunks:
        if not isinstance(chunk["source_text"], str):
            raise ValueError("source_text must be a string")
        # These fields are required even for a non-ranged singleton.
        chunk["locator"], chunk["relpath"]
    chunk_map = {chunk["chunkId"]: chunk for chunk in chunks}
    components, ranged, record_count = _components(chunks)
    original = {row["chunk_id"]: row["depth"] for row in nomination["rows"]}
    depths, triggers, memberships = dict(original), {}, {}
    for component in components:
        members = [member["chunk_id"] for member in component["members"]]
        support = [original[cid] for cid in members if original[cid] is not None]
        depth = min(support) if support else None
        sponsors = sorted(cid for cid in members if depth is not None and original[cid] == depth)
        for cid in members:
            depths[cid] = depth
            triggers[cid] = sponsors
            memberships[cid] = component["component_id"]

    grouped = defaultdict(list)
    for cid, depth in depths.items():
        if depth is not None:
            grouped[depth].append(cid)
    frontiers, intervals, cumulative, cumulative_chars = [], {}, 0, 0
    selected, crossing, selected_chars = [], [], 0
    crossed = False
    for depth, members in sorted(grouped.items()):
        members.sort(key=lambda cid: (original[cid] != depth, cid))
        cost = sum(len(chunk_map[cid]["source_text"]) for cid in members)
        first = cumulative + 1
        cumulative += len(members)
        cumulative_chars += cost
        intervals[depth] = first, cumulative
        frontiers.append({"depth": depth, "chunk_ids": members, "size": len(members),
                          "source_characters": cost, "cumulative_size": cumulative,
                          "cumulative_source_characters": cumulative_chars})
        if not crossed:
            if source_character_budget is not None and selected_chars + cost > source_character_budget:
                crossing, crossed = members, True
            else:
                selected.extend(members)
                selected_chars += cost
    recovered = []
    for cid in sorted(original, key=lambda cid: (
        depths[cid] is None, depths[cid] or 0, original[cid] != depths[cid], cid
    )):
        depth = depths[cid]
        first, last = intervals.get(depth, (None, None))
        recovered.append({"chunk_id": cid, "original_depth": original[cid], "depth": depth,
                          "first_position": first, "last_position": last,
                          "component_id": memberships.get(cid),
                          "trigger_chunk_ids": triggers.get(cid, [cid] if depth is not None else []),
                          "context_added": depth is not None and depth != original[cid]})
    return {
        "nomination": nomination, "components": components, "rows": recovered,
        "frontiers": frontiers, "selected_chunk_ids": selected,
        "selected_source_characters": selected_chars,
        "source_character_budget": source_character_budget,
        "unused_capacity": None if source_character_budget is None else source_character_budget - selected_chars,
        "crossing_frontier_chunk_ids": crossing,
        "crossing_frontier_source_characters": sum(len(chunk_map[cid]["source_text"]) for cid in crossing),
        "unsupported_chunk_ids": sorted(cid for cid, depth in depths.items() if depth is None),
        "counts": {"chunks": len(chunks), "char_range_chunks": len(ranged),
                   "logical_records": record_count, "contiguous_components": len(components),
                   "multi_chunk_components": sum(len(c["members"]) > 1 for c in components),
                   "non_range_singletons": len(chunks) - len(ranged)},
    }
