"""querytagger: what the parser keeps, what it refuses, and what the key answers for.
No model call — synthetic payloads only."""
import json
import unittest

from artefact.querytagger import (
    ALL_FACETS, FILLER, SYSTEM_V1, cache_key, extract_json, parse_payload, prompt_for, signature,
)


def facets(**over):
    f = {name: 0.5 for name in ALL_FACETS}
    f.update(over)
    return f


GOOD = {
    "description": "  A meeting transcript discussing a pricing change and its rollout.  ",
    "tags": [
        {"t": "pricing  change", "facets": facets(topic=1.0, temporal=0.0)},
        {"t": "Pricing Change", "facets": facets()},
        {"t": "rollout plan", "facets": facets(activity=1)},
        {"t": "data", "facets": facets()},
        {"t": "x", "facets": facets()},
    ],
}


class Parser(unittest.TestCase):

    def test_keeps_description_tags_and_five_facets(self):
        plan = parse_payload(json.loads(json.dumps(GOOD)))
        self.assertEqual(plan["description"],
                         "A meeting transcript discussing a pricing change and its rollout.")
        self.assertEqual([t["t"] for t in plan["tags"]], ["pricing change", "rollout plan"])
        self.assertEqual(set(plan["tags"][0]["facets"]), set(ALL_FACETS))
        self.assertEqual(plan["tags"][0]["facets"]["topic"], 1.0)
        self.assertEqual(plan["tags"][0]["facets"]["temporal"], 0.0)
        self.assertIsInstance(plan["tags"][1]["facets"]["activity"], float)

    def test_filler_and_one_character_tags_are_dropped(self):
        self.assertIn("data", FILLER)
        plan = parse_payload(json.loads(json.dumps(GOOD)))
        self.assertNotIn("data", [t["t"] for t in plan["tags"]])
        self.assertNotIn("x", [t["t"] for t in plan["tags"]])

    def test_empty_description_refused(self):
        bad = {"description": "   ", "tags": GOOD["tags"]}
        with self.assertRaises(ValueError):
            parse_payload(bad)

    def test_missing_facet_refused(self):
        f = facets()
        f.pop("evidence")
        with self.assertRaises(ValueError):
            parse_payload({"description": "d", "tags": [{"t": "pricing", "facets": f}]})

    def test_facet_out_of_range_refused(self):
        with self.assertRaises(ValueError):
            parse_payload({"description": "d",
                           "tags": [{"t": "pricing", "facets": facets(topic=1.4)}]})

    def test_non_numeric_facet_refused(self):
        for v in ("0.5", None, True):
            with self.assertRaises(ValueError):
                parse_payload({"description": "d",
                               "tags": [{"t": "pricing", "facets": facets(topic=v)}]})

    def test_no_surviving_tag_refused(self):
        with self.assertRaises(ValueError):
            parse_payload({"description": "d", "tags": [{"t": "data", "facets": facets()}]})

    def test_empty_tag_list_refused(self):
        with self.assertRaises(ValueError):
            parse_payload({"description": "d", "tags": []})


class Json(unittest.TestCase):

    def test_fenced_and_trailing_prose(self):
        raw = 'here you go:\n```json\n{"description":"d","tags":[]}\n```\nthanks'
        self.assertEqual(extract_json(raw), {"description": "d", "tags": []})

    def test_brace_inside_a_string_does_not_close_the_object(self):
        self.assertEqual(extract_json('{"description":"a } b","tags":[]}')["description"],
                         "a } b")

    def test_no_object_raises(self):
        with self.assertRaises(ValueError):
            extract_json("no json here")


class Prompt(unittest.TestCase):

    def test_the_question_is_the_only_input(self):
        system, user = prompt_for("who changed the pricing?")
        self.assertEqual(user, "Question: who changed the pricing?")
        self.assertIs(system, SYSTEM_V1)

    def test_no_scope_field_in_the_prompt(self):
        for word in ("gate", "product name", "channel name", "employee_id", "years"):
            self.assertNotIn(word, SYSTEM_V1)

    def test_key_moves_with_question_model_and_signature(self):
        a = cache_key("q one")
        self.assertNotEqual(a, cache_key("q two"))
        self.assertNotEqual(a, cache_key("q one", model="claude-sonnet-4-5"))
        self.assertEqual(a, cache_key("q one"))
        self.assertEqual(len(signature()), 64)


if __name__ == "__main__":
    unittest.main()
