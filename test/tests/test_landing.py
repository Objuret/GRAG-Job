"""land: literal, nearest-unique, first-name ambiguity; combine: where the landings meet."""
import unittest

from artefact.landing import (CHANNEL, FIRST, FULL, PRODUCT, Areas, Hit, Landing,
                              combine, land)


def synthetic():
    return [
        Landing("Employee", "eid_1", "Hannah Taylor", FULL),
        Landing("Employee", "eid_1", "Hannah", FIRST),
        Landing("Employee", "eid_2", "Hannah Moreno", FULL),
        Landing("Employee", "eid_2", "Hannah", FIRST),
        Landing("Employee", "eid_3", "Peter Vaughn", FULL),
        Landing("Employee", "eid_3", "Peter", FIRST),
        Landing("Channel", "ch-1", "planning-onForceX", CHANNEL),
        Landing("Channel", "ch-2", "support-escalations", CHANNEL),
        Landing("Product", "ActionGenie", "ActionGenie", PRODUCT),
        Landing("Product", "EdgeForce", "EdgeForce", PRODUCT),
    ]


def rule_of(hits, kind):
    return sorted({h.rule for h in hits if h.kind == kind})


def nodes_of(hits, kind):
    return sorted({h.node_id for h in hits if h.kind == kind})


class Literal(unittest.TestCase):

    def test_full_name_lands_one_node(self):
        hits = land("what did Hannah Taylor decide about ActionGenie", synthetic())
        self.assertEqual(nodes_of(hits, FULL), ["eid_1"])
        self.assertEqual(rule_of(hits, FULL), ["literal"])

    def test_case_insensitive_and_whole_word(self):
        hits = land("news from PLANNING-ONFORCEX today", synthetic())
        self.assertEqual(nodes_of(hits, CHANNEL), ["ch-1"])
        self.assertEqual([h.form for h in hits if h.kind == CHANNEL],
                         ["PLANNING-ONFORCEX"])

    def test_a_name_inside_a_word_is_not_a_literal_match(self):
        hits = land("the ActionGenies release", synthetic())
        self.assertEqual(rule_of(hits, PRODUCT), ["nearest-unique"])

    def test_product_lands_literally(self):
        hits = land("which incidents hit EdgeForce", synthetic())
        self.assertEqual(nodes_of(hits, PRODUCT), ["EdgeForce"])
        self.assertEqual(rule_of(hits, PRODUCT), ["literal"])


class NearestUnique(unittest.TestCase):

    def test_one_nearest_name_is_accepted(self):
        hits = land("what did Hannah Taylr decide", synthetic())
        self.assertEqual(nodes_of(hits, FULL), ["eid_1"])
        self.assertEqual(rule_of(hits, FULL), ["nearest-unique"])
        self.assertEqual([h.form for h in hits if h.kind == FULL], ["Hannah Taylr"])

    def test_a_tie_lands_nothing(self):
        tied = [Landing("Product", "Alpha", "Alpha", PRODUCT),
                Landing("Product", "Alpba", "Alpba", PRODUCT)]
        hits = land("the Alpha release", tied)
        self.assertEqual(nodes_of(hits, PRODUCT), ["Alpha"])
        hits = land("the Alpca release", tied)
        self.assertEqual(hits, [])

    def test_a_literal_hit_does_not_stop_another_word_from_landing(self):
        hits = land("EdgeForce and ActionGene", synthetic())
        self.assertEqual(nodes_of(hits, PRODUCT), ["ActionGenie", "EdgeForce"])
        self.assertEqual(rule_of(hits, PRODUCT), ["literal", "nearest-unique"])

    def test_a_question_with_no_capitalised_word_lands_nothing(self):
        self.assertEqual(land("what did the team decide last week", synthetic()), [])

    def test_a_sentence_initial_capital_is_not_a_candidate(self):
        self.assertEqual(land("What did the team decide last week", synthetic()), [])

    def test_only_the_named_words_land(self):
        hits = land("what did Hannah Taylr decide", synthetic())
        self.assertEqual(sorted({(h.kind, h.name) for h in hits}),
                         [(FIRST, "Hannah"), (FULL, "Hannah Taylor")])


class AmbiguousFirstName(unittest.TestCase):

    def test_a_first_name_lands_on_every_employee_carrying_it(self):
        hits = land("what did Hannah say", synthetic())
        self.assertEqual(nodes_of(hits, FIRST), ["eid_1", "eid_2"])
        self.assertEqual(rule_of(hits, FIRST), ["literal"])

    def test_the_full_name_also_lands_its_first_name(self):
        hits = land("what did Hannah Taylor say", synthetic())
        self.assertEqual(nodes_of(hits, FULL), ["eid_1"])
        self.assertEqual(nodes_of(hits, FIRST), ["eid_1", "eid_2"])


def synthetic_areas():
    """eid_1 sits in a channel under ActionGenie (c2); eid_2's channel (c3) is elsewhere."""
    by_node = {
        ("Employee", "eid_1"): {"c1", "c2"},
        ("Employee", "eid_2"): {"c3"},
        ("Product", "ActionGenie"): {"c2", "c4"},
        ("Product", "EdgeForce"): {"c5"},
    }
    by_chunk = {}
    for node, chunks in by_node.items():
        for chunk in chunks:
            by_chunk.setdefault(chunk, set()).add(node)
    return Areas(by_node=by_node, by_chunk=by_chunk, by_route={})


def hits_for(*names):
    """The hits land would carry for these (kind, name) landings, over the synthetic names."""
    wanted = set(names)
    return [Hit(l.label, l.node_id, l.name, l.kind, l.name, "literal")
            for l in synthetic() if (l.kind, l.name) in wanted]


class Combine(unittest.TestCase):

    def test_two_employees_of_one_name_and_a_product_meet_on_one_chunk(self):
        area = combine(synthetic_areas(),
                       hits_for((FIRST, "Hannah"), (PRODUCT, "ActionGenie")))
        self.assertEqual(sorted(area.landings), [(FIRST, "Hannah"), (PRODUCT, "ActionGenie")])
        self.assertEqual(area.nodes[(FIRST, "Hannah")],
                         (("Employee", "eid_1"), ("Employee", "eid_2")))
        self.assertEqual(sorted(area.landings[(FIRST, "Hannah")]), ["c1", "c2", "c3"])
        self.assertEqual(sorted(area.chunks), ["c2"])
        self.assertEqual(area.unmet, ())

    def test_every_chunk_carries_the_landings_that_reach_it(self):
        area = combine(synthetic_areas(),
                       hits_for((FIRST, "Hannah"), (PRODUCT, "ActionGenie")))
        self.assertEqual(area.by_chunk["c2"], ((FIRST, "Hannah"), (PRODUCT, "ActionGenie")))
        self.assertEqual(area.by_chunk["c4"], ((PRODUCT, "ActionGenie"),))
        self.assertEqual(area.by_chunk["c1"], ((FIRST, "Hannah"),))

    def test_a_single_landing_is_its_own_area(self):
        area = combine(synthetic_areas(), hits_for((PRODUCT, "ActionGenie")))
        self.assertEqual(sorted(area.landings), [(PRODUCT, "ActionGenie")])
        self.assertEqual(sorted(area.chunks), ["c2", "c4"])
        self.assertEqual(area.unmet, ())

    def test_landings_that_do_not_meet_come_back_empty_and_named(self):
        area = combine(synthetic_areas(),
                       hits_for((FIRST, "Hannah"), (PRODUCT, "EdgeForce")))
        self.assertEqual(sorted(area.chunks), [])
        self.assertEqual(sorted(area.unmet), [(FIRST, "Hannah"), (PRODUCT, "EdgeForce")])

    def test_the_full_name_and_the_first_name_are_two_landings(self):
        area = combine(synthetic_areas(),
                       hits_for((FULL, "Hannah Taylor"), (FIRST, "Hannah"),
                                (PRODUCT, "ActionGenie")))
        self.assertEqual(sorted(area.landings),
                         [(FIRST, "Hannah"), (FULL, "Hannah Taylor"),
                          (PRODUCT, "ActionGenie")])
        self.assertEqual(sorted(area.landings[(FULL, "Hannah Taylor")]), ["c1", "c2"])
        self.assertEqual(sorted(area.chunks), ["c2"])

    def test_no_landing_is_no_area(self):
        self.assertIsNone(combine(synthetic_areas(), []))

    def test_a_landing_reaching_nothing_empties_the_meet(self):
        area = combine(synthetic_areas(),
                       hits_for((FULL, "Peter Vaughn"), (PRODUCT, "ActionGenie")))
        self.assertEqual(sorted(area.landings[(FULL, "Peter Vaughn")]), [])
        self.assertEqual(sorted(area.chunks), [])
        self.assertEqual(sorted(area.unmet),
                         [(FULL, "Peter Vaughn"), (PRODUCT, "ActionGenie")])

    def test_every_kind_land_reports_is_a_landing_of_the_meet(self):
        hits = land("what did Hannah do on ActionGenie", synthetic())
        area = combine(synthetic_areas(), hits)
        self.assertEqual(sorted(area.landings),
                         [(FIRST, "Hannah"), (PRODUCT, "ActionGenie")])
        self.assertEqual(sorted(area.chunks), ["c2"])


class DropEmpty(unittest.TestCase):

    def test_a_landing_reaching_nothing_is_dropped_and_named(self):
        area = combine(synthetic_areas(),
                       hits_for((FULL, "Peter Vaughn"), (PRODUCT, "ActionGenie")),
                       drop_empty=True)
        self.assertEqual(sorted(area.landings), [(PRODUCT, "ActionGenie")])
        self.assertEqual(sorted(area.chunks), ["c2", "c4"])
        self.assertEqual(area.dropped, ((FULL, "Peter Vaughn"),))
        self.assertEqual(area.unmet, ())
        self.assertNotIn((FULL, "Peter Vaughn"), area.nodes)

    def test_every_landing_dropped_leaves_no_landing_and_no_chunk(self):
        area = combine(synthetic_areas(), hits_for((FULL, "Peter Vaughn")), drop_empty=True)
        self.assertEqual(area.landings, {})
        self.assertEqual(area.chunks, frozenset())
        self.assertEqual(area.dropped, ((FULL, "Peter Vaughn"),))

    def test_landings_that_reach_chunks_are_read_as_before(self):
        hits = hits_for((FIRST, "Hannah"), (PRODUCT, "EdgeForce"))
        kept = combine(synthetic_areas(), hits, drop_empty=True)
        plain = combine(synthetic_areas(), hits)
        self.assertEqual(kept.landings, plain.landings)
        self.assertEqual(kept.chunks, plain.chunks)
        self.assertEqual(kept.unmet, plain.unmet)
        self.assertEqual(kept.dropped, ())


class KnownWords(unittest.TestCase):

    def test_a_word_the_corpus_carries_never_reaches_the_nearest_name_pass(self):
        names = [Landing("Employee", "eid_9", "Jack", FIRST)]
        self.assertEqual(nodes_of(land("the Slack thread", names), FIRST), ["eid_9"])
        self.assertEqual(land("the Slack thread", names, known={"slack", "thread"}), [])

    def test_a_misspelling_the_corpus_does_not_carry_still_lands(self):
        hits = land("what did Hannah Taylr decide", synthetic(),
                    known={"hannah", "taylor", "what", "did", "decide"})
        self.assertEqual(nodes_of(hits, FULL), ["eid_1"])
        self.assertEqual(rule_of(hits, FULL), ["nearest-unique"])

    def test_a_window_of_corpus_words_is_no_misspelling(self):
        names = [Landing("Employee", "eid_8", "Alice King", FULL)]
        self.assertEqual(nodes_of(land("the Engineering Kings meeting", names), FULL),
                         ["eid_8"])
        self.assertEqual(land("the Engineering Kings meeting", names,
                              known={"engineering", "kings"}), [])

    def test_literal_matches_are_read_as_before(self):
        plain = land("which incidents hit EdgeForce", synthetic())
        known = land("which incidents hit EdgeForce", synthetic(), known={"edgeforce"})
        self.assertEqual(plain, known)


if __name__ == "__main__":
    unittest.main()
