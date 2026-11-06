import { parse } from 'acorn';

export type Profile = {id:string; name:string; provider:string; protocol:string; base_url:string; model:string; key:string; key_last4?:string};
export type Version = {id:string; number:number; title:string; html:string; created:number; status:'ready'|'failed'; error?:string};
export type Message = {id:string; role:'user'|'assistant'; kind:'text'|'research'|'check'|'system'; content:string; created:number; runId?:string};
export type ResearchDocument = {id:string; name:string; kind:'plan'|'report'; content:string; created:number; runId?:string};
export type Chat = {id:string; title:string; folderId:string|null; favorite:boolean; deleted:boolean; created:number; updated:number; versions:Version[]; activeId:string|null; messages:Message[]; previewData:Record<string,string>; publication?:{id:string; secret:string; url:string; versionId:string}; plan?:{text:string; prompt:string; profileId:string}; researchPlan?:{documentId:string; prompt:string; profileId:string; runId:string}; documents?:ResearchDocument[]; references:string[]};
export type Run = {id:string; chatId:string; scheduleId?:string; mode:string; prompt:string; status:'running'|'awaiting_plan'|'succeeded'|'failed'|'cancelled'|'missed'|'skipped'; created:number; ended?:number; events:string[]; error?:string};
export type State = {schema:1; profiles:Profile[]; profileId:string; chats:Chat[]; folders:{id:string;name:string}[]; runs:Run[]; notices:{id:string; title:string; chatId?:string; created:number; read:boolean}[]};
export const uid = () => crypto.randomUUID().replaceAll('-','');
export const emptyState = ():State => ({schema:1,profiles:[],profileId:'',chats:[],folders:[],runs:[],notices:[]});
export const newChat = (title='新的想法',folderId:string|null=null):Chat => ({id:uid(),title,folderId,favorite:false,deleted:false,created:Date.now(),updated:Date.now(),versions:[],activeId:null,messages:[],previewData:{},references:[]});
export const activeVersion = (chat?:Chat) => chat?.versions.find(v=>v.id===chat.activeId);
export function validateHtml(html:string):void {
  if(!/<html[\s>]/i.test(html)||!/<\/html\s*>/i.test(html)) throw new Error('需要完整的 HTML 文档');
  if(new TextEncoder().encode(html).length>2_000_000) throw new Error('HTML 超过 2 MB');
  const document = new DOMParser().parseFromString(html,'text/html');
  for(const script of document.querySelectorAll('script')) {
    if(script.src) throw new Error('单文件应用不能依赖外部 JavaScript，请将脚本内联');
    if(!['','module','text/javascript','application/javascript'].includes(script.type)) continue;
    parse(script.textContent||'',{ecmaVersion:'latest',sourceType:script.type==='module'?'module':'script',allowReturnOutsideFunction:false});
  }
}

export function safeJson(value:unknown):string {return JSON.stringify(value).replace(/</g,'\\u003c').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');}

/** Opaque sandbox gets an app-scoped Storage facade. The parent persists only this
 * map, never grants access to platform keys or the rest of LocalStorage. */
export function storageDocument(html:string, data:Record<string,string>, namespace:string, preview:boolean):string {
  const config=safeJson({seed:data,namespace,preview});
  const bootstrap=`<script>(function(){const c=${config};let native=null,m={...c.seed};if(!c.preview){try{native=window.localStorage;const old=native.getItem(c.namespace);if(old)m=JSON.parse(old)}catch(e){}}const save=()=>{if(c.preview)parent.postMessage({type:'atmos:storage',namespace:c.namespace,values:m},'*');else if(native)try{native.setItem(c.namespace,JSON.stringify(m))}catch(e){window.dispatchEvent(new CustomEvent('atmos:storage-error',{detail:'存储已满，数据未保存'}))}};const methods={getItem:k=>Object.hasOwn(m,String(k))?m[String(k)]:null,setItem:(k,v)=>{m[String(k)]=String(v);save()},removeItem:k=>{delete m[String(k)];save()},clear:()=>{m={};save()},key:i=>Object.keys(m)[Number(i)]??null};const storage=new Proxy(methods,{get:(t,k)=>k==='length'?Object.keys(m).length:k in t?t[k]:m[k],set:(t,k,v)=>{methods.setItem(k,v);return true},deleteProperty:(t,k)=>{methods.removeItem(k);return true},ownKeys:()=>Object.keys(m),getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})});Object.defineProperty(window,'localStorage',{value:storage,configurable:false});})();<\/script>`;
  return html.replace(/<head(?:\s[^>]*)?>/i, match=>match+bootstrap).replace(/^(?![\s\S]*<head[\s>])/i,bootstrap);
}

export function cloneChat(source:Chat,version:Version):Chat {
  const c=newChat(source.title+' · 副本',source.folderId);
  const v={...version,id:uid(),number:1,created:Date.now()};
  c.versions=[v];c.activeId=v.id;
  return c;
}

export function download(name:string, content:string, type='text/html;charset=utf-8') {
  const url=URL.createObjectURL(new Blob([content],{type}));
  const a=document.createElement('a');a.href=url;a.download=name;a.hidden=true;
  document.body.appendChild(a);
  try{a.click()}finally{a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)}
}

export function exportHtml(chat:Chat,version:Version,withData:boolean):string {
  return storageDocument(version.html,withData?chat.previewData:{},'atmos.app.'+uid(),false);
}
