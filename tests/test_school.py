"""Exercise learning persistence and meeting evidence boundaries in isolated repos."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import school


class SchoolWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fde-school-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.rows=[]
        for n in [1,2]:
            cid=f'case-{n:02d}-fixture'
            self.rows.append({'id':n,'case_id':cid,'learning_title':f'Fixture {n}',
                'source_pdf_page_range':[1,3],
                'reflections_dir':f'cases/{cid}/reflections'})
            (self.root/self.rows[-1]['reflections_dir']).mkdir(parents=True)
        (self.root/'data').mkdir()
        (self.root/'data/case-index.json').write_text(json.dumps({'cases':self.rows}),encoding='utf-8')
        (self.root/'.gitignore').write_text('.school/\n',encoding='utf-8')

    def profile(self,learner='learner-a'):
        return school.init_identity(self.root,learner,learner.upper())

    def packet(self,turn='session-t01',kind='question',text='What evidence supports the delivery choice?',**extra):
        return {'interaction_id':turn,'contributions':[{'kind':kind,'text':text,**extra}],
                'agent_feedback':['An agent answer is not learner agreement.'],
                'next_steps':['A proposed action is not a commitment.']}

    def add(self,turn='session-t01',kind='question',text='What evidence supports the delivery choice?',
            case='01',day='2026-09-07',stamp='2026-09-07T08:00:00+00:00',private=False,**extra):
        return school.append_record(self.root,case,self.packet(turn,kind,text,**extra),day,private,stamp)

    def brief(self,meeting='test-meeting',**kwargs):
        return school.make_brief(self.root,meeting,['01','02'],working_tree=True,
                                 cutoff='2026-09-08T18:00:00+00:00',**kwargs)

    def read(self,result):
        return school.parse_record((self.root/result['path']).read_text(encoding='utf-8'))

    def commit(self):
        school.git(self.root,'init','-q','-b','main')
        school.git(self.root,'config','user.name','Fixture Author')
        school.git(self.root,'config','user.email','fixture@example.invalid')
        school.git(self.root,'add','data','cases','.gitignore')
        school.git(self.root,'commit','-qm','Fixture snapshot')
        head=school.git(self.root,'rev-parse','HEAD').strip()
        school.git(self.root,'update-ref','refs/remotes/origin/main',head)
        return head

    def test_identity_required_and_paths_cannot_escape(self):
        with self.assertRaisesRegex(ValueError,'identity is missing'):
            self.add()
        for slug in ['../outside','a/b','a\\b','UPPER','',None]:
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                school.init_identity(self.root,slug,'Name')
        self.assertEqual(list((self.root/'cases').glob('*/reflections/*.md')),[])

    def test_same_turn_retry_is_idempotent_and_changed_content_fails(self):
        self.profile()
        first=self.add()
        original=(self.root/first['path']).read_bytes()
        self.assertEqual(self.add()['status'],'unchanged')
        with self.assertRaisesRegex(ValueError,'different content'):
            self.add(text='Changed without an explicit revision')
        self.assertEqual((self.root/first['path']).read_bytes(),original)

    def test_append_preserves_previous_turn_and_separates_people_dates_cases(self):
        self.profile()
        first=self.add()
        original=deepcopy(self.read(first)['interactions'][0])
        second=self.add('session-t02',kind='thought',stamp='2026-09-07T08:01:00Z')
        self.assertEqual(first['path'],second['path'])
        self.assertEqual(self.read(second)['interactions'][0],original)
        other_day=self.add('session-t03',day='2026-09-08',stamp='2026-09-08T08:00:00Z')
        other_case=self.add('session-t04',case='02')
        self.profile('learner-b')
        other_person=self.add()
        self.assertEqual(len({x['path'] for x in [first,other_day,other_case,other_person]}),4)
        self.assertEqual(len(school.validate_reflections(self.root)),4)

    def test_revision_appends_and_cannot_change_peer_question(self):
        self.profile()
        original=self.add(kind='thought')
        revision=self.add('session-t02','revision','I changed my interpretation.',target_id=original['entry_ids'][0])
        turns=self.read(revision)['interactions']
        self.assertEqual(len(turns),2)
        self.assertEqual(turns[1]['contributions'][0]['target_id'],turns[0]['contributions'][0]['entry_id'])
        own_question=self.add('session-t03')
        self.profile('learner-b')
        with self.assertRaisesRegex(ValueError,"not in this learner"):
            self.add('session-t01','question_status','I cannot resolve another person\'s question.',
                     target_id=own_question['entry_ids'][0],state='answered')

    def test_peer_feedback_lives_in_the_authors_file(self):
        self.profile()
        original=self.add()
        old_bytes=(self.root/original['path']).read_bytes()
        self.profile('learner-b')
        feedback=self.add(kind='feedback',relates_to=original['entry_ids'])
        self.assertIn('/learner-b-',feedback['path'])
        self.assertEqual((self.root/original['path']).read_bytes(),old_bytes)
        self.assertEqual(len(school.validate_reflections(self.root)),2)

    def test_private_records_excluded_and_not_leaked_via_public_updates(self):
        self.profile()
        private=self.add(private=True)
        self.assertTrue(private['path'].startswith('.school/private/'))
        self.assertEqual(self.brief()['entry_count'],0)
        with self.assertRaisesRegex(ValueError,'private original'):
            self.add('session-t02','question_status',target_id=private['entry_ids'][0],state='answered')

    def test_source_pages_and_derived_identity_are_validated(self):
        self.profile()
        with self.assertRaisesRegex(ValueError,'outside its case'):
            self.add(source_refs=[{'case_id':'01','pdf_pages':[99]}])
        packet=self.packet()
        packet['learner_id']='learner-b'
        with self.assertRaisesRegex(ValueError,'identity comes from'):
            school.append_record(self.root,'01',packet)
        result=self.add(source_refs=[{'case_id':'01','pdf_pages':[2],'note':'Verified fixture page'}])
        self.assertEqual(self.read(result)['interactions'][0]['contributions'][0]['source_refs'][0]['case_number'],1)
        rendered=(self.root/result['path']).read_text(encoding='utf-8')
        self.assertIn('https://littleduckycoin-ai.github.io/DP-FDE-school/sources/original-interviews.pdf#page=2',rendered)

    def test_agent_feedback_does_not_close_question(self):
        self.profile()
        self.add()
        result=self.brief()
        self.assertEqual(result['question_count'],1)
        self.assertEqual(result['unresolved_question_count'],1)
        data=json.loads((self.root/'meetings/test-meeting/records.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['learner_entries']),1)
        self.assertEqual(len(data['agent_feedback']),1)
        self.assertEqual(len(data['agent_next_steps']),1)

    def test_explicit_question_state_and_reopening(self):
        self.profile()
        question=self.add()['entry_ids'][0]
        self.add('session-t02','question_status',state='discussed',target_id=question)
        self.assertEqual(self.brief()['unresolved_question_count'],1)
        self.add('session-t03','question_status',state='answered',target_id=question,stamp='2026-09-07T08:01:00Z')
        self.assertEqual(self.brief(refresh=True)['unresolved_question_count'],0)
        self.add('session-t04','question_status',state='open',target_id=question,stamp='2026-09-07T08:02:00Z')
        self.assertEqual(self.brief(refresh=True)['unresolved_question_count'],1)

    def test_cutoff_and_distinct_learners_not_message_counts(self):
        self.profile()
        self.add()
        self.add('session-t02',kind='thought',stamp='2026-09-07T08:01:00Z')
        self.profile('learner-b')
        self.add(stamp='2026-09-09T08:00:00Z')
        result=self.brief(expected=['learner-a','learner-b'])
        self.assertEqual(result['entry_count'],2)
        self.assertEqual(list(result['participants']),['learner-a'])
        text=(self.root/result['path']).read_text(encoding='utf-8')
        self.assertIn('learner-b',text)
        self.assertIn('不等于缺席',text)

    def test_refresh_keeps_synthesis_and_decisions(self):
        self.profile()
        self.add()
        self.brief()
        folder=self.root/'meetings/test-meeting'
        for name in ['synthesis.md','decisions.md']:
            (folder/name).write_text('Human-maintained work',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Meeting already exists'):
            self.brief()
        self.add('session-t02',kind='evaluation')
        self.assertEqual(self.brief(refresh=True)['entry_count'],2)
        for name in ['synthesis.md','decisions.md']:
            self.assertEqual((folder/name).read_text(encoding='utf-8'),'Human-maintained work')

    def test_default_meeting_reads_committed_snapshot_not_working_changes(self):
        self.profile()
        self.add()
        snapshot=self.commit()
        self.add('session-t02',kind='thought')
        result=school.make_brief(self.root,'from-commit',['01'],cutoff='2026-09-08T18:00:00Z')
        self.assertEqual(result['source_commit'],snapshot)
        self.assertEqual(result['entry_count'],1)
        data=json.loads((self.root/'meetings/from-commit/records.json').read_text(encoding='utf-8'))
        self.assertIn('/blob/'+snapshot+'/',data['learner_entries'][0]['source_url'])
        self.assertEqual(self.brief('from-workspace')['entry_count'],2)

    def test_history_check_accepts_append_and_rejects_rewrite_or_deletion(self):
        self.profile()
        first=self.add()
        snapshot=self.commit()
        self.add('session-t02',kind='thought')
        school.preserve_history(self.root,snapshot)
        path=self.root/first['path']
        record=self.read(first)
        record['interactions'][0]['contributions'][0]['text']='Rewritten history'
        path.write_text(school.render_record(record),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Historical learner turns changed'):
            school.preserve_history(self.root,snapshot)
        self.assertTrue(path.resolve().is_relative_to(self.root))
        path.unlink()
        with self.assertRaisesRegex(ValueError,'Historical learner file deleted'):
            school.preserve_history(self.root,snapshot)

    def test_tampered_markdown_and_duplicate_ids_rejected(self):
        self.profile()
        result=self.add()
        text=(self.root/result['path']).read_text(encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'differs from record data'):
            school.parse_record(text.replace('### 问题','### 思考',1))
        record=self.read(result)
        record['interactions'].append(deepcopy(record['interactions'][0]))
        (self.root/result['path']).write_text(school.render_record(record),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Duplicate interaction'):
            school.validate_reflections(self.root)

    def test_missing_peer_reference_rejected_and_empty_meeting_is_honest(self):
        self.profile()
        result=self.brief()
        self.assertEqual(result['entry_count'],0)
        text=(self.root/result['path']).read_text(encoding='utf-8')
        self.assertIn('没有学习记录',text)
        self.assertIn('未提供应参与名单',text)
        with self.assertRaisesRegex(ValueError,'does not exist'):
            self.add(kind='feedback',relates_to=['missing-peer-entry'])
        result=self.add(kind='feedback')
        record=self.read(result)
        record['interactions'][0]['contributions'][0]['relates_to']=['missing-peer-entry']
        (self.root/result['path']).write_text(school.render_record(record),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'does not exist'):
            self.brief('invalid-feedback')

    def test_timezones_order_states_correctly(self):
        self.profile()
        question=self.add(stamp='2026-09-07T08:00:00Z')['entry_ids'][0]
        self.add('session-t02','question_status',state='answered',target_id=question,stamp='2026-09-07T17:00:00+08:00')
        self.add('session-t03','question_status',state='open',target_id=question,stamp='2026-09-07T10:00:00Z')
        self.assertEqual(self.brief()['unresolved_question_count'],1)
        with self.assertRaisesRegex(ValueError,'timezone'):
            self.add('session-t04',stamp='2026-09-07T12:00:00')

    def test_meeting_manifest_preserves_precise_cutoff(self):
        self.profile()
        self.add(stamp='2026-09-07T08:00:00.123456Z')
        result=school.make_brief(self.root,'precise',['01'],working_tree=True,
                                 cutoff='2026-09-07T08:00:00.123456Z')
        self.assertEqual(result['entry_count'],1)
        self.assertEqual(result['cutoff'],'2026-09-07T08:00:00.123456+00:00')

    def test_concurrent_writer_lock_and_invalid_meeting_paths(self):
        self.profile()
        with school.learner_lock(self.root,'learner-a','case-01-fixture'):
            with self.assertRaisesRegex(ValueError,'Another session'):
                self.add()
        self.assertEqual(self.add()['status'],'recorded')
        with self.assertRaises(ValueError):
            self.brief('../outside')

    def test_cli_handles_unicode_identity_and_record_input(self):
        script=Path(school.__file__).resolve()
        command=[sys.executable,str(script),'--root',str(self.root)]
        profile=subprocess.run(command+['init','--learner','learner-a','--name','小林🌱'],
                               capture_output=True,text=True,encoding='utf-8',check=True)
        self.assertEqual(json.loads(profile.stdout)['display_name'],'小林🌱')
        turn=self.root/'.school/turn.json'
        turn.write_text(json.dumps(self.packet(text='我想先验证交付是否被采用。'),ensure_ascii=False),encoding='utf-8')
        written=subprocess.run(command+['record','--case','01','--input',str(turn),'--date','2026-09-07'],
                               capture_output=True,text=True,encoding='utf-8',check=True)
        result=json.loads(written.stdout)
        self.assertEqual(result['status'],'recorded')
        self.assertFalse(result['github_published'])
        self.assertEqual(self.read(result)['interactions'][0]['contributions'][0]['text'],'我想先验证交付是否被采用。')


if __name__=='__main__':
    unittest.main()
