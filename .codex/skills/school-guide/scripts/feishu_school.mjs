#!/usr/bin/env node
/** Online school adapter. No dependencies, no material cache, no token handling. */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, delimiter, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

export const ROUTER = 'https://raw.githubusercontent.com/littleduckycoin-ai/DP-FDE-school/main/data/school-backend.json';
const KINDS = new Set(['thought','evaluation','question','application','disagreement','feedback','revision','question_status']);
const LABELS = {thought:'思考',evaluation:'评价',question:'问题',application:'应用设想',disagreement:'分歧',feedback:'同伴反馈',revision:'观点修订',question_status:'问题状态'};
const SLUG = /^[a-z0-9][a-z0-9_-]{0,79}$/;
export class SchoolError extends Error {
  constructor(code, message, details = {}) { super(message); this.code=code; this.details=details; }
}
const requireValue = (condition, message) => { if (!condition) throw new SchoolError('invalid_input',message); };
export const digest = value => createHash('sha256').update(typeof value==='string'?value:canonical(value)).digest('hex');
export function canonical(value) {
  if (Array.isArray(value)) return '['+value.map(canonical).join(',')+']';
  if (value && typeof value==='object') return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
  return JSON.stringify(value);
}
const plain = value => typeof value==='string' && value.trim().length>0;
const iso = value => typeof value==='string' && /(Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value));
const sameActor = (a,b) => plain(a?.app_id)&&plain(a?.open_id)&&a.app_id===b?.app_id&&a.open_id===b?.open_id;
const reflectionTitle = meta => `school-reflection | ${meta.case_id} | ${meta.learner_id} | ${meta.study_date}`;
const redact = text => String(text).replace(/(Bearer\s+)[^\s"']+/gi,'$1[redacted]').replace(/((?:access[_-]?token|refresh[_-]?token|app[_-]?secret|client[_-]?secret)["']?\s*[=:]\s*["']?)[^\s,"'}]+/gi,'$1[redacted]');

export function findCli(env=process.env) {
  const ext=process.platform==='win32'?'.exe':'';
  const candidates=[env.SCHOOL_LARK_CLI];
  if (env.APPDATA) candidates.push(join(env.APPDATA,'npm','node_modules','@larksuite','cli','bin','lark-cli'+ext));
  for (const directory of (env.PATH||'').split(delimiter)) {
    candidates.push(join(directory,'lark-cli'+ext));
    if (process.platform==='win32') candidates.push(join(directory,'node_modules','@larksuite','cli','bin','lark-cli.exe'));
  }
  for (const path of candidates.filter(Boolean)) if (existsSync(path)) return path;
  throw new SchoolError('cli_missing','缺少飞书读写工具。由 Agent 安装官方 @larksuite/cli；学员不需要另装飞书 Skills。');
}
export function unwrap(result) {
  if (result?.ok===false) throw new SchoolError(result.error?.subtype||'lark_error',redact(result.error?.message||'飞书调用失败'),{hint:result.error?.hint?redact(result.error.hint):undefined,missing_scopes:result.error?.missing_scopes,console_url:result.error?.console_url});
  // CLI and raw OpenAPI have different envelopes; check both explicitly.
  if (typeof result?.code==='number' && result.code!==0) throw new SchoolError('api_'+result.code,redact(result.msg||'飞书 API 调用失败'));
  let data=result?.data??result;
  if (typeof data?.code==='number') { if (data.code!==0) throw new SchoolError('api_'+data.code,redact(data.msg||'飞书 API 调用失败')); data=data.data??data; }
  return data;
}
export class LarkCli {
  constructor({profile,executable,runner=spawnSync}={}) {this.profile=profile;this.executable=executable;this.runner=runner;}
  call(args,input) {
    const binary=this.executable||findCli();
    const argv=[...(this.profile?['--profile',this.profile]:[]),...args];
    const out=this.runner(binary,argv,{encoding:'utf8',input,windowsHide:true,shell:false,timeout:90000,maxBuffer:32*1024*1024,env:{...process.env,LARKSUITE_CLI_NO_UPDATE_NOTIFIER:'1',LARKSUITE_CLI_NO_SKILLS_NOTIFIER:'1'}});
    if (out.error) throw new SchoolError(out.error.code==='ETIMEDOUT'?'outcome_unknown':'cli_failed',redact(out.error.message));
    let value;
    try { value=JSON.parse((out.status===0?out.stdout:out.stderr)||out.stdout||''); }
    catch { throw new SchoolError('cli_failed',redact((out.stderr||out.stdout||'CLI未返回可验证JSON').slice(0,1600))); }
    if (out.status!==0 && value.ok!==false) throw new SchoolError('cli_failed','飞书工具未成功退出');
    return unwrap(value);
  }
  api(method,path,params={},body) {
    const args=['api',method,path,'--as','user','--format','json'];
    if(Object.keys(params).length) args.push('--params',JSON.stringify(params));
    if(body!==undefined) args.push('--data','-');
    return this.call(args,body===undefined?undefined:JSON.stringify(body));
  }
  identity() {
    const value=this.call(['auth','status','--json','--verify']);
    const user=value.identities?.user;
    if(!user?.openId || !value.appId || user.available!==true || user.verified!==true || !['ready','needs_refresh'].includes(user.status)) throw new SchoolError('login_required','请先完成本人的飞书 OAuth 登录，并通过远端身份核验，再保存学习记录。');
    // Account state is never printed wholesale or copied to school documents.
    return {open_id:user.openId,app_id:value.appId,display_name:user.userName||null};
  }
}
export function textOf(block) {
  for(const value of Object.values(block)) if(value && typeof value==='object' && Array.isArray(value.elements)) return value.elements.map(e=>e.text_run?.content??'').join('');
  return '';
}
export function markedJson(text,marker) {
  const values=[];let offset=0;
  while(true) {
    const found=text.indexOf(marker+'\n',offset); if(found<0) break;
    const start=text.indexOf('{',found+marker.length); if(start<0) throw new SchoolError('invalid_record','记录标记后缺少JSON');
    let depth=0,quoted=false,escaped=false,end=-1;
    for(let i=start;i<text.length;i++) {
      const c=text[i]; if(quoted){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')quoted=false;}
      else if(c==='"')quoted=true;else if(c==='{')depth++;else if(c==='}' && --depth===0){end=i+1;break;}
    }
    if(end<0) throw new SchoolError('invalid_record','结构化记录被截断');
    try { values.push(JSON.parse(text.slice(start,end))); } catch { throw new SchoolError('invalid_record','结构化记录不是有效JSON'); }
    offset=end;
  }
  return values;
}
export function parseReflection(doc) {
  const text=doc.blocks.filter(b=>b.block_type===14).map(textOf).join('\n');
  const metadata=markedJson(text,'school-record-meta-v1');
  requireValue(metadata.length===1,'reflection文档必须有唯一的school-record-meta-v1元数据');
  const interactions=[];
  for(const block of doc.blocks) {
    // Markers only count in code blocks, never inside quoted learner text.
    if(block.block_type!==14) continue;
    for(const interaction of markedJson(textOf(block),'school-interaction-v1')) interactions.push({...interaction,_block_id:block.block_id});
  }
  return {metadata:metadata[0],interactions,document_id:doc.document_id,url:doc.url,revision_id:doc.revision_id};
}
function elements(text) {const chunks=[];for(let i=0;i<text.length;i+=1500)chunks.push({text_run:{content:text.slice(i,i+1500)}});return chunks.length?chunks:[{text_run:{content:''}}];}
export function textBlock(text) {return {block_type:2,text:{elements:elements(text)}};}
export function codeBlock(text) {return {block_type:14,code:{elements:elements(text),style:{language:1,wrap:true}}};}
export function renderInteraction(turn) {
  const blocks=[{block_type:4,heading2:{elements:elements(`${turn.created_at}｜${turn.summary||turn.interaction_id}`)}}];
  for(const entry of turn.contributions) blocks.push(textBlock(`${LABELS[entry.kind]}｜${entry.capture==='verbatim'?'学员原话':'忠实概括'}｜${entry.confirmation}\n${entry.text}\n记录编号：${entry.entry_id}${entry.target_id?'\n关联原记录：'+entry.target_id:''}${entry.state?'\n问题状态：'+entry.state:''}${entry.relates_to?.length?'\n关联条目：'+entry.relates_to.join('、'):''}${entry.source_refs?.length?'\n案例依据：'+entry.source_refs.map(r=>`${r.case_id} PDF物理页 ${(r.pdf_pages||[]).join(',')} ${r.note||''}`).join('；'):''}`));
  if(turn.agent_feedback?.length)blocks.push(textBlock('Agent反馈（不是学员观点）\n'+turn.agent_feedback.join('\n')));
  if(turn.next_steps?.length)blocks.push(textBlock('待验证建议（不是学员承诺）\n'+turn.next_steps.join('\n')));
  blocks.push(codeBlock('school-interaction-v1\n'+JSON.stringify(turn)+'\nschool-interaction-end'));
  requireValue(blocks.length<=50,'单轮记录过长，请按真实讨论轮次拆分');
  return blocks;
}
export function validatePayload(payload,caseRow,allCases,timezone='Asia/Shanghai') {
  const {learner,consent,study_date,interaction:turn}=payload;
  requireValue(SLUG.test(learner?.learner_id||''),'需要学员自述的稳定learner_id');
  requireValue(plain(learner?.display_name)&&learner.display_name.length<=80,'需要学员确认的公开昵称');
  requireValue(consent?.granted===true && consent.scope==='session' && plain(consent.session_id) && iso(consent.granted_at),'缺少本会话持续记录授权');
  requireValue(/^\d{4}-\d{2}-\d{2}$/.test(study_date||'') && iso(turn?.created_at),'日期或轮次时间无效，时间必须含时区');
  requireValue(new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(turn.created_at))===study_date,'study_date与轮次时间不一致');
  requireValue(SLUG.test(turn?.interaction_id||''),'需要稳定interaction_id，重试不能换ID');
  requireValue(plain(turn.summary)&&turn.summary.length<=2000,'需要简短主题');
  requireValue(Array.isArray(turn.contributions)&&turn.contributions.length>0&&turn.contributions.length<=20,'每轮需1至20条真实表达');
  for(const key of ['agent_feedback','next_steps']) requireValue(Array.isArray(turn[key])&&turn[key].every(t=>typeof t==='string'),'Agent反馈和待验证建议必须单列字符串数组');
  for(let i=0;i<turn.contributions.length;i++) {
    const item=turn.contributions[i];
    requireValue(KINDS.has(item.kind)&&plain(item.text)&&item.text.length<=12000,'表达类型或内容无效');
    requireValue(['verbatim','paraphrase'].includes(item.capture)&&['captured','confirmed'].includes(item.confirmation),'必须标明原话/概括和是否经用户确认');
    requireValue(item.entry_id===`${caseRow.case_id}:${learner.learner_id}:${turn.interaction_id}:${String(i+1).padStart(2,'0')}`,'entry_id与案例/学员/轮次不一致');
    requireValue(Array.isArray(item.source_refs)&&Array.isArray(item.relates_to),'source_refs和relates_to必须为数组');
    for(const ref of item.source_refs) {
      const c=allCases.find(row=>row.case_id===ref.case_id); requireValue(c,'引用案例不在学校目录');
      const pages=new Set(c.source_pdf_pages||c.source_page_links?.map(p=>p.pdf_page)||[]);
      requireValue(Array.isArray(ref.pdf_pages)&&ref.pdf_pages.every(p=>Number.isInteger(p)&&pages.has(p)),'引用PDF页必须来自实际案例页码');
    }
    if(item.kind==='revision'||item.kind==='question_status') requireValue(plain(item.target_id)&&item.target_id.startsWith(`${caseRow.case_id}:${learner.learner_id}:`),'只能修订本人记录或更新本人问题');
    if(item.kind==='question_status') requireValue(['open','answered','deferred','discussed'].includes(item.state)&&item.confirmation==='confirmed','问题状态须由提问者明确确认');
  }
  requireValue(Buffer.byteLength(JSON.stringify(turn))<=60000,'单轮结构化记录超过60KB，请缩小本轮记录范围');
  return payload;
}

export class SchoolClient {
  constructor(lark=new LarkCli()) {this.lark=lark;this.origin=null;}
  pages(path,params={}) {
    const rows=[],seen=new Set();let token;
    for(let page=0;page<10000;page++) {
      const value=this.lark.api('GET',path,{...params,...(token?{page_token:token}:{})});
      const items=value.items??value.files??value.nodes;
      if(!Array.isArray(items)) throw new SchoolError('incomplete_read','分页接口缺少items，不能当成空目录');
      if(typeof value.has_more!=='boolean') throw new SchoolError('incomplete_read','分页接口未明确是否还有下一页，不能声称读取完整');
      rows.push(...items);
      if(!value.has_more)return rows;
      token=value.page_token??value.next_page_token;
      if(!token||seen.has(token)) throw new SchoolError('incomplete_read','分页游标缺失或重复，资料读取不完整');
      seen.add(token);
    }
    throw new SchoolError('incomplete_read','分页未结束，不声称已读取全部资料');
  }
  resolveDoc(value) {
    requireValue(plain(value),'缺少飞书文档入口');
    if(!value.includes('://')) {requireValue(/^[a-zA-Z0-9_-]+$/.test(value),'无效文档ID');return {document_id:value,url:null};}
    const url=new URL(value);requireValue(url.protocol==='https:'&&/(^|\.)(feishu\.cn|larksuite\.com)$/.test(url.hostname),'文档必须为飞书/Lark HTTPS地址');
    const parts=url.pathname.split('/').filter(Boolean);requireValue(parts.length>=2,'无效文档URL');
    if(parts[0]==='wiki') {
      const result=this.lark.api('GET','/open-apis/wiki/v2/spaces/get_node',{token:parts[1]});
      requireValue(result.node?.obj_type==='docx','学校索引必须为Docx文档');
      return {document_id:result.node.obj_token,url:url.origin+url.pathname};
    }
    requireValue(parts[0]==='docx','需要Docx或Wiki文档链接');
    return {document_id:parts[1],url:url.origin+url.pathname};
  }
  document(value) {
    const resolved=this.resolveDoc(value),id=resolved.document_id;
    if(resolved.url)this.origin=new URL(resolved.url).origin;
    const metadata=this.lark.api('GET',`/open-apis/docx/v1/documents/${id}`);
    const version=metadata.document?.revision_id;
    if(!Number.isInteger(version)||version<0)throw new SchoolError('incomplete_read','文档未返回有效版本，无法核实本次读取');
    const blocks=this.pages(`/open-apis/docx/v1/documents/${id}/blocks`,{page_size:500,document_revision_id:version??-1});
    const after=this.lark.api('GET',`/open-apis/docx/v1/documents/${id}`);
    if(after.document?.revision_id!==version) throw new SchoolError('source_changed','读取期间文档已变化，请重新读取本轮所需资料');
    return {document_id:id,revision_id:version,url:resolved.url||metadata.document?.url||(this.origin?`${this.origin}/docx/${id}`:null),title:metadata.document?.title,blocks,read_at:new Date().toISOString()};
  }
  manifest(value) {
    const doc=this.document(value);
    const text=doc.blocks.filter(b=>b.block_type===14).map(textOf).join('\n');
    let rows=markedJson(text,'school-manifest-v1');
    if(rows.length===0) {try{rows=[JSON.parse(text)];}catch{}}
    requireValue(rows.length===1&&rows[0].schema_version==='feishu-school-v1','缺少唯一有效学校目录');
    const manifest=rows[0];
    requireValue(Array.isArray(manifest.cases)&&manifest.cases.length>0&&plain(manifest.rules_document_id),'学校目录缺少案例或线上规则');
    requireValue(new Set(manifest.cases.map(c=>c.case_id)).size===manifest.cases.length,'案例目录存在重复case_id');
    return {...manifest,_source:{document_id:doc.document_id,revision_id:doc.revision_id,read_at:doc.read_at,url:doc.url}};
  }
  caseRow(manifest,value) {
    const row=manifest.cases.find(c=>c.case_id===String(value)||String(c.id)===String(value)||Number(/^case-(\d+)-/.exec(c.case_id)?.[1])===Number(value));
    requireValue(row,'学校目录中找不到该案例');return row;
  }
  list(parent) {
    requireValue(parent?.type==='folder'||parent?.type==='wiki','缺少有效的案例子目录');
    requireValue(/^[\w-]+$/.test(parent.token||''),'无效父节点ID');
    if(parent.type==='wiki') {
      requireValue(/^[\w-]+$/.test(parent.space_id||''),'Wiki缺少space_id');
      // The actual Wiki list API has no URL field. Retain the verified tenant origin.
      const origin=parent.url?new URL(parent.url).origin:this.origin;
      return this.pages(`/open-apis/wiki/v2/spaces/${parent.space_id}/nodes`,{parent_node_token:parent.token,page_size:50}).map(n=>({title:n.title,type:n.obj_type,document_id:n.obj_token,token:n.node_token,url:n.url||(origin?`${origin}/wiki/${n.node_token}`:null)}));
    }
    return this.pages('/open-apis/drive/v1/files',{folder_token:parent.token,page_size:200}).map(f=>({title:f.name,type:f.type,document_id:f.token,token:f.token,url:f.url||null}));
  }
  reflections(manifest,value,{cutoff}={}) {
    if(cutoff)requireValue(iso(cutoff),'截止时间须含时区');
    const row=this.caseRow(manifest,value),docs=this.list(row.reflections_parent),records=[],failures=[],excluded=[];
    // Only the maintained manifest can designate README/archive files as auxiliary.
    const auxiliary=new Set(row.reflections_auxiliary_document_ids||[]);
    for(const doc of docs) {
      if(auxiliary.has(doc.document_id)){excluded.push({document_id:doc.document_id,title:doc.title});continue;}
      if(typeof doc.title!=='string'||!doc.title.startsWith('school-reflection | ')){failures.push({document_id:doc.document_id,title:doc.title,error:'unclassified_reflection_document'});continue;}
      if(doc.type!=='docx'){failures.push({title:doc.title,error:'not_docx'});continue;}
      try {
        const record=parseReflection(this.document(doc.url||doc.document_id));
        record.url=record.url||doc.url;
        requireValue(record.metadata.case_id===row.case_id,'记录归档案例不匹配');
        requireValue(SLUG.test(record.metadata.learner_id||'')&&doc.title===reflectionTitle(record.metadata),'记录标题与学员元数据不匹配');
        requireValue(record.interactions.every(t=>iso(t.created_at)),'记录时间无效，不能可靠按截止时间汇总');
        for(const turn of record.interactions) {
          requireValue(SLUG.test(turn.interaction_id||'')&&Array.isArray(turn.contributions),'记录轮次或表达列表无效');
          if(turn.recording?.actor)requireValue(sameActor(turn.recording.actor,record.metadata.actor),'轮次提交身份与文档绑定身份不一致');
          for(const [index,entry] of turn.contributions.entries()) {
            requireValue(KINDS.has(entry.kind)&&plain(entry.text)&&entry.entry_id===`${row.case_id}:${record.metadata.learner_id}:${turn.interaction_id}:${String(index+1).padStart(2,'0')}`,'条目编号或表达内容与作者不匹配');
            if(entry.kind==='question_status')requireValue(entry.confirmation==='confirmed'&&['open','answered','deferred','discussed'].includes(entry.state)&&entry.target_id?.startsWith(`${row.case_id}:${record.metadata.learner_id}:`),'问题状态记录无效');
          }
        }
        record.interactions=record.interactions.filter(t=>!cutoff||Date.parse(t.created_at)<=Date.parse(cutoff));
        records.push(record);
      }catch(error){failures.push({document_id:doc.document_id,error:error.code||error.message});}
    }
    return {case_id:row.case_id,complete:failures.length===0,read_at:new Date().toISOString(),cutoff:cutoff||null,documents_enumerated:docs.length,records,failures,excluded};
  }
  learnerArchive(manifest,learnerId,actor) {
    // Live school-wide check closes cross-day and cross-case nickname impersonation.
    // No persistent identity/material cache; a future protected registry can reduce reads.
    const records=[];
    for(const row of manifest.cases) {
      const archive=this.reflections(manifest,row.case_id);
      if(!archive.complete)throw new SchoolError('incomplete_read','无法完整核实全校学员身份绑定；本轮暂不写入',{case_id:row.case_id,failures:archive.failures});
      for(const record of archive.records.filter(r=>r.metadata.learner_id===learnerId)) {
        if(!sameActor(record.metadata.actor,actor))throw new SchoolError('identity_mismatch','该 learner_id 已存在其他账户绑定或未绑定的历史记录，不能跨日期、跨案例仅凭昵称认领。',{document_id:record.document_id,url:record.url});
        records.push(record);
      }
    }
    return records;
  }
  verifyAppend(row,doc,before,interaction,{recovered=false}={}) {
    const fresh=parseReflection(this.document(doc.url||doc.document_id));
    if(canonical(fresh.metadata)!==canonical(before.metadata))throw new SchoolError('history_changed','写后核验发现文档作者或元数据变化，需要维护者检查',{document_id:doc.document_id,url:doc.url});
    for(const previous of before.interactions) {
      const {_block_id,...old}=previous;
      const current=fresh.interactions.filter(t=>t.interaction_id===previous.interaction_id);
      const {_block_id:ignored,...currentBody}=current[0]||{};
      if(current.length!==1||canonical(old)!==canonical(currentBody))throw new SchoolError('history_changed','核验发现历史记录发生变化，需要维护者检查；本轮写入状态见原文档',{document_id:doc.document_id,url:doc.url});
    }
    const saved=fresh.interactions.filter(t=>t.interaction_id===interaction.interaction_id);
    if(saved.length!==1)throw new SchoolError('save_unverified','写后回读未发现唯一新增条目，保存状态待核实',{document_id:doc.document_id,url:doc.url});
    const {_block_id,...body}=saved[0];
    if(canonical(body)!==canonical(interaction))throw new SchoolError('save_unverified','写后回读内容不一致',{document_id:doc.document_id,url:doc.url});
    const listing=this.list(row.reflections_parent),matches=listing.filter(d=>d.title===reflectionTitle(fresh.metadata));
    if(matches.length>1)throw new SchoolError('duplicate_documents','并发保存产生同名文档，需要维护者核对合并；记录原文仍保留',{document_id:doc.document_id,url:doc.url});
    const published=matches.length===1&&matches[0].document_id===doc.document_id;
    return {status:published?'verified_saved':'saved_unindexed',document_id:doc.document_id,url:doc.url?doc.url+'#'+_block_id:null,interaction_id:interaction.interaction_id,revision_id:fresh.revision_id,sharing_verified:false,...(recovered?{recovered:true}:{})};
  }
  append(manifest,value,input) {
    const row=this.caseRow(manifest,value);
    const payload=validatePayload(structuredClone(input),row,manifest.cases,manifest.timezone||'Asia/Shanghai');
    const actor=this.lark.identity();requireValue(plain(actor.open_id)&&plain(actor.app_id),'缺少可核实的飞书应用或用户身份');
    const {learner,study_date,interaction}=payload;
    interaction.recording={actor:{app_id:actor.app_id,open_id:actor.open_id},consent:payload.consent};
    const archive=this.learnerArchive(manifest,learner.learner_id,actor);
    const title=`school-reflection | ${row.case_id} | ${learner.learner_id} | ${study_date}`;
    const matches=this.list(row.reflections_parent).filter(d=>d.title===title&&d.type==='docx');
    if(matches.length>1)throw new SchoolError('duplicate_documents','发现同名记录文档，需要核对后合并；本次未写入');
    let doc,record;
    if(matches.length) {
      doc=this.document(matches[0].url||matches[0].document_id);doc.url=doc.url||matches[0].url;record=parseReflection(doc);
      const meta=record.metadata;
      requireValue(meta.case_id===row.case_id&&meta.learner_id===learner.learner_id&&meta.study_date===study_date,'文档元数据与目标不一致');
      if(!sameActor(meta.actor,actor))throw new SchoolError('identity_mismatch','当前登录账户未绑定此记录。旧迁移记录或他人记录不能仅凭昵称认领。');
      const existing=record.interactions.filter(t=>t.interaction_id===interaction.interaction_id);
      if(existing.length>1)throw new SchoolError('interaction_conflict','同一文档有重复轮次编号，需要维护者检查');
      if(existing.length) {
        const {_block_id,...body}=existing[0];
        if(canonical(body)!==canonical(interaction))throw new SchoolError('interaction_conflict','相同interaction_id已有不同内容，请用新轮次追加修订');
        return {status:'verified_existing',document_id:doc.document_id,url:doc.url?doc.url+'#'+_block_id:null,interaction_id:interaction.interaction_id};
      }
    }
    const targeted=interaction.contributions.filter(c=>c.kind==='revision'||c.kind==='question_status');
    if(targeted.length) {
      const entries=archive.filter(r=>r.metadata.case_id===row.case_id&&sameActor(r.metadata.actor,actor)).flatMap(r=>r.interactions.filter(t=>sameActor(t.recording?.actor,actor)).flatMap(t=>t.contributions));
      for(const entry of targeted){const old=entries.find(e=>e.entry_id===entry.target_id);requireValue(old,'找不到被关联的本人历史条目');if(entry.kind==='question_status')requireValue(old.kind==='question','状态更新必须指向一个原始问题');}
    }
    if(!doc) {
      const metadata={schema_version:'1.0',case_id:row.case_id,learner_id:learner.learner_id,display_name:learner.display_name,identity_source:'self_declared_with_feishu_binding',study_date,visibility:'school_shared',actor:{app_id:actor.app_id,open_id:actor.open_id},consent:payload.consent};
      const content='仅记录该学习者获授权公开的表达；个人观点不代表教材或共识。\n\n```text\nschool-record-meta-v1\n'+JSON.stringify(metadata)+'\nschool-record-meta-end\n```';
      // No automatic retry of document creation: a timeout may have created it.
      const created=this.lark.call(['docs','+create','--as','user','--title',title,'--parent-token',row.reflections_parent.token,'--doc-format','markdown','--content','-'],content);
      requireValue(created.document?.document_id,'创建文档未返回ID，保存状态待核实');
      if(created.warnings?.length)throw new SchoolError('creation_needs_verification','文档已创建但返回警告，请先核对后再追加',{document_id:created.document.document_id});
      doc=this.document(created.document.url||created.document.document_id);doc.url=doc.url||created.document.url;
      record=parseReflection(doc);
    }
    const clientToken=digest(`${manifest.school_id}|${doc.document_id}|${interaction.interaction_id}`);
    let writeError;
    try {
      this.lark.api('POST',`/open-apis/docx/v1/documents/${doc.document_id}/blocks/${doc.document_id}/children`,{document_revision_id:doc.revision_id??-1,client_token:clientToken},{index:-1,children:renderInteraction(interaction)});
    }catch(error){writeError=error;}
    // Success and uncertain writes use exactly the same history and index checks.
    try{return this.verifyAppend(row,doc,record,interaction,{recovered:Boolean(writeError)});}
    catch(error){
      if(['history_changed','duplicate_documents'].includes(error.code))throw error;
      throw new SchoolError('save_unverified','未能核实记录已保存；继续教学并保留本轮待提交内容，下次先查重',{document_id:doc.document_id,url:doc.url,cause:error.code,write_cause:writeError?.code});
    }
  }
  meeting(manifest,cases,options={}) {
    const outputs=cases.map(c=>this.reflections(manifest,c,options));
    return meetingData(outputs,manifest._source,options.cutoff);
  }
}

export function meetingData(outputs,manifestSource,cutoff) {
  const unique=new Map(),sources=[],errors=outputs.flatMap(o=>o.failures||[]);
  for(const output of outputs)for(const record of output.records) {
    sources.push({document_id:record.document_id,url:record.url,revision_id:record.revision_id});
    for(const turn of record.interactions) {
      requireValue(iso(turn.created_at),'记录时间缺少时区或无效');
      if(cutoff&&Date.parse(turn.created_at)>Date.parse(cutoff))continue;
      const {_block_id,...body}=turn,key=`${record.metadata.case_id}:${record.metadata.learner_id}:${turn.interaction_id}`;
      if(unique.has(key)) {if(canonical(unique.get(key).body)!==canonical(body))errors.push({interaction_id:turn.interaction_id,error:'conflicting_duplicate'});continue;}
      unique.set(key,{body,case_id:record.metadata.case_id,learner_id:record.metadata.learner_id,display_name:record.metadata.display_name,actor:record.metadata.actor||null,url:record.url?record.url+'#'+_block_id:null});
    }
  }
  const turns=[...unique.values()].sort((a,b)=>Date.parse(a.body.created_at)-Date.parse(b.body.created_at));
  const questions=new Map();
  for(const turn of turns)for(const entry of turn.body.contributions) {
    if(entry.kind==='question')questions.set(entry.entry_id,{...entry,state:'open',case_id:turn.case_id,learner_id:turn.learner_id,display_name:turn.display_name,actor:turn.actor,url:turn.url});
    if(entry.kind==='question_status') {
      const question=questions.get(entry.target_id);
      if(question&&question.case_id===turn.case_id&&question.learner_id===turn.learner_id&&entry.confirmation==='confirmed'&&sameActor(question.actor,turn.actor)&&sameActor(turn.actor,turn.body.recording?.actor))question.state=entry.state;
      else errors.push({entry_id:entry.entry_id,error:'unverified_question_status'});
    }
  }
  return {complete:errors.length===0&&outputs.every(o=>o.complete),read_at:new Date().toISOString(),cutoff:cutoff||null,manifest_source:manifestSource,sources,learner_count:new Set(turns.map(t=>t.learner_id)).size,interactions:turns,open_questions:[...questions.values()].filter(q=>q.state==='open'),unresolved_questions:[...questions.values()].filter(q=>q.state!=='answered'),failures:errors,note:'这是来源与记录清单，不是团队共识；多个文档版本不构成全库原子快照。'};
}

export async function fetchRouter(url=ROUTER,fetcher=fetch) {
  // Default GitHub route is read by a freshly queried commit, not a raw-main cache.
  const parsed=new URL(url);
  const match=parsed.hostname==='raw.githubusercontent.com'&&parsed.pathname.match(/^\/([^/]+)\/([^/]+)\/main\/(.+)$/);
  let actual=url,commit=null;
  if(match){const response=await fetcher(`https://api.github.com/repos/${match[1]}/${match[2]}/commits/main`,{headers:{'User-Agent':'FDE-School'},cache:'no-store',signal:AbortSignal.timeout(20000)});if(!response.ok)throw new SchoolError('router_unavailable','无法核实学校路由最新版');commit=(await response.json()).sha;requireValue(/^[a-f0-9]{40}$/.test(commit||''),'GitHub未返回有效版本');actual=`https://raw.githubusercontent.com/${match[1]}/${match[2]}/${commit}/${match[3]}`;}
  const response=await fetcher(actual,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!response.ok)throw new SchoolError('router_unavailable','学校入口读取失败：HTTP '+response.status);
  const router=await response.json();requireValue(router.schema_version==='school-backend-v1'&&['github','feishu'].includes(router.active_backend),'学校路由格式无效');
  if(router.active_backend==='feishu')requireValue(router.status==='ready'&&plain(router.feishu?.manifest_url),'飞书资料尚未验收发布，不能切换教学来源');
  return {...router,_read_at:new Date().toISOString(),_commit:commit};
}
function argsOf(argv) {
  const options={};const action=argv.shift()||'help';
  while(argv.length){const key=argv.shift();requireValue(key.startsWith('--'),'未知参数 '+key);if(key==='--help'){options.help=true;continue;}requireValue(argv.length>0,'参数缺少值 '+key);options[key.slice(2)]=argv.shift();}
  return {action,options};
}
export async function main(argv=process.argv.slice(2)) {
  const {action,options}=argsOf([...argv]);
  if(action==='help'||action==='--help'||options.help)return {usage:'node feishu_school.mjs <doctor|bootstrap|index|case|reflections|append|meeting> [--manifest <Feishu Docx/Wiki URL>] [--profile <CLI profile>]',commands:{doctor:'检查工具/本人登录；不输出凭据',bootstrap:'读取最新路由；--manifest 可直接使用已授权的飞书入口',index:'列案例',case:'--case 01，读完整基础文档及原PDF页链接',reflections:'--case 01 [--cutoff ISO-with-timezone]',append:'--case 01 --input -（JSON经stdin）或明确授权的输入文件',meeting:'--cases 01,02 [--cutoff ISO-with-timezone]（返回全部记录与来源）'},limits:'不安装其他Skills，不落地教材；首次安装CLI/OAuth由Agent协助。发布/权限需维护者真实审核。'};
  const lark=new LarkCli({profile:options.profile}),school=new SchoolClient(lark);
  if(action==='doctor'){const executable=findCli();return {cli:executable,identity:lark.identity(),ready:true};}
  let manifestUrl=options.manifest;
  if(action==='bootstrap'&&!manifestUrl){const router=await fetchRouter(options['router-url']);if(router.active_backend==='github')return {backend:'github',router};manifestUrl=router.feishu.manifest_url;}
  requireValue(plain(manifestUrl),'需要学校飞书manifest链接；先执行bootstrap获取最新入口');
  const manifest=school.manifest(manifestUrl);
  if(action==='bootstrap'){const rules=school.document(manifest.rules_document_id);return {backend:'feishu',manifest,rules:{...rules,text:rules.blocks.map(textOf).join('\n')}};}
  if(action==='index')return manifest;
  if(action==='case'){const row=school.caseRow(manifest,options.case),doc=school.document(row.base_document_id);return {case:row,document:doc,text:doc.blocks.map(textOf).join('\n'),source_page_links:row.source_page_links};}
  if(action==='reflections')return school.reflections(manifest,options.case,{cutoff:options.cutoff});
  if(action==='meeting'){requireValue(plain(options.cases),'需要指定案例列表');return school.meeting(manifest,options.cases.split(','),{cutoff:options.cutoff});}
  if(action==='append'){requireValue(options.input,'需要--input -或明确授权的输入文件');const text=readFileSync(options.input==='-'?0:options.input,'utf8').replace(/^\uFEFF/,'');return school.append(manifest,options.case,JSON.parse(text));}
  throw new SchoolError('invalid_input','未知操作 '+action);
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))main().then(value=>process.stdout.write(JSON.stringify({ok:true,data:value},null,2)+'\n')).catch(error=>{process.stderr.write(JSON.stringify({ok:false,error:{code:error.code||'runtime_error',message:redact(error.message),...error.details}},null,2)+'\n');process.exitCode=1;});
