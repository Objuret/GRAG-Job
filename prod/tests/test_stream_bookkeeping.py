"""Large trace bookkeeping stays streaming and preserves torn-tail semantics."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness import jsonl, orchestrator


class StreamingBookkeeping(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'arm_outputs.jsonl'

    def write(self, value):
        self.path.write_text(value, encoding='utf-8', newline='')

    def test_real_bookkeeping_avoids_bulk_read(self):
        self.write('\n'.join(json.dumps(record) for record in [
            {'id': 'a', 'meta': {'char_budget': {'exhausted': True}}, 'trace': 'x' * 200000},
            {'id': 'b', 'meta': {'char_budget': {'exhausted': False}}},
            {'id': 'c', 'meta': None},
        ]) + '\n{"id":')
        with patch.object(Path, 'read_text', side_effect=AssertionError('bulk read forbidden')):
            self.assertEqual(orchestrator._done_ids(self.path), {'a', 'b', 'c'})
            self.assertEqual(orchestrator._n_exhausted(self.path), 1)

    def test_missing_and_blank_files(self):
        self.assertEqual(jsonl.load(self.path), [])
        self.write(' \r\n\t\n')
        self.assertEqual(jsonl.load(self.path), [])

    def test_blank_lines_crlf_and_final_without_newline(self):
        self.write(' \r\n{"id": 1}\r\n\t\r\n{"id": 2}')
        self.assertEqual(jsonl.load(self.path), [{'id': 1}, {'id': 2}])

    def test_torn_tail_followed_only_by_blank_lines(self):
        self.write('{"id": 1}\n{"id":\n  \r\n')
        self.assertEqual(jsonl.load(self.path), [{'id': 1}])

    def test_corruption_before_later_nonblank_line_raises(self):
        for later in ('{"id": 2}', '{"id":'):
            with self.subTest(later=later):
                self.write('{"id": 1}\nBROKEN\n\n' + later)
                with self.assertRaises(json.JSONDecodeError):
                    jsonl.load(self.path)

    def test_iterator_parses_only_requested_record(self):
        self.write('{"id": 1}\n{"id": 2}\n')
        with patch.object(jsonl.json, 'loads', wraps=json.loads) as decode:
            records = jsonl.iter_records(self.path)
            self.assertEqual(decode.call_count, 0)
            self.assertEqual(next(records), {'id': 1})
            self.assertEqual(decode.call_count, 1)
            records.close()
