"""Network contract checks with an in-memory transport; no learner checkout."""
import base64
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from online_school import OnlineSchool,OnlineReadError

def encoded(value):
    return {'type':'file','encoding':'base64','content':base64.b64encode(json.dumps(value).encode()).decode()}

class OnlineSchoolTests(unittest.TestCase):
    def setUp(self):
        self.requests=[]
        self.rev='a'*40
        self.cid='case-04-fixture'
        self.row={'id':4,'case_id':self.cid,'json_file':'cases/'+self.cid+'/base/case.json'}

    def lesson_transport(self,path,params):
        self.requests.append((path,params))
        if path=='/commits/main':
            return {'sha':self.rev}
        self.assertEqual(params['ref'],self.rev)
        if path=='/contents/data/case-index.json':
            return encoded({'cases':[self.row]})
        return encoded({'identity':{'case_id':self.cid},'one_sentence_intro':'Read from the current online revision.'})

    def issue(self,n=1,**changes):
        return {'id':n,'number':n,'title':'[学习记录] '+self.cid+' / learner-a',
                'body':'### 案例\n\n'+self.cid+'\n\n### 学习者标识\n\nlearner-a',
                'html_url':'https://github.com/example/school/issues/'+str(n),
                'labels':[],'state':'closed','user':{'login':'publisher'},
                'created_at':'2026-09-07T08:00:00Z','updated_at':'2026-09-07T08:00:00Z',**changes}

    def comment(self,n=10,**changes):
        return {'id':n,'body':'A learner question, not an agent answer.',
                'html_url':'https://github.com/example/school/issues/1#issuecomment-'+str(n),
                'user':{'login':'publisher'},'created_at':'2026-09-07T09:00:00Z',
                'updated_at':'2026-09-07T09:00:00Z',**changes}

    def test_each_lesson_checks_current_head_and_pins_all_files(self):
        client=OnlineSchool(transport=self.lesson_transport)
        first=client.lesson('04')
        self.rev='b'*40
        second=client.lesson(self.cid)
        self.assertEqual(first['source_commit'],'a'*40)
        self.assertEqual(second['source_commit'],'b'*40)
        self.assertEqual(len([r for r in self.requests if r[0]=='/commits/main']),2)
        self.assertFalse(second['local_materials_written'])

    def test_online_failure_does_not_reuse_old_material(self):
        client=OnlineSchool(transport=self.lesson_transport)
        client.lesson('04')
        def failed(path,params):
            raise OnlineReadError('No network')
        client.transport=failed
        with self.assertRaisesRegex(OnlineReadError,'No network'):
            client.lesson('04')

    def test_partial_content_and_path_escape_are_rejected(self):
        client=OnlineSchool(transport=lambda p,q:{'type':'file','encoding':'none','content':''})
        with self.assertRaisesRegex(OnlineReadError,'complete file'):
            client.file('data/case-index.json',self.rev)
        for path in ['../outside','/etc/passwd','cases\\secret']:
            with self.assertRaisesRegex(OnlineReadError,'Unsafe'):
                client.file(path,self.rev)

    def test_pagination_reads_comments_and_unlabeled_topics(self):
        def transport(path,params):
            self.requests.append((path,params))
            if path=='/issues':
                return [self.issue(),self.issue(2,pull_request={})] if params['page']==1 else []
            return [self.comment(10),self.comment(11)] if params['page']==1 else [self.comment(12)]
        result=OnlineSchool(transport=transport,page_size=2).discussions([self.cid],cutoff='2026-09-08T00:00:00Z')
        self.assertEqual(len(result['records']),4)
        self.assertTrue(result['all_pages_read'])
        self.assertTrue(all(r['github_author']=='publisher' for r in result['records']))
        self.assertTrue(all(r['issue_state']=='closed' for r in result['records']))
        self.assertIn('not question resolution',result['note'])

    def test_cutoff_excludes_later_edits_and_future_comments(self):
        def transport(path,params):
            if path=='/issues':
                return [self.issue()]
            return [self.comment(10,updated_at='2026-09-09T00:00:00Z'),
                    self.comment(11,created_at='2026-09-10T00:00:00Z',updated_at='2026-09-10T00:00:00Z')]
        result=OnlineSchool(transport=transport).discussions([self.cid],cutoff='2026-09-08T00:00:00Z')
        self.assertEqual(len(result['records']),1)
        self.assertEqual(len(result['historical_sources_excluded']),1)

    def test_empty_online_records_do_not_invent_participants(self):
        result=OnlineSchool(transport=lambda p,q:[]).discussions([self.cid])
        self.assertEqual(result['records'],[])
        self.assertEqual(result['thread_urls'],[])
        self.assertFalse(result['local_materials_written'])

    def test_bad_online_revision_is_not_presented_as_fresh(self):
        with self.assertRaisesRegex(OnlineReadError,'could not be verified'):
            OnlineSchool(transport=lambda p,q:{'sha':'main'}).lesson('04')

    def test_case_filter_uses_full_slug_not_substring(self):
        row=self.issue(title='[学习记录] '+self.cid+'-other',body='Different case')
        result=OnlineSchool(transport=lambda p,q:[row] if p=='/issues' else []).discussions([self.cid])
        self.assertEqual(result['records'],[])

if __name__=='__main__':
    unittest.main()
