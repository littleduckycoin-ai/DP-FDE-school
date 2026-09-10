import test from 'node:test';
import assert from 'node:assert/strict';
import {SchoolClient,SchoolError,LarkCli,unwrap,markedJson,parseReflection,codeBlock,textBlock,renderInteraction,validatePayload,meetingData,fetchRouter} from '../.codex/skills/school-guide/scripts/feishu_school.mjs';

const row={id:1,case_id:'case-01-manufacturing-training',base_document_id:'base01',source_pdf_pages:[8,9],reflections_parent:{type:'folder',token:'folder01'}};
const manifest={schema_version:'feishu-school-v1',school_id:'fde-school',rules_document_id:'rules',cases:[row]};
const actor={app_id:'app1',open_id:'user1'};
function payload(id='turn1') { return {learner:{learner_id:'alice',display_name:'Alice'},consent:{granted:true,scope:'session',session_id:'session1',granted_at:'2026-09-10T08:00:00+08:00'},study_date:'2026-09-10',interaction:{interaction_id:id,created_at:'2026-09-10T09:00:00+08:00',summary:'先验证使用场景',contributions:[{kind:'thought',text:'我觉得应该先确认一线人员会不会使用。',capture:'verbatim',confirmation:'captured',source_refs:[{case_id:row.case_id,pdf_pages:[8],note:'原访谈'}],entry_id:`${row.case_id}:alice:${id}:01`,relates_to:[]}],agent_feedback:[],next_steps:[]}}; }
class FakeLark {
  constructor(){this.documents=new Map();this.posts=0;this.creates=0;this.tokens=new Set();this.actor=actor;this.timeoutAfterWrite=false;this.failList=false;}
  identity(){return this.actor;}
  call(args,input){assert.equal(args[0],'docs');this.creates++;const id='doc'+this.creates,title=args[args.indexOf('--title')+1],parent=args[args.indexOf('--parent-token')+1];const text=input.match(/```text\n([\s\S]+)\n```/)[1];this.documents.set(id,{title,parent,revision:1,blocks:[{...codeBlock(text),block_id:'meta'+id}]});return {document:{document_id:id,url:`https://test.feishu.cn/docx/${id}`}};}
  api(method,path,params={},body){
    if(path==='/open-apis/drive/v1/files'){if(this.failList)throw new SchoolError('permission_denied','no access');return {files:[...this.documents].filter(([id,d])=>d.parent===params.folder_token).map(([id,d])=>({name:d.title,token:id,type:'docx',url:`https://test.feishu.cn/docx/${id}`})),has_more:false};}
    const id=path.split('/')[5],doc=this.documents.get(id);assert.ok(doc,`${path} ${id}`);
    if(method==='GET'&&path.endsWith('/blocks'))return {items:doc.blocks,has_more:false};
    if(method==='GET')return {document:{document_id:id,revision_id:doc.revision,title:doc.title}};
    this.posts++;
    if(!this.tokens.has(params.client_token)){this.tokens.add(params.client_token);doc.blocks.push(...body.children.map((block,i)=>({...block,block_id:`b${doc.revision}-${i}`})));doc.revision++;}
    this.onPost?.(doc);
    if(this.timeoutAfterWrite)throw new SchoolError('outcome_unknown','timeout');
    return {children:doc.blocks,document_revision_id:doc.revision};
  }
}
test('CLI distinguishes its envelope and raw API error',()=>{
  assert.deepEqual(unwrap({ok:true,data:{code:0,data:{items:[]}}}),{items:[]});
  assert.throws(()=>unwrap({ok:true,data:{code:999,msg:'denied'}}),/denied/);
  assert.throws(()=>unwrap({ok:false,error:{subtype:'missing_scope',message:'permission'}}),e=>e.code==='missing_scope');
});
test('CLI puts bodies on stdin, never builds a shell command',()=>{
  let captured; const cli=new LarkCli({executable:'fake.exe',profile:'test',runner:(file,args,options)=>{captured={file,args,options};return {status:0,stdout:'{"ok":true,"data":{}}'};}});
  cli.api('POST','/open-apis/docx/v1/documents',{}, {title:'literal $(secret) `stuff`'});
  assert.equal(captured.options.shell,false);assert.equal(captured.options.input,'{"title":"literal $(secret) `stuff`"}');assert.ok(!captured.args.join(' ').includes('secret'));
});
test('markers parse braces and marker-looking text within JSON strings',()=>{
  const json={text:'brace } and \\" and school-interaction-v1\n{fake}',nested:{ok:true}};
  assert.deepEqual(markedJson('school-interaction-v1\n'+JSON.stringify(json)+'\nschool-interaction-end','school-interaction-v1'),[json]);
  assert.throws(()=>markedJson('school-interaction-v1\n{"unfinished":','school-interaction-v1'));
});

test('OAuth actor requires actual remote verification, not just local token expiry',()=>{
  let user={openId:'u1',userName:'A',status:'ready',available:true,verified:true,tokenStatus:'valid'};
  const cli=new LarkCli({executable:'fake.exe',runner:()=>({status:0,stdout:JSON.stringify({ok:true,data:{appId:'app1',identities:{user}}})})});
  assert.deepEqual(cli.identity(),{app_id:'app1',open_id:'u1',display_name:'A'});
  user={...user,status:'verify_failed',verified:false};assert.throws(()=>cli.identity(),e=>e.code==='login_required');
  user={...user,status:'needs_refresh',verified:true,tokenStatus:'expired'};assert.equal(cli.identity().open_id,'u1');
  user={...user,available:false};assert.throws(()=>cli.identity(),e=>e.code==='login_required');
});
test('only code blocks are parsed as records; quoted text cannot inject metadata',()=>{
  const metadata={learner_id:'alice'};const doc={blocks:[codeBlock('school-record-meta-v1\n'+JSON.stringify(metadata)),textBlock('school-record-meta-v1\n{"learner_id":"mallory"}')]};
  assert.equal(parseReflection(doc).metadata.learner_id,'alice');
});
test('payload refuses missing consent, invented PDF pages and mismatched entry ID',()=>{
  const a=payload();a.consent.granted=false;assert.throws(()=>validatePayload(a,row,[row]),/授权/);
  const b=payload();b.interaction.contributions[0].source_refs[0].pdf_pages=[999];assert.throws(()=>validatePayload(b,row,[row]),/PDF/);
  const c=payload();c.interaction.contributions[0].entry_id='other';assert.throws(()=>validatePayload(c,row,[row]),/entry_id/);
});
test('payload uses school timezone for daily document boundaries',()=>{
  const a=payload();a.interaction.created_at='2026-09-09T18:00:00Z';assert.doesNotThrow(()=>validatePayload(a,row,[row]));
  a.study_date='2026-09-09';assert.throws(()=>validatePayload(a,row,[row]),/study_date/);
});
test('render and parse retain exact wording, agent feedback and machine fields',()=>{
  const turn=payload().interaction;turn.agent_feedback=['补充验证建议'];
  const doc={blocks:[codeBlock('school-record-meta-v1\n{"learner_id":"alice"}'),...renderInteraction(turn)]};
  const {_block_id,...actual}=parseReflection(doc).interactions[0];assert.deepEqual(actual,turn);
});
test('all pages are read and a repeated continuation is not treated as complete',()=>{
  let calls=0;const c=new SchoolClient({api:()=>++calls===1?{items:[1],has_more:true,page_token:'next'}:{items:[2],has_more:false}});
  assert.deepEqual(c.pages('/list'),[1,2]);
  const bad=new SchoolClient({api:()=>({items:[],has_more:true,page_token:'same'})});assert.throws(()=>bad.pages('/list'),e=>e.code==='incomplete_read');
  assert.throws(()=>new SchoolClient({api:()=>({})}).pages('/list'),e=>e.code==='incomplete_read');
});
test('first save verifies persisted content and second identical save avoids another POST',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake),p=payload();
  assert.equal(c.append(manifest,'01',p).status,'verified_saved');
  const result=c.append(manifest,'01',p);assert.equal(result.status,'verified_existing');assert.equal(fake.posts,1);assert.equal(fake.creates,1);assert.match(result.url,/#b/);
});
test('uncertain POST success is resolved by readback without a blind retry',()=>{
  const fake=new FakeLark();fake.timeoutAfterWrite=true;const result=new SchoolClient(fake).append(manifest,1,payload());assert.equal(result.status,'verified_saved');assert.equal(result.recovered,true);assert.equal(fake.posts,1);
});
test('same ID different content is rejected and old text survives',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake),p=payload();c.append(manifest,1,p);p.interaction.contributions[0].text='changed';assert.throws(()=>c.append(manifest,1,p),e=>e.code==='interaction_conflict');assert.equal(fake.posts,1);
});
test('another OAuth account cannot claim the existing author by reusing their label',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake);c.append(manifest,1,payload());fake.actor={app_id:'app1',open_id:'other'};assert.throws(()=>c.append(manifest,1,payload('turn2')),e=>e.code==='identity_mismatch');assert.equal(fake.posts,1);
});
test('new consent context is recorded for subsequent sessions on the same day',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake);c.append(manifest,1,payload());const p=payload('turn2');p.consent.session_id='session2';c.append(manifest,1,p);
  const archive=c.reflections(manifest,1);assert.equal(archive.records[0].interactions[1].recording.consent.session_id,'session2');
});
test('status update needs explicit author confirmation and an existing question',()=>{
  const p=payload();p.interaction.contributions[0].kind='question_status';p.interaction.contributions[0].state='answered';p.interaction.contributions[0].target_id=`${row.case_id}:alice:old:01`;assert.throws(()=>validatePayload(p,row,[row]),/确认/);
  p.interaction.contributions[0].confirmation='confirmed';assert.throws(()=>new SchoolClient(new FakeLark()).append(manifest,1,p),/找不到/);
});
test('partial reflection reads report failures instead of claiming all peers were read',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake);c.append(manifest,1,payload());fake.documents.get('doc1').blocks=[];const result=c.reflections(manifest,1);assert.equal(result.complete,false);assert.equal(result.failures.length,1);
});
test('meeting deduplicates IDs, applies cutoff, and retains unresolved questions',()=>{
  const p=payload(),question={...p.interaction.contributions[0],kind:'question'};
  const turn={...p.interaction,contributions:[question],_block_id:'b1'};
  const record={metadata:{case_id:row.case_id,learner_id:'alice',display_name:'Alice'},document_id:'d',url:'https://test.feishu.cn/docx/d',revision_id:2,interactions:[turn]};
  const result=meetingData([{complete:true,failures:[],records:[record,structuredClone(record)]}],{},'2026-09-10T12:00:00+08:00');assert.equal(result.interactions.length,1);assert.equal(result.learner_count,1);assert.equal(result.open_questions.length,1);
  assert.equal(meetingData([{complete:true,failures:[],records:[record]}],{},'2026-09-10T08:00:00+08:00').interactions.length,0);
});
test('meeting reports contradictory duplicates',()=>{
  const turn=payload().interaction,record={metadata:{case_id:row.case_id,learner_id:'alice'},interactions:[turn]};const other=structuredClone(record);other.interactions[0].summary='changed';assert.equal(meetingData([{complete:true,failures:[],records:[record,other]}],{}).complete,false);
});
test('a route in preparation cannot silently activate the Feishu backend',async()=>{
  const router={schema_version:'school-backend-v1',active_backend:'feishu',status:'preparing',feishu:{manifest_url:null}};
  await assert.rejects(()=>fetchRouter('https://school.test/route',async()=>({ok:true,json:async()=>router})),/尚未验收/);
});
test('GitHub route lookup pins raw data to the freshly returned commit',async()=>{
  const calls=[],sha='a'.repeat(40);const router={schema_version:'school-backend-v1',active_backend:'github',status:'preparing'};
  const result=await fetchRouter(undefined,async url=>{calls.push(url);return {ok:true,json:async()=>calls.length===1?{sha}:router};});
  assert.ok(calls[1].includes('/'+sha+'/data/'));assert.equal(result._commit,sha);
});

test('JSON-looking credentials are redacted when the CLI fails to emit valid JSON',()=>{
  const cli=new LarkCli({executable:'fake.exe',runner:()=>({status:1,stderr:'broken {"access_token":"private_access","appSecret":"private_secret", "refresh_token": "private_refresh"}'})});
  assert.throws(()=>cli.call(['auth','status']),e=>!e.message.includes('private_')&&e.message.includes('[redacted]'));
});
test('pagination cannot claim completeness without a boolean has_more',()=>{
  for(const has_more of [undefined,null,'false'])assert.throws(()=>new SchoolClient({api:()=>({items:[],has_more})}).pages('/list'),e=>e.code==='incomplete_read');
});
test('document reads require a real revision and retain a known tenant URL for bare IDs',()=>{
  const invalid=new SchoolClient({api:()=>({document:{title:'missing revision'}})});
  assert.throws(()=>invalid.document('token'),e=>e.code==='incomplete_read');
  const fake=new FakeLark(),c=new SchoolClient(fake);c.append(manifest,1,payload());
  assert.equal(c.document('doc1').url,'https://test.feishu.cn/docx/doc1');
});
test('Wiki listings derive source links from the known tenant and real node token',()=>{
  const c=new SchoolClient({api:()=>({items:[{title:'record',obj_type:'docx',obj_token:'realDoc',node_token:'realNode'}],has_more:false})});
  c.origin='https://test.feishu.cn';
  assert.equal(c.list({type:'wiki',token:'parent',space_id:'123'})[0].url,'https://test.feishu.cn/wiki/realNode');
});
test('unknown documents make reflections incomplete unless the manifest explicitly excludes them',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake);c.append(manifest,1,payload());
  fake.documents.set('readme',{title:'README',parent:'folder01',revision:1,blocks:[]});
  assert.equal(c.reflections(manifest,1).complete,false);
  const m=structuredClone(manifest);m.cases[0].reflections_auxiliary_document_ids=['readme'];
  const result=c.reflections(m,1);assert.equal(result.complete,true);assert.equal(result.excluded.length,1);
});
test('another OAuth account cannot reuse an existing learner_id on another day or case',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake);c.append(manifest,1,payload());fake.actor={app_id:'app1',open_id:'other'};
  const next=payload('day2');next.study_date='2026-09-11';next.interaction.created_at='2026-09-11T09:00:00+08:00';
  assert.throws(()=>c.append(manifest,1,next),e=>e.code==='identity_mismatch');
  const row2={...row,id:2,case_id:'case-02-example',reflections_parent:{type:'folder',token:'folder02'}},m={...manifest,cases:[row,row2]},p=payload('case2');
  p.interaction.contributions[0].entry_id=`${row2.case_id}:alice:case2:01`;
  assert.throws(()=>c.append(m,2,p),e=>e.code==='identity_mismatch');
  assert.equal(fake.creates,1);assert.equal(fake.posts,1);
});
test('unbound migrated learner IDs cannot be claimed but do not block a distinct new learner',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake);c.append(manifest,1,payload());
  const d=fake.documents.get('doc1'),r=parseReflection({blocks:d.blocks});delete r.metadata.actor;
  for(const turn of r.interactions)delete turn.recording;
  d.blocks=[{...codeBlock('school-record-meta-v1\n'+JSON.stringify(r.metadata)),block_id:'legacyMeta'},...r.interactions.flatMap(renderInteraction)];
  assert.throws(()=>c.append(manifest,1,payload('turn2')),e=>e.code==='identity_mismatch');
  const other=payload('other');other.learner={learner_id:'bob',display_name:'Bob'};other.interaction.contributions[0].entry_id=`${row.case_id}:bob:other:01`;
  assert.equal(c.append(manifest,1,other).status,'verified_saved');
});
test('the bound author can confirm an old question status from a later day',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake),q=payload();q.interaction.contributions[0].kind='question';c.append(manifest,1,q);
  const p=payload('day2');p.study_date='2026-09-11';p.interaction.created_at='2026-09-11T09:00:00+08:00';
  Object.assign(p.interaction.contributions[0],{kind:'question_status',state:'answered',confirmation:'confirmed',target_id:q.interaction.contributions[0].entry_id});
  assert.equal(c.append(manifest,1,p).status,'verified_saved');
  assert.equal(c.meeting(manifest,[1]).unresolved_questions.length,0);
});
test('uncertain writes still verify old history and directory discoverability',()=>{
  const fake=new FakeLark(),c=new SchoolClient(fake);c.append(manifest,1,payload());fake.timeoutAfterWrite=true;
  fake.onPost=doc=>{doc.blocks=doc.blocks.filter(b=>b.block_id!=='b1-2');};
  assert.throws(()=>c.append(manifest,1,payload('turn2')),e=>e.code==='history_changed');
  const hidden=new FakeLark();hidden.timeoutAfterWrite=true;hidden.onPost=doc=>{doc.parent='moved';};
  const result=new SchoolClient(hidden).append(manifest,1,payload());assert.equal(result.status,'saved_unindexed');assert.equal(result.recovered,true);
});
test('concurrent duplicate documents cannot both be reported as verified_saved',()=>{
  const fake=new FakeLark();fake.onPost=doc=>{fake.documents.set('concurrent',structuredClone(doc));};
  assert.throws(()=>new SchoolClient(fake).append(manifest,1,payload()),e=>e.code==='duplicate_documents');
});
test('deferred and discussed questions remain unresolved until the same bound author answers',()=>{
  for(const state of ['deferred','discussed','answered']) {
    const fake=new FakeLark(),c=new SchoolClient(fake),q=payload();q.interaction.contributions[0].kind='question';c.append(manifest,1,q);
    const p=payload('status');Object.assign(p.interaction.contributions[0],{kind:'question_status',state,confirmation:'confirmed',target_id:q.interaction.contributions[0].entry_id});
    c.append(manifest,1,p);const result=c.meeting(manifest,[1]);assert.equal(result.complete,true);assert.equal(result.open_questions.length,0);assert.equal(result.unresolved_questions.length,state==='answered'?0:1);
  }
});
