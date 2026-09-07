"""Identity, append-only learning records, and traceable meeting packs. Stdlib only."""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
KINDS = {'thought':'思考', 'evaluation':'评价', 'question':'问题', 'application':'应用设想',
         'disagreement':'分歧', 'feedback':'给同学的反馈', 'revision':'观点修订', 'question_status':'问题状态更新'}
MARKER = re.compile(r'<!-- school-record-v1\n(.*?)\n-->', re.S)
SLUG = re.compile(r'[a-z0-9][a-z0-9_-]{0,79}\Z')

def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def safe_slug(value, label):
    require(isinstance(value,str) and bool(SLUG.fullmatch(value)), f'{label}: use lowercase letters, numbers, hyphens or underscores')
    return value

def inside(root, path):
    require(path.resolve().is_relative_to(root.resolve()), 'Path leaves the repository')
    return path

def atomic_write(root, path, text):
    inside(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = inside(root, path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp'))
    try:
        tmp.write_text(text, encoding='utf-8', newline='\n')
        os.replace(tmp,path)
    finally:
        if tmp.exists():
            tmp.unlink()

def dump(value):
    return json.dumps(value,ensure_ascii=False,indent=2)

def git(root,*args):
    p = subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,encoding='utf-8')
    require(p.returncode==0, 'Git operation failed: ' + ' '.join(args[:2]))
    return p.stdout

def catalog(root,commit=None):
    text = git(root,'show',commit+':data/case-index.json') if commit else (root/'data/case-index.json').read_text(encoding='utf-8')
    rows = json.loads(text)['cases']
    require(all('case_id' in r for r in rows),'This snapshot predates the school layout; use an updated branch')
    return rows

def resolve_case(rows, value):
    for row in rows:
        if str(value) in [row['case_id'],str(row['id']),f'{row["id"]:02d}']:
            return row
    raise ValueError('Unknown case: '+str(value))

def identity(root):
    path = root/'.school/identity.json'
    require(path.is_file(),'Learner identity is missing. Ask for a public learner ID, then run init.')
    who = json.loads(path.read_text(encoding='utf-8'))
    safe_slug(who.get('learner_id'),'learner_id')
    require(who.get('identity_source')=='self_declared','Identity must be supplied by the learner')
    require(isinstance(who.get('display_name'),str) and 0<len(who['display_name'].strip())<=80,'Invalid display name')
    return who

def init_identity(root, learner_id, display_name):
    safe_slug(learner_id,'learner_id')
    require(isinstance(display_name,str) and 0<len(display_name.strip())<=80,'A public display name is required')
    require('\n' not in display_name and '\r' not in display_name,'Display name must be a single line')
    who = {'learner_id':learner_id,'display_name':display_name.strip(),
           'identity_source':'self_declared','updated_at':now()}
    atomic_write(root,root/'.school/identity.json',dump(who)+'\n')
    return who

def quote(text):
    return '\n'.join('> '+html.escape(line,quote=False) for line in text.split('\n'))

def record_anchor(interaction_id, position):
    return f'r-{interaction_id}-{position+1:02d}'

def render_record(record):
    meta = {k:record[k] for k in ['schema_version','case_id','learner_id','display_name','identity_source','study_date','visibility']}
    lines = ['---']+[k+': '+json.dumps(v,ensure_ascii=False) for k,v in meta.items()]+['---','',
        f'# {record["display_name"]}｜{record["study_date"]}｜学习记录','',
        f'学习者标识：`{record["learner_id"]}`。身份由学习者自述；文件归档不代表观点已获课程审核。','',
        f'[基础案例](../../../cases/{record["case_id"]}/base/case.md)','']
    for turn in record['interactions']:
        lines += [f'## {turn["created_at"]}｜{turn["interaction_id"]}','']
        if turn.get('summary'):
            lines += [html.escape(turn['summary'],quote=False),'']
        for i,item in enumerate(turn['contributions']):
            anchor = record_anchor(turn['interaction_id'],i)
            lines += [f'<a id="{anchor}"></a>','',f'### {KINDS[item["kind"]]}','',
                      f'记录编号：`{item["entry_id"]}` · 学员'+('原话' if item['capture']=='verbatim' else '观点的概括')+
                      (' · 学员已确认此记录' if item['confirmation']=='confirmed' else ' · 自动记录，可后续更正'),'',quote(item['text']),'']
            if item.get('target_id'):
                lines += ['针对记录：`'+item['target_id']+'`','']
            if item['kind']=='question_status':
                lines += ['明确更新为：`'+item['state']+'`','']
            if item.get('relates_to'):
                lines += ['相关记录：'+ '、'.join('`'+x+'`' for x in item['relates_to']),'']
            for ref in item['source_refs']:
                page = ref['pdf_pages'][0]
                lines += [f'- [案例{ref["case_number"]:02d} · PDF第'+ '、'.join(map(str,ref['pdf_pages']))+
                          f'页](../../../sources/original-interviews.pdf#page={page})：'+html.escape(ref.get('note',''),quote=False)]
            if item['source_refs']:
                lines.append('')
        if turn['agent_feedback']:
            lines += ['### Agent反馈｜不代表学员认同','']+[quote(x)+'\n' for x in turn['agent_feedback']]
        if turn['next_steps']:
            lines += ['### 待验证动作｜建议，尚未视为承诺','']+['- '+html.escape(x,quote=False) for x in turn['next_steps']]+['']
    payload = dump(record).replace('<','\\u003c').replace('>','\\u003e')
    lines += ['<!-- school-record-v1',payload,'-->','']
    return '\n'.join(lines)

def parse_record(text, strict=True):
    matches = list(MARKER.finditer(text))
    require(len(matches)==1,'Missing or duplicated school-record metadata')
    record = json.loads(matches[0].group(1))
    require(isinstance(record,dict),'Record metadata must be an object')
    require(record.get('schema_version')=='1.0','Unsupported reflection schema')
    safe_slug(record.get('learner_id'),'learner_id')
    safe_slug(record.get('case_id'),'case_id')
    require(isinstance(record.get('display_name'),str) and 0<len(record['display_name'].strip())<=80,'Invalid display name')
    date.fromisoformat(record['study_date'])
    require(record.get('identity_source')=='self_declared','Invalid identity source')
    require(record.get('visibility') in ['shared_draft','private'],'Invalid visibility')
    require(isinstance(record.get('interactions'),list) and record['interactions'],'Empty reflection')
    if strict:
        require(render_record(record)==text,'Readable text differs from record data; append a revision through the helper')
    return record

def normalize_packet(rows, value):
    require(isinstance(value,dict),'Record input must be an object')
    require(set(value)<= {'interaction_id','summary','contributions','agent_feedback','next_steps'},'Unknown input field; learner identity comes from the local profile')
    safe_slug(value.get('interaction_id'),'interaction_id')
    contributions = value.get('contributions')
    require(isinstance(contributions,list) and contributions,'No substantive learner contributions to record')
    clean=[]
    for item in contributions:
        require(isinstance(item,dict),'Contribution must be an object')
        require(set(item)<= {'kind','text','capture','confirmation','source_refs','target_id','state','relates_to'},'Unknown contribution field')
        require(item.get('kind') in KINDS,'Unknown contribution kind')
        require(isinstance(item.get('text'),str) and item['text'].strip(),'Empty contribution text')
        c = dict(item)
        c.setdefault('capture','paraphrase')
        c.setdefault('confirmation','captured')
        require(c['capture'] in ['paraphrase','verbatim'],'Invalid capture type')
        require(c['confirmation'] in ['captured','confirmed'],'Invalid confirmation')
        refs=[]
        require(isinstance(c.get('source_refs',[]),list),'source_refs must be a list')
        for ref in c.get('source_refs',[]):
            require(isinstance(ref,dict) and 'case_id' in ref,'Invalid source reference')
            r=resolve_case(rows,ref['case_id'])
            pages=ref.get('pdf_pages',[])
            lo,hi=r['source_pdf_page_range']
            require(isinstance(pages,list) and pages and all(isinstance(p,int) and not isinstance(p,bool) and lo<=p<=hi for p in pages),'Source page is outside its case')
            require(isinstance(ref.get('note',''),str),'Reference note must be text')
            refs.append({'case_id':r['case_id'],'case_number':r['id'],'pdf_pages':pages,'note':ref.get('note','')})
        c['source_refs']=refs
        require(isinstance(c.get('relates_to',[]),list) and all(isinstance(x,str) for x in c.get('relates_to',[])),'Invalid related record IDs')
        if c['kind']=='question_status':
            require(isinstance(c.get('target_id'),str) and c['target_id'],'Question update requires a target ID')
            require(c.get('state') in ['answered','deferred','discussed','open'],'Invalid question state')
        elif c['kind']=='revision':
            require(isinstance(c.get('target_id'),str) and c['target_id'],'Revision requires the original entry ID')
        if c['kind']!='question_status':
            require('state' not in c,'Only a question update may set a state')
        if c['kind'] not in ['question_status','revision']:
            require('target_id' not in c,'Use relates_to for peer feedback')
        clean.append(c)
    result={'interaction_id':value['interaction_id'],'summary':value.get('summary',''), 'contributions':clean,
            'agent_feedback':value.get('agent_feedback',[]),'next_steps':value.get('next_steps',[])}
    require(isinstance(result['summary'],str),'Summary must be text')
    for key in ['agent_feedback','next_steps']:
        require(isinstance(result[key],list) and all(isinstance(x,str) for x in result[key]),key+' must be a list of text')
    return result

@contextmanager
def learner_lock(root, learner_id, case_id):
    lock=root/'.school/locks'/f'{learner_id}-{case_id}.lock'
    inside(root,lock).parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Another session is writing this learner record. Retry after it finishes; do not overwrite its lock.')
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()

def append_record(root, case, packet, study_date=None, private=False, timestamp=None):
    who=identity(root)
    rows=catalog(root)
    row=resolve_case(rows,case)
    packet=normalize_packet(rows,packet)
    study_date=study_date or date.today().isoformat()
    date.fromisoformat(study_date)
    cid=row['case_id']; learner=who['learner_id']
    public_dir=root/row['reflections_dir']
    private_dir=root/'.school/private'/cid
    target=(private_dir if private else public_dir)/f'{learner}-{study_date}.md'
    inside(root,target)
    with learner_lock(root,learner,cid):
        previous={}
        all_entries={}
        private_entries=set()
        for folder in [public_dir,private_dir]:
            for path in folder.glob(learner+'-????-??-??.md'):
                r=parse_record(inside(root,path).read_text(encoding='utf-8'))
                require(r['learner_id']==learner and r['case_id']==cid,'File ownership or case mismatch')
                previous[path]=r
                for turn in r['interactions']:
                    for c in turn['contributions']:
                        all_entries[c['entry_id']]=c
                        if r['visibility']=='private':
                            private_entries.add(c['entry_id'])
                    if turn['interaction_id']==packet['interaction_id']:
                        stripped={k:v for k,v in turn.items() if k!='created_at'}
                        stripped['contributions']=[{k:v for k,v in c.items() if k!='entry_id'} for c in turn['contributions']]
                        require(stripped==packet,'Interaction ID already exists with different content; append a revision with a new ID')
                        return {'status':'unchanged','path':path.relative_to(root).as_posix(),'interaction_id':packet['interaction_id']}
        for i,c in enumerate(packet['contributions']):
            c['entry_id']=f'{cid}:{learner}:{packet["interaction_id"]}:{i+1:02d}'
            if c['kind'] in ['question_status','revision']:
                require(c['target_id'] in all_entries,'Referenced original entry is not in this learner\'s records')
                require(private or c['target_id'] not in private_entries,'A shared update cannot reference a private original entry')
                if c['kind']=='question_status':
                    require(all_entries[c['target_id']]['kind']=='question','Target is not a question')
            all_entries[c['entry_id']]=c
        if any(c.get('relates_to') for c in packet['contributions']):
            visible_ids={c['entry_id'] for _,_,r in reflection_sources(root)
                         for turn in r['interactions'] for c in turn['contributions']}
            visible_ids.update(c['entry_id'] for c in packet['contributions'])
            for c in packet['contributions']:
                require(all(x in visible_ids for x in c.get('relates_to',[])),'Related learner entry does not exist in shared records')
        record=previous.get(target,{'schema_version':'1.0','case_id':cid,'learner_id':learner,
            'display_name':who['display_name'],'identity_source':'self_declared','study_date':study_date,
            'visibility':'private' if private else 'shared_draft','interactions':[]})
        require(not target.exists() or target in previous,'Refusing to replace an unrelated file')
        packet['created_at']=timestamp or now()
        parse_time(packet['created_at'])
        record['interactions'].append(packet)
        atomic_write(root,target,render_record(record))
        return {'status':'recorded','path':target.relative_to(root).as_posix(),
                'entry_ids':[x['entry_id'] for x in packet['contributions']],
                'visibility':record['visibility'],'github_published':False}

def parse_time(value, end=False):
    if len(value)==10:
        value += 'T23:59:59+00:00' if end else 'T00:00:00+00:00'
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(result.tzinfo is not None,'Timestamps must include a timezone')
    return result.astimezone(timezone.utc)

def reflection_sources(root, commit=None):
    if commit:
        paths=git(root,'ls-tree','-r','--name-only',commit,'--','cases').splitlines()
    else:
        paths=[p.relative_to(root).as_posix() for p in (root/'cases').glob('*/reflections/*.md')]
    for path in sorted(paths):
        if '/reflections/' not in path or not path.endswith('.md') or Path(path).name=='README.md':
            continue
        text=git(root,'show',commit+':'+path) if commit else inside(root,root/path).read_text(encoding='utf-8')
        record=parse_record(text)
        require(record['visibility']=='shared_draft','Private record found in shared reflections')
        expected=f'cases/{record["case_id"]}/reflections/{record["learner_id"]}-{record["study_date"]}.md'
        require(path==expected,'Reflection identity does not match its path: '+path)
        yield path,text,record

def validate_reflections(root, commit=None):
    """Check semantic consistency beyond Markdown/JSON rendering equality."""
    rows=catalog(root,commit)
    sources=list(reflection_sources(root,commit))
    turns=set(); entries={}
    for path,text,record in sources:
        resolve_case(rows,record['case_id'])
        for turn in record['interactions']:
            require(set(turn)=={'interaction_id','summary','contributions','agent_feedback','next_steps','created_at'},'Unexpected stored turn fields: '+path)
            parse_time(turn['created_at'])
            key=(record['case_id'],record['learner_id'],turn['interaction_id'])
            require(key not in turns,'Duplicate interaction ID: '+path)
            turns.add(key)
            packet={k:v for k,v in turn.items() if k!='created_at'}
            packet['contributions']=[{k:v for k,v in c.items() if k!='entry_id'} for c in turn['contributions']]
            require(normalize_packet(rows,packet)==packet,'Stored packet is not normalized: '+path)
            for i,c in enumerate(turn['contributions']):
                expected=f'{record["case_id"]}:{record["learner_id"]}:{turn["interaction_id"]}:{i+1:02d}'
                require(c.get('entry_id')==expected,'Entry ID mismatch: '+path)
                require(expected not in entries,'Duplicate entry ID: '+expected)
                entries[expected]=(c,record,turn['created_at'])
    for c,record,stamp in entries.values():
        if c['kind'] in ['question_status','revision']:
            require(c['target_id'] in entries,'Missing original entry: '+c['target_id'])
            original,owner,old_stamp=entries[c['target_id']]
            require(owner['learner_id']==record['learner_id'] and owner['case_id']==record['case_id'],'Cannot change another learner or case record')
            require(c['target_id']!=c['entry_id'] and parse_time(old_stamp)<=parse_time(stamp),'Update must reference an earlier entry')
            if c['kind']=='question_status':
                require(original['kind']=='question','Question update targets a non-question')
        for related in c.get('relates_to',[]):
            require(related in entries,'Related learner entry does not exist: '+related)
    return sources

def preserve_history(root, base_ref):
    """A PR can append learner turns, but cannot delete or rewrite old ones."""
    commit=git(root,'rev-parse','--verify','--end-of-options',base_ref+'^{commit}').strip()
    for path,text,old in reflection_sources(root,commit):
        current=inside(root,root/path)
        require(current.is_file(),'Historical learner file deleted: '+path)
        new=parse_record(current.read_text(encoding='utf-8'))
        require({k:v for k,v in old.items() if k!='interactions'}=={k:v for k,v in new.items() if k!='interactions'},'Historical identity or metadata changed: '+path)
        require(new['interactions'][:len(old['interactions'])]==old['interactions'],'Historical learner turns changed: '+path)

def make_brief(root, meeting_id, cases, ref='origin/main', working_tree=False,
               since=None, cutoff=None, expected=None, refresh=False):
    safe_slug(meeting_id,'meeting_id')
    cutoff_dt=parse_time(cutoff,True) if cutoff else datetime.now(timezone.utc)
    since_dt=parse_time(since) if since else datetime.min.replace(tzinfo=timezone.utc)
    require(since_dt<=cutoff_dt,'Start is later than cutoff')
    commit=None if working_tree else git(root,'rev-parse','--verify','--end-of-options',ref+'^{commit}').strip()
    rows=catalog(root,commit)
    selected=[resolve_case(rows,c) for c in cases]
    selected_ids={r['case_id'] for r in selected}
    require(len(selected)==len(selected_ids),'Duplicate case selection')
    for learner in expected or []:
        safe_slug(learner,'expected learner')
    source_files=[]; entries=[]; feedback=[]; suggestions=[]; participants={}
    repository_url='https://github.com/littleduckycoin-ai/DP-FDE-school'
    for path,text,r in validate_reflections(root,commit):
        if r['case_id'] not in selected_ids:
            continue
        included=False
        for turn in r['interactions']:
            stamp=parse_time(turn['created_at'])
            if not since_dt<=stamp<=cutoff_dt:
                continue
            included=True
            participants[r['learner_id']]=r['display_name']
            for i,c in enumerate(turn['contributions']):
                anchor=record_anchor(turn['interaction_id'],i)
                url=(repository_url+'/blob/'+commit+'/'+path if commit else '../../'+path)+'#'+anchor
                entries.append({**c,'learner_id':r['learner_id'],'display_name':r['display_name'],
                    'case_id':r['case_id'],'created_at':turn['created_at'],'source_file':path,'source_url':url})
            for value in turn['agent_feedback']:
                feedback.append({'case_id':r['case_id'],'learner_id':r['learner_id'],
                                 'text':value,'created_at':turn['created_at'],'source_file':path})
            for value in turn['next_steps']:
                suggestions.append({'case_id':r['case_id'],'learner_id':r['learner_id'],
                                    'text':value,'created_at':turn['created_at'],'source_file':path})
        if included:
            source_files.append({'path':path,'sha256':hashlib.sha256(text.encode('utf-8')).hexdigest()})
    entries.sort(key=lambda e:(parse_time(e['created_at']),e['entry_id']))
    require(len({e['entry_id'] for e in entries})==len(entries),'Duplicate entry IDs in meeting sources')
    by_id={e['entry_id']:e for e in entries}
    states={e['entry_id']:'open' for e in entries if e['kind']=='question'}
    for e in entries:
        if e['kind']=='question_status' and e['target_id'] in states:
            q=by_id[e['target_id']]
            require(q['learner_id']==e['learner_id'],'A learner cannot resolve someone else\'s question')
            states[e['target_id']]=e['state']
    questions=[{**e,'question_state':states[e['entry_id']]} for e in entries if e['kind']=='question']
    unanswered=[e for e in questions if e['question_state']!='answered']
    destination=inside(root,root/'meetings'/meeting_id)
    manifest_path=destination/'manifest.json'
    if destination.exists():
        require(refresh,'Meeting already exists; use --refresh for generated files only')
        require(manifest_path.is_file(),'Existing directory is not a generated meeting pack')
        old=json.loads(manifest_path.read_text(encoding='utf-8'))
        require(old.get('generator')=='school-brief-v1' and old.get('meeting_id')==meeting_id,'Refusing to overwrite unrelated meeting files')
    scope='当前工作区（可能包含未提交笔记）' if working_tree else f'Git快照 `{commit}`，引用指向该版本'
    lines=[f'# {meeting_id}｜会前资料包','',f'资料范围：{scope}。','',
           f'时间范围：{since or "全部已记录时间"} 至 {cutoff_dt.isoformat()}。','',
           f'本次读取 {len(source_files)} 份记录，涉及 {len(participants)} 位学习者、{len(selected)} 个指定案例。',
           f'提取 {len(entries)} 条学员内容，其中 {len(questions)} 个问题，{len(unanswered)} 个尚未被本人明确标记为已解决。','',
           '这是有出处的资料整理，不代表小组共识。相近表达暂不合并为共同立场；Agent的回答不自动关闭问题。','',
           '## 参与记录','', '| 学习者标识 | 显示名 |','|---|---|']
    lines += [f'| {k} | {html.escape(v).replace("|","&#124;")} |' for k,v in sorted(participants.items())]
    if not participants:
        lines += ['','指定范围内没有学习记录；不生成虚构观点或问题。']
    if expected is not None:
        missing=sorted(set(expected)-set(participants))
        unexpected=sorted(set(participants)-set(expected))
        lines += ['','应参与名单中未找到记录：'+('、'.join(missing) or '无')+'。这只表示当前资料中没有记录，不等于缺席。']
        if unexpected:
            lines += ['名单之外的记录提供者：'+'、'.join(unexpected)+'。']
    else:
        lines += ['','未提供应参与名单，因此不推断谁尚未提交或缺席。']
    lines += ['','## 开放问题｜按案例列出','']
    for row in selected:
        group=[e for e in unanswered if e['case_id']==row['case_id']]
        lines += [f'### 案例{row["id"]:02d}｜{row["learning_title"]}','']
        if not group:
            lines += ['本次资料中没有未解决问题。','']
        for e in group:
            lines += [f'- **{e["display_name"]}（{e["learner_id"]}）** · {e["question_state"]} · [原记录]({e["source_url"]})','',quote(e['text']),'']
    for kind in ['thought','evaluation','application','disagreement','feedback','revision']:
        group=[e for e in entries if e['kind']==kind]
        lines += ['## '+KINDS[kind],'']
        if not group:
            lines += ['本次资料中没有此类记录。','']
        for e in group:
            lines += [f'- **{e["display_name"]}（{e["learner_id"]}）** · `{e["case_id"]}` · [原记录]({e["source_url"]})','',quote(e['text']),'']
    lines += ['## 主持人与Agent下一步','',
        '根据这些材料提出讨论优先级时，另写`synthesis.md`，每个主题引用记录编号，说明涉及几位独立学习者。保留少数意见，不把高频提问当成共识。',
        '已解决问题和Agent反馈保存在[结构化资料](records.json)中；反馈与学员观点分别存储。会议结论用[决策模板](../../templates/meeting-decisions.md)单独记录，不能由此资料包自动推定。','']
    manifest={'generator':'school-brief-v1','meeting_id':meeting_id,'generated_at':now(),
        'source_scope':'working_tree' if working_tree else 'git_snapshot','source_commit':commit,
        'since':since,'cutoff':cutoff_dt.isoformat(),'case_ids':[r['case_id'] for r in selected],
        'participants':participants,'expected_learners':expected,'source_files':source_files,
        'entry_count':len(entries),'question_count':len(questions),'unresolved_question_count':len(unanswered)}
    atomic_write(root,destination/'brief.md','\n'.join(lines))
    atomic_write(root,destination/'records.json',dump({'learner_entries':entries,'questions':questions,'agent_feedback':feedback,'agent_next_steps':suggestions})+'\n')
    atomic_write(root,manifest_path,dump(manifest)+'\n')
    return {'path':(destination/'brief.md').relative_to(root).as_posix(),**manifest}

def main():
    for stream in [sys.stdout,sys.stderr]:
        if hasattr(stream,'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    sub=p.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init',help='Save an explicitly supplied public learner identity locally')
    init.add_argument('--learner',required=True); init.add_argument('--name',required=True)
    sub.add_parser('whoami'); sub.add_parser('session',help='Generate a session ID to reuse for this conversation')
    rec=sub.add_parser('record',help='Append one substantive learning turn; never push to GitHub')
    rec.add_argument('--case',required=True); rec.add_argument('--input',type=Path,required=True)
    rec.add_argument('--date'); rec.add_argument('--private',action='store_true')
    brief=sub.add_parser('brief',help='Build a traceable pre-meeting pack')
    brief.add_argument('--meeting',required=True); brief.add_argument('--cases',nargs='+',required=True)
    brief.add_argument('--ref',default='origin/main'); brief.add_argument('--working-tree',action='store_true')
    brief.add_argument('--since'); brief.add_argument('--cutoff'); brief.add_argument('--expected',nargs='*')
    brief.add_argument('--refresh',action='store_true')
    args=p.parse_args(); root=args.root.resolve()
    try:
        if args.command=='init': result=init_identity(root,args.learner,args.name)
        elif args.command=='whoami': result=identity(root)
        elif args.command=='session': result={'session_id':'s-'+uuid.uuid4().hex[:16]}
        elif args.command=='record':
            result=append_record(root,args.case,json.loads(args.input.read_text(encoding='utf-8-sig')),args.date,args.private)
        else:
            result=make_brief(root,args.meeting,args.cases,args.ref,args.working_tree,args.since,args.cutoff,args.expected,args.refresh)
        print(dump(result))
    except (ValueError,KeyError,OSError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
