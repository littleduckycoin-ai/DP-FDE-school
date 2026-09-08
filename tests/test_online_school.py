"""Network contract checks with an in-memory transport; no learner checkout."""
import base64
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from online_school import OnlineSchool, OnlineReadError
from school import render_record


def encoded_text(value):
    return {'type': 'file', 'encoding': 'base64',
            'content': base64.b64encode(value.encode()).decode()}


def encoded_json(value):
    return encoded_text(json.dumps(value))


class OnlineSchoolTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.rev = 'a' * 40
        self.cid = 'case-04-fixture'
        self.folder = 'cases/' + self.cid + '/reflections'
        self.path = self.folder + '/learner-a-2026-09-07.md'
        self.row = {'id': 4, 'case_id': self.cid,
                    'json_file': 'cases/' + self.cid + '/base/case.json',
                    'markdown_file': 'cases/' + self.cid + '/base/case.md',
                    'source_pdf_page_range': [34, 46],
                    'reflections_dir': self.folder}

    def lesson_transport(self, path, params):
        self.requests.append((path, params))
        if path == '/commits/main':
            return {'sha': self.rev}
        self.assertEqual(params['ref'], self.rev)
        if path == '/contents/data/case-index.json':
            return encoded_json({
                'citation': {'pdf_page_url_template':
                    'https://school.example/source.pdf#page={pdf_page}'},
                'cases': [self.row]})
        return encoded_json({'identity': {'case_id': self.cid},
                             'one_sentence_intro': 'Read from the current online revision.',
                             'setting': {'source_pdf_pages': [2]},
                             'provenance': {'pdf_physical_pages': [1],
                                            'original_qa': []}})

    def record(self, second_time='2026-09-07T09:00:00+00:00'):
        def contribution(interaction_id, number, kind, text):
            return {'kind': kind, 'text': text, 'capture': 'paraphrase',
                    'confirmation': 'captured', 'source_refs': [],
                    'relates_to': [],
                    'entry_id': f'{self.cid}:learner-a:{interaction_id}:{number:02d}'}
        turns = [
            {'interaction_id': 's1-t01', 'summary': 'First thought',
             'contributions': [contribution('s1-t01', 1, 'thought', 'A learner thought.')],
             'agent_feedback': [], 'next_steps': [],
             'created_at': '2026-09-07T08:00:00+00:00'},
            {'interaction_id': 's1-t02', 'summary': 'Open question',
             'contributions': [contribution('s1-t02', 1, 'question', 'A learner question.')],
             'agent_feedback': ['Check the interview evidence.'], 'next_steps': [],
             'created_at': second_time}]
        return {'schema_version': '1.0', 'case_id': self.cid,
                'learner_id': 'learner-a', 'display_name': 'Learner A',
                'identity_source': 'self_declared', 'study_date': '2026-09-07',
                'visibility': 'shared_draft', 'interactions': turns}

    def reflection_transport(self, record=None, listing=None):
        record = record or self.record()
        listing = listing if listing is not None else [
            {'type': 'file', 'name': 'README.md',
             'path': self.folder + '/README.md'},
            {'type': 'file', 'name': Path(self.path).name, 'path': self.path}]

        def transport(path, params):
            self.requests.append((path, params))
            if path == '/commits/main':
                return {'sha': self.rev}
            self.assertEqual(params['ref'], self.rev)
            if path == '/contents/data/case-index.json':
                return encoded_json({
                    'citation': {'pdf_page_url_template':
                        'https://school.example/source.pdf#page={pdf_page}'},
                    'cases': [self.row]})
            if path == '/contents/' + self.folder:
                return listing
            if path == '/contents/' + self.path:
                return encoded_text(render_record(record))
            raise AssertionError('Unexpected request: ' + path)
        return transport

    def test_each_lesson_checks_current_head_and_pins_all_files(self):
        client = OnlineSchool(transport=self.lesson_transport)
        first = client.lesson('04')
        self.rev = 'b' * 40
        second = client.lesson(self.cid)
        self.assertEqual(first['source_commit'], 'a' * 40)
        self.assertEqual(second['source_commit'], 'b' * 40)
        self.assertEqual(second['source_url'],
                         'https://school.example/source.pdf#page=2')
        self.assertEqual(second['pdf_page_url_template'],
                         'https://school.example/source.pdf#page={pdf_page}')
        self.assertTrue(second['data_url'].endswith('/' + self.row['json_file']))
        self.assertTrue(second['case_url'].endswith('/' + self.row['markdown_file']))
        self.assertEqual(len([r for r in self.requests if r[0] == '/commits/main']), 2)
        self.assertFalse(second['local_materials_written'])

    def test_online_failure_does_not_reuse_old_material(self):
        client = OnlineSchool(transport=self.lesson_transport)
        client.lesson('04')

        def failed(path, params):
            raise OnlineReadError('No network')
        client.transport = failed
        with self.assertRaisesRegex(OnlineReadError, 'No network'):
            client.lesson('04')

    def test_partial_content_path_escape_and_bad_directory_are_rejected(self):
        client = OnlineSchool(
            transport=lambda p, q: {'type': 'file', 'encoding': 'none', 'content': ''})
        with self.assertRaisesRegex(OnlineReadError, 'complete file'):
            client.file('data/case-index.json', self.rev)
        for path in ['../outside', '/etc/passwd', 'cases\\secret']:
            with self.assertRaisesRegex(OnlineReadError, 'Unsafe'):
                client.file(path, self.rev)
        with self.assertRaisesRegex(OnlineReadError, 'directory listing'):
            client.directory('cases/case-01/reflections', self.rev)

    def test_reflections_read_every_markdown_except_readme_at_one_commit(self):
        result = OnlineSchool(
            transport=self.reflection_transport()).reflections([self.cid])
        self.assertEqual(len(result['files']), 1)
        self.assertEqual(len(result['interactions']), 2)
        self.assertEqual(len(result['records']), 2)
        self.assertEqual(result['records'][1]['kind'], 'question')
        self.assertIn('#r-s1-t02-01', result['records'][1]['source_url'])
        self.assertTrue(result['all_files_read'])
        self.assertFalse(result['local_materials_written'])
        self.assertTrue(all('/issues' not in path for path, _ in self.requests))
        pinned = [params['ref'] for path, params in self.requests
                  if path.startswith('/contents/')]
        self.assertTrue(pinned and set(pinned) == {self.rev})

    def test_cutoff_filters_interactions_inside_append_only_file(self):
        result = OnlineSchool(
            transport=self.reflection_transport()).reflections(
                ['04'], cutoff='2026-09-07T08:30:00Z')
        self.assertEqual(len(result['records']), 1)
        self.assertEqual(result['records'][0]['kind'], 'thought')
        self.assertEqual(result['interactions_after_cutoff'], 1)

    def test_empty_reflection_directory_does_not_invent_participants(self):
        result = OnlineSchool(
            transport=self.reflection_transport(listing=[])).reflections([self.cid])
        self.assertEqual(result['files'], [])
        self.assertEqual(result['records'], [])
        self.assertTrue(result['all_files_read'])

    def test_reflection_identity_must_match_file_path(self):
        wrong = self.record()
        wrong['learner_id'] = 'someone-else'
        with self.assertRaisesRegex(OnlineReadError, 'identity differs'):
            OnlineSchool(
                transport=self.reflection_transport(record=wrong)).reflections([self.cid])

    def test_bad_online_revision_and_unknown_case_are_rejected(self):
        with self.assertRaisesRegex(OnlineReadError, 'could not be verified'):
            OnlineSchool(transport=lambda p, q: {'sha': 'main'}).lesson('04')
        with self.assertRaisesRegex(OnlineReadError, 'Case not found'):
            OnlineSchool(
                transport=self.reflection_transport()).reflections(['case-99-missing'])


if __name__ == '__main__':
    unittest.main()
