"""Reference online reader: HTTP responses stay in memory; no clone, files or cache.

For integrations and maintenance verification. Learners use the school's URL,
not this program. Actual agents can use equivalent GitHub or HTTP tools.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import PurePosixPath
import re
import sys
from urllib.parse import urlencode, quote
import urllib.error
import urllib.request

REPOSITORY='littleduckycoin-ai/DP-FDE-school'

class OnlineReadError(ValueError):
    pass

def timestamp(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise OnlineReadError('A cutoff must include its timezone')
    return parsed.astimezone(timezone.utc)

class OnlineSchool:
    def __init__(self,token=None,transport=None,page_size=100):
        if not 1<=page_size<=100:
            raise OnlineReadError('Invalid page size')
        self.token=token
        self.transport=transport or self._http
        self.page_size=page_size
        self.api='https://api.github.com/repos/'+REPOSITORY
        self.web='https://github.com/'+REPOSITORY

    def _http(self,path,params):
        url=self.api+path+('?' + urlencode(params) if params else '')
        headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28',
                 'Cache-Control':'no-cache','User-Agent':'FDE-Online-School'}
        if self.token:
            headers['Authorization']='Bearer '+self.token
        request=urllib.request.Request(url,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise OnlineReadError(f'Online request failed with HTTP {exc.code}; no local fallback was used') from None
        except urllib.error.URLError as exc:
            raise OnlineReadError('Online request failed; no local fallback was used') from None

    def get(self,path,**params):
        return self.transport(path,params)

    def head(self):
        commit=self.get('/commits/main').get('sha','')
        if not re.fullmatch('[a-f0-9]{40}',commit):
            raise OnlineReadError('The online main revision could not be verified')
        return commit

    def file(self,path,commit):
        if not isinstance(path,str) or not path or path.startswith('/') or '\\' in path or '..' in PurePosixPath(path).parts:
            raise OnlineReadError('Unsafe repository path')
        response=self.get('/contents/'+quote(path,safe='/'),ref=commit)
        if not isinstance(response,dict) or response.get('type')!='file' or response.get('encoding')!='base64':
            raise OnlineReadError('The response is not complete file content')
        try:
            content=base64.b64decode(''.join(response['content'].split()),validate=True).decode('utf-8')
        except (ValueError,KeyError,UnicodeDecodeError):
            raise OnlineReadError('The response body could not be decoded') from None
        return content

    def lesson(self,case):
        commit=self.head()
        index=json.loads(self.file('data/case-index.json',commit))
        row=next((r for r in index['cases'] if str(case) in [str(r['id']),f'{r["id"]:02d}',r['case_id']]),None)
        if row is None:
            raise OnlineReadError('Case not found in the current online index')
        value=json.loads(self.file(row['json_file'],commit))
        if value['identity']['case_id']!=row['case_id']:
            raise OnlineReadError('Online case identity differs from its index')
        return {'source_commit':commit,'fetched_at':datetime.now(timezone.utc).isoformat(),
                'source_url':self.web+'/blob/'+commit+'/'+row['json_file'],
                'case_id':row['case_id'],'case':value,'local_materials_written':False}

    def pages(self,path,**params):
        for page in range(1,1001):
            items=self.get(path,**params,per_page=self.page_size,page=page)
            if not isinstance(items,list):
                raise OnlineReadError('Expected an online list, not an error or login response')
            yield from items
            if len(items)<self.page_size:
                return
        raise OnlineReadError('Pagination limit reached; cannot claim all records were read')

    def discussions(self,case_ids,cutoff=None):
        selected=set(case_ids)
        stop=timestamp(cutoff) if cutoff else datetime.now(timezone.utc)
        records=[]; excluded=[]; threads=[]
        # Include unlabeled form submissions too. GitHub also returns PRs here.
        for issue in self.pages('/issues',state='all',sort='updated',direction='desc'):
            if 'pull_request' in issue:
                continue
            labels={v['name'] if isinstance(v,dict) else v for v in issue.get('labels',[])}
            if 'school-reflection' not in labels and not issue.get('title','').startswith('[学习记录]'):
                continue
            body=issue.get('body') or ''
            tokens=set(re.findall(r'case-\d{2}-[a-z0-9-]+',issue.get('title','')+'\n'+body))
            if not selected.intersection(tokens):
                continue
            if timestamp(issue['created_at'])>stop:
                continue
            threads.append(issue['html_url'])
            entries=[{**issue,'source_kind':'issue'}]
            entries.extend({**c,'source_kind':'comment'} for c in self.pages('/issues/'+str(issue['number'])+'/comments'))
            for entry in entries:
                if timestamp(entry['created_at'])>stop:
                    continue
                if timestamp(entry.get('updated_at',entry['created_at']))>stop:
                    excluded.append({'source_url':entry['html_url'],'reason':'Edited after cutoff; the earlier body cannot be reconstructed from this response'})
                    continue
                records.append({'source_kind':entry['source_kind'],'id':entry['id'],
                    'thread_url':issue['html_url'],'source_url':entry['html_url'],
                    'github_author':entry['user']['login'],'created_at':entry['created_at'],
                    'updated_at':entry.get('updated_at',entry['created_at']),
                    'body':entry.get('body') or '', 'issue_state':issue['state']})
        # Discussion bodies remain attributed data. No generated learner claims.
        records.sort(key=lambda r:(timestamp(r['created_at']),r['source_kind'],r['id']))
        return {'fetched_at':datetime.now(timezone.utc).isoformat(),'cutoff':stop.isoformat(),
                'thread_urls':threads,'records':records,'historical_sources_excluded':excluded,
                'all_pages_read':True,'local_materials_written':False,
                'note':'Issue closure is not question resolution. File archives, if used, require separate online reads and deduplication.'}

def main():
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',default='04')
    parser.add_argument('--discussions',action='store_true')
    args=parser.parse_args()
    client=OnlineSchool(token=os.environ.get('SCHOOL_GITHUB_TOKEN'))
    try:
        data=client.lesson(args.case)
        result={k:v for k,v in data.items() if k!='case'}
        result.update(one_sentence_intro=data['case']['one_sentence_intro'],
                      source_pdf_pages=data['case']['provenance']['pdf_physical_pages'],
                      original_qa_count=len(data['case']['provenance']['original_qa']))
        if args.discussions:
            result['discussions']=client.discussions([data['case_id']])
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OnlineReadError,KeyError,ValueError) as exc:
        print('Online reading unavailable: '+str(exc),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
