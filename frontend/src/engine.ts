import {change,getState,getAccount} from './store';
import {uid,validateHtml,activeVersion} from './core';
const controllers=new Map<string,AbortController>();
export async function api(path:string, body?:unknown, method='POST') {
  const response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json',...(getAccount()?{'X-Atmos-User':getAccount()!.id}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  if(!response.ok){const error=await response.json().catch(()=>({detail:'服务连接失败'}));throw new Error(typeof error.detail==='string'?error.detail:'请求参数无效，请检查设置');}
  return response.json();
}
function note(runId:string,text:string){change(s=>{const r=s.runs.find(x=>x.id===runId);if(r){r.events=[...r.events.slice(-99),text]}})}
export function stopRun(id:string){controllers.get(id)?.abort();change(s=>{const r=s.runs.find(x=>x.id===id);if(r&&['running','awaiting_plan'].includes(r.status)){r.status='cancelled';r.ended=Date.now()}const c=s.chats.find(x=>x.id===r?.chatId);if(c&&r?.mode==='plan')delete c.plan;});}

async function stream(body:unknown,signal:AbortSignal,receive:(e:any)=>void){
  const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json',...(getAccount()?{'X-Atmos-User':getAccount()!.id}:{})},body:JSON.stringify(body),signal});
  if(!response.ok){const e=await response.json().catch(()=>({detail:'无法连接 Python 服务'}));throw Error(typeof e.detail==='string'?e.detail:'请求被拒绝');}
  const reader=response.body!.getReader(),decoder=new TextDecoder();let buffer='',finished=false;
  while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let end;
    while((end=buffer.indexOf('\n\n'))>=0){const block=buffer.slice(0,end);buffer=buffer.slice(end+2);for(const line of block.split('\n'))if(line.startsWith('data: ')){const event=JSON.parse(line.slice(6));if(event.type==='error')throw Error(event.text);if(event.type==='done')finished=true;receive(event);}}
  }
  if(!finished)throw Error('连接提前结束，未将不完整输出保存为成功版本');
}

export async function runChat(chatId:string,prompt:string,mode:string,profileId:string,options:{plan?:string}={}){
  const state=getState(),chat=state.chats.find(c=>c.id===chatId),profile=state.profiles.find(p=>p.id===profileId);
  if(!chat||chat.deleted)throw Error('对话不存在');if(!profile||(!getAccount()&&!profile.key))throw Error('请先配置可用的模型 API Key');
  if(state.runs.some(r=>r.chatId===chatId&&r.status==='running'))throw Error('此对话已有运行中的任务，请先停止或等待完成');
  const id=uid(),controller=new AbortController();controllers.set(id,controller);
  localStorage.setItem('atmos.run.'+id,String(Date.now()+10000));
  const base=activeVersion(chat)?.html||'';
  if(mode==='research'&&!options.plan?.trim())throw Error('请先确认研究计划');
  change(s=>{s.runs.unshift({id,chatId,mode,prompt,status:'running',created:Date.now(),events:['任务已启动']});const c=s.chats.find(x=>x.id===chatId)!;if(mode!=='check'&&(mode==='research_plan'||!options.plan))c.messages.push({id:uid(),role:'user',kind:'text',content:prompt,created:Date.now(),runId:id});c.updated=Date.now();if(mode==='build'||mode==='plan')delete c.plan;if(c.title==='新的想法')c.title=prompt.slice(0,32);});
  const guard=setInterval(()=>{localStorage.setItem('atmos.run.'+id,String(Date.now()+10000));const r=getState().runs.find(r=>r.id===id),c=getState().chats.find(c=>c.id===chatId);if(!r||r.status!=='running'||!c||c.deleted)controller.abort();},750);
  let text='',html='',versionId='',lastUi=0;
  const context=(chat.messages.filter(m=>m.kind!=='check').slice(-12).map(m=>`${m.role}: ${m.content.slice(0,3000)}`).join('\n')+'\n'+chat.references.map(id=>state.chats.flatMap(c=>c.messages).find(m=>m.id===id)?.content||'').join('\n')+(mode==='check'?'\n当前浏览器中本应用的只读预览数据：\n'+JSON.stringify(chat.previewData).slice(0,16000):'')).slice(0,80000);
  try {
    for(let attempt=0;attempt<=3;attempt++){
      text='';html='';
      await stream({...(getAccount()?{profile_id:profile.id}:{profile}),mode,prompt:attempt?prompt+'\n请修复上次HTML的语法错误：'+getState().chats.find(c=>c.id===chatId)?.versions.find(v=>v.id===versionId)?.error:prompt,html:attempt?getState().chats.find(c=>c.id===chatId)?.versions.find(v=>v.id===versionId)?.html:base,context,plan:options.plan||''},controller.signal,event=>{
        if(controller.signal.aborted)throw new DOMException('Stopped','AbortError');
        if(event.type==='stage')note(id,event.text);
        if(event.type==='sources')note(id,`取得 ${event.sources.length} 个来源，其中 ${event.sources.filter((x:any)=>x.read).length} 个已读正文`);
        if(event.type==='delta'){text+=event.text;if(Date.now()-lastUi>500){window.dispatchEvent(new CustomEvent('atmos:stream',{detail:{id,text,mode}}));lastUi=Date.now();}}
        if(event.type==='result')text=event.text;
        if(event.type==='artifact')html=event.html;
      });
      if(mode!=='build')break;
      if(!html)throw Error('模型没有返回 HTML 产物');
      let error='';try{validateHtml(html)}catch(e){error=(e as Error).message}
      if(!versionId)versionId=uid();
      change(s=>{const c=s.chats.find(x=>x.id===chatId)!;const previous=c.versions.find(v=>v.id===versionId);const v={id:versionId,number:previous?.number||c.versions.length+1,title:prompt.slice(0,60),html,created:previous?.created||Date.now(),status:error?'failed' as const:'ready' as const,error};c.versions=previous?c.versions.map(x=>x.id===v.id?v:x):[...c.versions,v];});
      if(!error){note(id,'HTML 结构与 JavaScript 语法检查通过；请在预览中验证交互');break;}
      if(attempt===3)throw Error('已达到 3 次自动修复上限：'+error);
      note(id,`发现语法错误，正在第 ${attempt+1}/3 次自动修复`);
    }
    if(controller.signal.aborted)throw new DOMException('Stopped','AbortError');
    change(s=>{const r=s.runs.find(x=>x.id===id)!;if(r.status!=='running')return;
      const c=s.chats.find(x=>x.id===chatId)!;r.status=(mode==='plan'||mode==='research_plan')?'awaiting_plan':'succeeded';r.ended=Date.now();c.updated=Date.now();
      if(mode==='research_plan'){const old=c.researchPlan;const docId=old?.documentId||uid();c.documents=c.documents||[];const doc={id:docId,name:'research-plan.md',kind:'plan' as const,content:text,created:Date.now(),runId:id};c.documents=old?c.documents.map(d=>d.id===docId?doc:d):[...c.documents,doc];if(old){const prior=s.runs.find(x=>x.id===old.runId);if(prior?.status==='awaiting_plan')prior.status='succeeded'}c.researchPlan={documentId:docId,prompt:old?.prompt||prompt,profileId,runId:id};}
      else if(mode==='plan')c.plan={text,prompt,profileId};
      else if(mode==='build'){c.activeId=versionId;c.messages.push({id:uid(),role:'assistant',kind:'text',content:`已生成 v${c.versions.find(v=>v.id===versionId)!.number}。可切换代码与预览，继续描述需求即可迭代。`,created:Date.now(),runId:id});}
      else {const messageId=uid();c.messages.push({id:messageId,role:'assistant',kind:mode==='check'?'check':'research',content:text,created:Date.now(),runId:id});if(mode==='research'){c.documents=c.documents||[];c.documents.push({id:messageId,name:'research-report.md',kind:'report',content:text,created:Date.now(),runId:id});const waiting=s.runs.find(x=>x.id===c.researchPlan?.runId);if(waiting?.status==='awaiting_plan')waiting.status='succeeded';delete c.researchPlan;}}
    });
  }catch(error){
    const cancelled=controller.signal.aborted;
    change(s=>{const r=s.runs.find(x=>x.id===id);if(!r)return;r.status=cancelled?'cancelled':'failed';r.error=cancelled?'已停止':(error as Error).message;r.ended=Date.now();});
    if(!cancelled)window.dispatchEvent(new CustomEvent('atmos:error',{detail:(error as Error).message}));
  }finally{clearInterval(guard);controllers.delete(id);localStorage.removeItem('atmos.run.'+id);window.dispatchEvent(new CustomEvent('atmos:stream',{detail:{id,text:'',mode}}));}
}

export function startRunRecovery(){
  const recover=()=>{
    const orphaned=getState().runs.filter(r=>r.status==='running'&&!controllers.has(r.id)&&Number(localStorage.getItem('atmos.run.'+r.id)||0)<Date.now());
    if(orphaned.length)change(s=>{for(const r of s.runs)if(orphaned.some(x=>x.id===r.id)){r.status='failed';r.error='页面已关闭或刷新，本次运行已中断，可手动重试';r.ended=Date.now();}});
  };
  recover();const timer=setInterval(recover,5000);return()=>clearInterval(timer);
}
