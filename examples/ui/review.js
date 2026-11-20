(() => {
 'use strict';
 const bases = {
  metric:{
   node:'M1', id:'MET-DEMO-01', version:'demo-v1', title:'月度有效验收工单数',
   stage:'M1 · 核对指标口径', purpose:'本步先讲清算什么、怎样算、依据在哪里。核对后再准备独立计算样例。',
   meaning:'这个月，有多少张工单完成了客户的有效验收？',
   scope:'只看验收数量；不能据此判断收入、满意度或结算金额。', rulesLabel:'口径怎么定',
   facts:[['统计对象','工单','每张工单只计一次'],['归月依据','有效签认日期','不按施工完工日期'],['去重依据','工单 ID','派工 ID 不能替代']],
   flowLabel:'计算顺序', flow:['筛选本月有效签认','按工单 ID 去重','计数，单位：张'],
   exampleId:'工单 B · 2026 年', exampleSteps:[['施工完工','11 月 30 日'],['有效签认','12 月 1 日'],['计入月份','12 月']],
   exampleNote:'因此不计入 11 月。依据 MR1–MR3；这是规则示例，实际程序未运行。',
   pending:'缺签认仅表示资料未知；出现多份签认时，先核实哪份有效。不能直接当零，或任取一份。',
   limit:'本例按 Asia/Shanghai 的自然月统计，月初包含、下月初不含。本小样本每单最多一条有效签认；缺签认不代表未验收，多条冲突签认须待核。只做只读汇总，不做结算或改状态；不能推断真实项目已覆盖异常。',
   next:'你核对后，流程下一步是 M2：让 AI 准备独立样例和期望结果。仍由你发出下一步指令。',
   steps:[['M0','任务与适配'],['M1','口径与映射'],['M2','独立标准'],['M3','构建指标库'],['M4','加载与检查'],['M5','实际验证'],['M6','验收与交接']]
  },
  model:{
   node:'S3', id:'CAND-DEMO-01', version:'demo-v1', title:'工单、派工与验收签认',
   stage:'S3 · 组织业务模型', purpose:'本步把已有候选认识组织成模型草稿，解释对象之间的关系和仍待核的边界。',
   meaning:'分清“维修任务、人员安排、客户验收”三件事。',
   scope:'仅据虚构维修材料形成的模型草稿，尚无真实项目采用记录。', rulesLabel:'对象与关系怎么定',
   facts:[['工单','维修任务','用工单 ID 区分身份'],['派工','人员安排','多次派工可关联同单'],['签认','客户验收','签认与完工时间分开']],
   flowLabel:'本例的关系', flow:['一张工单','可以关联多条派工记录'],
   exampleId:'工单 A · MR2–MR3', exampleSteps:[['业务任务','工单 A'],['派工记录','A1、A2'],['工单数量','仍为 1 张']],
   exampleNote:'两次派工不等于两张工单。保留关联和工单身份，后续统计才能避免重复计数。',
   pending:'本例限定每单最多一条有效签认；真实业务出现多份签认时，取舍规则及时间仍需核实。',
   limit:'这里使用 MR1–MR3 的虚构材料。不能把“样本每单最多一条有效签认”外推为全公司的规则；缺签认仅说明材料未知。用户理解一致不等于业务方确认或正式采用。',
   next:'你核对后，流程下一步是 S4：设计来源对照和使用测试。未决条目仍保留待核，不靠点击变成事实。',
   steps:[['plan','任务与方案'],['S1','材料盘点'],['S2','候选提取'],['S3','核查建模'],['S4','测试准备'],['S5','实际使用'],['S6','修订回归']]
  }
 };
 const $=id=>document.getElementById(id);
 const scopes={metric:'本批为 1 项指标的 2 个核对点',model:'本批为 1 组模型认识的 2 个核对点'};
 const queues={metric:[
  {...bases.metric,version:'demo-v2',short:'口径与归月',focus:'一单只计一次，按有效签认日期归月。'},
  {...bases.metric,id:'MET-DEMO-01-BOUNDARY',version:'demo-v2',short:'缺失与冲突',title:'同一指标 · 签认缺失或冲突时怎么办？',
   focus:'缺记录是未知；多份冲突签认先核实，不能随意取一份。',meaning:'这些记录，能否支持一个可信的完整总数？',
   facts:[['缺签认','资料未知','不能直接推断未验收'],['多份冲突签认','先核实','不能随意取第一份或最后一份'],['当前范围','限定小样本','不能推断真实项目全量已覆盖']],
   flowLabel:'处理顺序',flow:['识别缺口','保留来源与影响','取证后再核规则'],
   exampleId:'MR2 的边界说明 · 非运行结果',exampleSteps:[['发现情况','多份签认'],['当前状态','有效性待核'],['下一行动','查处理依据']],
   exampleNote:'这是待核场景的解释，没有实际多签认案例或处理答复；不能据此补出一条业务规则。'}
 ],model:[
  {...bases.model,version:'demo-v2',short:'对象与职责',focus:'工单、派工、签认，是三种不同的业务记录。'},
  {...bases.model,id:'CAND-DEMO-01-RELATION',version:'demo-v2',short:'身份与关系',title:'同一模型 · 多次派工仍关联同一张工单',
   focus:'记录有多条，不等于业务任务有多个。',meaning:'看清多次派工属于哪个维修任务，避免把安排次数当成工单数。',
   facts:[['工单身份','工单 ID','同一任务保留同一身份'],['派工身份','独立派工 ID','与工单 ID 区分'],['关联关系','派工指向工单','本例 A1、A2 都关联 A']],
   exampleNote:'A1、A2 关联同一工单 A。这是 MR2–MR3 的关系示例；完整签认规则仍受本例范围限制。'}
 ]};
 const choices=['理解一致','需要解释','修改意见','二次核实'];
 const labels={'理解一致':'理解一致','需要解释':'待解释','修改意见':'待修改','二次核实':'待业务核实','自由反馈':'待 AI 阅读'};
 const params=new URLSearchParams(location.search);
 let mode=params.get('module')==='model'?'model':'metric',view='review',positions={metric:0,model:0},drafts={},records={},blocked={},raws={},exportData=null;
 const entry=()=>queues[mode][positions[mode]];
 const itemKey=(m,d)=>m+':'+d.id;
 const storageKey=(m,d)=>'bmk-review:fictional-repair:'+m+':'+d.id+':'+d.version;
 const signature=d=>JSON.stringify(d);
 function warn(message){$('storage-warning').textContent=message;$('storage-warning').hidden=false;}
 function readRecord(m,d){
  const k=itemKey(m,d);records[k]=null;blocked[k]=false;
  try{
   const raw=localStorage.getItem(storageKey(m,d));raws[k]=raw;
   if(!raw)return;
   const r=JSON.parse(raw);
   if(r.schema_version!==1||r.project_id!=='fictional-repair'||r.module!==m||r.item_id!==d.id||r.item_version!==d.version||r.content_snapshot!==signature(d)||!choices.concat('自由反馈').includes(r.decision)||typeof r.user_text!=='string'||!Number.isFinite(Date.parse(r.created_at))||r.saved_to_project!==false||r.customer_confirmed!==false||r.advance_stage!==false)throw Error('incompatible record');
   records[k]=r;
  }catch(error){blocked[k]=true;warn('本机部分记录无法读取或与当前内容不一致，未计入进度，也不会覆盖。请保留原记录，交 AI 核对；当前意见可直接在聊天里说明。');}
 }
 for(const m of Object.keys(queues))for(const d of queues[m])readRecord(m,d);
 const requested=params.get('item');
 if(requested){const i=queues[mode].findIndex(d=>d.id===requested);if(i>=0)positions[mode]=i;else warn('链接中的条目不属于当前样稿。请按本批条目重新选择，不能将当前内容当作原链接对应的核对项。');}
 function draft(){const k=itemKey(mode,entry());if(!drafts[k]){const r=records[k];drafts[k]={choice:r?.decision==='自由反馈'?'':r?.decision||'',text:r?.user_text||''};}return drafts[k];}
 function dirty(){const f=draft(),r=records[itemKey(mode,entry())];return r?f.choice!==(r.decision==='自由反馈'?'':r.decision)||f.text!==r.user_text:!!(f.choice||f.text);}
 function capture(){drafts[itemKey(mode,entry())]={choice:document.querySelector('input[name="decision"]:checked')?.value||'',text:$('feedback').value};}
 function clearExport(){exportData=null;$('export-panel').hidden=true;$('download-status').textContent='';}
 function syncLocation(){const url=new URL(location.href);url.searchParams.set('module',mode);url.searchParams.set('item',entry().id);url.searchParams.delete('section');url.hash=view;history.replaceState(null,'',url);}
 function showView(name){view=name;document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));$('review-panel').hidden=view!=='review';$('questions-panel').hidden=view!=='questions';$('item-nav').hidden=view!=='review';$('batch-summary').hidden=view!=='summary';clearExport();syncLocation();}
 function focusReview(){showView('review');$('item-title').focus({preventScroll:true});$('review-panel').scrollIntoView({block:'start'});}
 function statusLabel(d){const k=itemKey(mode,d),r=records[k],f=drafts[k];const changed=f&&(r?(f.choice||'自由反馈')!==r.decision||f.text!==r.user_text:!!(f.choice||f.text));return changed?'有修改未记录':r?'已记录 · '+labels[r.decision]:'未记录';}
 function refreshProgress(){
  const list=queues[mode],saved=list.filter(d=>records[itemKey(mode,d)]),agreed=saved.filter(d=>records[itemKey(mode,d)].decision==='理解一致').length;
  $('batch-progress').textContent='已记录 '+saved.length+' / '+list.length+' 条';
  $('batch-detail').textContent='理解一致 '+agreed+' · 待跟进 '+(saved.length-agreed)+' · 未记录 '+(list.length-saved.length)+'（仅当前浏览器）';
  $('human-status').textContent='本机已记录 '+saved.length+' / '+list.length+'，AI 尚未接收';
  $('item-count').textContent=list.length;
  $('item-nav').replaceChildren(...list.map((d,i)=>{const b=document.createElement('button'),small=document.createElement('small');b.type='button';b.dataset.item=d.id;b.setAttribute('aria-current',String(i===positions[mode]));b.append((i+1)+'. '+d.short);small.textContent=statusLabel(d);b.append(small);b.addEventListener('click',()=>navigate(i));return b;}));
 }
 function updateFormState(message){
  const r=records[itemKey(mode,entry())],changed=dirty();
  $('item-status').textContent=statusLabel(entry());$('save-review').textContent=draft().choice==='理解一致'?'确认理解一致':r?'更新本条核对':'记录本条核对';
  $('save-status').textContent=message||(changed?'当前选择或修改尚未记录。':r?'已保存到本机 · '+labels[r.decision]+'；AI 尚未接收。':'选好处理方式后，点击“记录本条核对”。');
  $('save-status').classList.toggle('unsaved',changed);
  $('export-review').disabled=!r||changed;$('previous-item').disabled=positions[mode]===0;
  $('next-item').textContent=positions[mode]===queues[mode].length-1?'查看本批记录':'下一条 →';
  refreshProgress();
 }
 function render(){
  const d=entry();document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));
  $('stage-title').textContent=d.stage;$('purpose').textContent=d.purpose;$('item-id').textContent=d.id+' · '+d.version+' · 第 '+(positions[mode]+1)+' / '+queues[mode].length+' 条';$('item-title').textContent=d.title;
  $('entry-title').textContent=d.stage+' · '+d.short;$('entry-description').textContent=scopes[mode]+'。先看左侧解释，再在右侧记录判断。';
  $('unready-title').textContent=mode==='metric'?'M2 · 独立样例与期望核对':'S4 · 测试准备核对';
  $('meaning').textContent=d.meaning;$('scope-note').textContent=d.scope;$('rules-label').textContent=d.rulesLabel;$('review-focus').textContent=d.focus;
  $('limit-summary').textContent=d.pending;$('limit').textContent=d.limit;
  $('next').textContent='下一条只切换本批内容。下一流程的专门核对页尚未准备，不从本页自动进入。';
  $('flow-label').textContent=d.flowLabel;$('calculation-steps').replaceChildren(...d.flow.map(value=>{const li=document.createElement('li');li.textContent=value;return li;}));
  $('example-id').textContent=d.exampleId;$('example-note').textContent=d.exampleNote;
  $('example-track').replaceChildren(...d.exampleSteps.map(([label,value])=>{const li=document.createElement('li'),event=document.createElement('span'),answer=document.createElement('strong');event.className='example-event';event.textContent=label;answer.className='example-value';answer.textContent=value;li.append(event,answer);return li;}));
  $('stages').replaceChildren(...d.steps.map(([code,label])=>{const li=document.createElement('li'),strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=code+' · '+label;small.textContent=code===d.node?'当前演示节点':'';if(code===d.node)li.setAttribute('aria-current','step');li.append(strong,small);return li;}));
  $('facts').replaceChildren(...d.facts.map(([label,value,note])=>{const div=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd'),answer=document.createElement('strong'),hint=document.createElement('span');dt.textContent=label;answer.className='rule-value';answer.textContent=value;hint.className='rule-note';hint.textContent=note;dd.append(answer,hint);div.append(dt,dd);return div;}));
  $('sources').innerHTML='<p><strong>来源：本包《维修指标完整示范》第一节，MR1–MR3。</strong>均为虚构教学材料，不是客户原件。</p><blockquote>MR1：按客户有效验收签认时间统计每月工单数量。<br>MR2：每个统计对象为工单；派工编号不是工单编号；缺签认为未知，冲突待核。<br>MR3：A 有两条派工；B 在 11 月完工、12 月签认。</blockquote><p>以上为来源摘要。<a href="../维修指标-完整示范.md" target="_blank" rel="noopener">可选：打开完整示范</a></p><p>解释与原文不是同一层；真实项目需替换成实际来源、定位和版本。</p>';
  const f=draft();document.querySelectorAll('input[name="decision"]').forEach(r=>r.checked=r.value===f.choice);$('feedback').value=f.text;$('error').hidden=true;updateFormState();showView('review');
 }
 function navigate(i){capture();positions[mode]=i;render();focusReview();}
 function recordCurrent(event){
  event.preventDefault();capture();const f=draft(),d=entry(),k=itemKey(mode,d);
  if((!f.choice&&!f.text.trim())||(f.choice==='修改意见'&&!f.text.trim())){$('error').textContent=f.choice==='修改意见'?'请写下需要调整的地方。':'请选择处理方式，或写下你的意见。';$('error').hidden=false;return;}
  if(blocked[k]){warn('本条原记录尚待核对，未覆盖。请先在聊天中提供意见与当前条目版本。');return;}
  const r={schema_version:1,kind:'review_record',example:true,project_id:'fictional-repair',project:'虚构维修示范',module:mode,node:d.node,item_id:d.id,item_version:d.version,content_snapshot:signature(d),decision:f.choice||'自由反馈',user_text:f.text,source_ids:['MR1','MR2','MR3'],open_questions:['Q-DEMO-01'],created_at:new Date().toISOString(),status:'browser_saved_not_submitted',saved_to_project:false,customer_confirmed:false,adopted:false,advance_stage:false};
  try{
   if(localStorage.getItem(storageKey(mode,d))!==raws[k]){warn('另一页面修改了本条记录，未覆盖。请保留当前原话，重新打开后核对差异。');return;}
   const raw=JSON.stringify(r);localStorage.setItem(storageKey(mode,d),raw);if(localStorage.getItem(storageKey(mode,d))!==raw)throw Error('readback failed');raws[k]=raw;
  }catch(error){warn('未能保存到浏览器，本次不算已记录。当前原话仍在输入框，可复制给 AI；不要将下载或切页当成保存成功。');return;}
  records[k]=r;$('error').hidden=true;clearExport();updateFormState('已保存到本机 · '+labels[r.decision]+'。可以查看下一条；AI 尚未接收。');
 }
 function download(payload,filename){const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function summary(){capture();showView('summary');const list=queues[mode],saved=list.filter(d=>records[itemKey(mode,d)]).length;
  $('summary-description').textContent='本机已记录 '+saved+' / '+list.length+' 条；未记录的输入不会随本批导出。这里只汇总本人意见，不宣布阶段通过。';
  $('summary-items').replaceChildren(...list.map((d,i)=>{const li=document.createElement('li'),body=document.createElement('div'),title=document.createElement('strong'),p=document.createElement('p'),b=document.createElement('button'),r=records[itemKey(mode,d)];title.textContent=d.short+' · '+statusLabel(d);p.textContent=r?r.user_text||'没有补充原话':'尚无已记录意见';b.type='button';b.className='secondary';b.textContent='查看本条';b.addEventListener('click',()=>navigate(i));body.append(title,p);li.append(body,b);return li;}));
  $('download-batch').disabled=!saved;$('batch-download-status').textContent='';$('summary-title').focus({preventScroll:true});$('batch-summary').scrollIntoView({block:'start'});
 }
 $('review-form').addEventListener('submit',recordCurrent);
 $('review-form').addEventListener('input',()=>{capture();clearExport();$('error').hidden=true;updateFormState();});
 $('next-item').addEventListener('click',()=>positions[mode]<queues[mode].length-1?navigate(positions[mode]+1):summary());
 $('previous-item').addEventListener('click',()=>{if(positions[mode]>0)navigate(positions[mode]-1);});
 $('show-summary').addEventListener('click',summary);$('back-to-review').addEventListener('click',focusReview);$('go-review').addEventListener('click',focusReview);
 $('export-review').addEventListener('click',()=>{const r=records[itemKey(mode,entry())];if(!r||dirty())return;download(r,'review-record-'+r.item_id+'-'+r.item_version+'.json');updateFormState('已发起下载本条记录；AI 尚未接收，尚未写入项目。');});
 $('download-batch').addEventListener('click',()=>{const list=queues[mode];download({schema_version:1,kind:'review_batch',example:true,project_id:'fictional-repair',module:mode,created_at:new Date().toISOString(),items:list.map(d=>({item_id:d.id,item_version:d.version,record:records[itemKey(mode,d)]||null,has_unrecorded_edits:!!drafts[itemKey(mode,d)]&&statusLabel(d)==='有修改未记录'})),saved_to_project:false,customer_confirmed:false,advance_stage:false},'review-batch-'+mode+'.json');$('batch-download-status').textContent='已发起下载；请交给 AI 核对版本并归档，下载本身不算提交。';});
 document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{capture();mode=b.dataset.mode;render();}));
 document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{capture();showView(b.dataset.view);}));
 $('open-pending').addEventListener('click',()=>{capture();showView('questions');document.querySelector('[data-view="questions"]').focus();$('question-title').scrollIntoView({block:'start'});});
 $('route-toggle').addEventListener('click',()=>{const expanded=$('route-toggle').getAttribute('aria-expanded')!=='true';$('route-toggle').setAttribute('aria-expanded',String(expanded));$('route-toggle').textContent=expanded?'收起完整路线':'展开完整路线';document.querySelector('.sidebar').classList.toggle('route-expanded',expanded);});
 $('question-export').addEventListener('click',()=>{const d=entry(),text='二次访谈提纲 · Q-DEMO-01\n虚构维修示范 / '+d.id+' / '+d.version+'\n\n现场问法：最近有没有同一工单留下两份签认记录的情况？当时怎么判断哪份有效，能一起看一下记录和处理经过吗？\n\n找谁：实际办理验收、保管签认记录的人；规则确认责任另核。\n带回：原问原答、处理实例、记录标识与时间、判断依据、说明人及范围。没有案例保留未知。\n实际答复：尚未取得。';$('question-export-slot').append($('export-panel'));exportData={kind:'interview_outline',example:true,item_id:d.id,item_version:d.version,question_id:'Q-DEMO-01',text};$('export-title').textContent='可带走的访谈提纲';$('export-hint').textContent='仅整理待问问题，尚无实际答复。';$('export-text').value=text;$('export-panel').hidden=false;});
 $('download').addEventListener('click',()=>{if(!exportData)return;download(exportData,'interview-outline-'+exportData.item_id+'.json');$('download-status').textContent='已发起下载；不会自动提交。';});
 const initialView=location.hash,initialSection=params.get('section');render();
 if(initialView==='#questions')showView('questions');
 else if(initialView==='#summary')summary();
 else if(initialView==='#review'||initialSection){focusReview();const target={example:'review-example',rules:'review-rules',feedback:'review-form'}[initialSection];if(target){$(target).setAttribute('tabindex','-1');$(target).focus({preventScroll:true});$(target).scrollIntoView({block:'start'});const url=new URL(location.href);url.searchParams.set('section',initialSection);history.replaceState(null,'',url);}}
})();
