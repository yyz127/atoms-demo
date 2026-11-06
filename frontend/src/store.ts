import { useSyncExternalStore } from 'react';
import { emptyState, type State, type Profile } from './core';
export const STORAGE_KEY='atmos.workspace.v1';
type Account={id:string;email:string;needs_password:boolean};
let account:Account|null=null;
let revision=0, pending=false, saving=false, migrating=false, syncError='', state:State=loadGuest();
const listeners=new Set<()=>void>();
function emit(){listeners.forEach(fn=>fn())}
function error(text:string){window.dispatchEvent(new CustomEvent('atmos:error',{detail:text}))}
function parse(raw:string|null):State {if(!raw)return emptyState();const data=JSON.parse(raw);if(data.schema!==1||!Array.isArray(data.chats)||!Array.isArray(data.profiles)||!Array.isArray(data.runs))throw Error('工作空间数据格式无效');delete data.schedules;return data}
function loadGuest():State {try{return parse(localStorage.getItem(STORAGE_KEY))}catch{throw Error('本地工作空间数据无法读取，请先备份 atmos.workspace.v1。')}}
function previewKey(){return 'atmos.preview.'+account!.id}
function readPreview():Record<string,Record<string,string>>{try{return JSON.parse(localStorage.getItem(previewKey())||'{}')}catch{return {}}}
function cloudCopy(s:State):State {const copy=structuredClone(s);copy.profiles=[];for(const c of copy.chats)c.previewData={};return copy}
function savePreview(s:State){const values:Record<string,Record<string,string>>={};for(const c of s.chats)if(Object.keys(c.previewData||{}).length)values[c.id]=c.previewData;localStorage.setItem(previewKey(),JSON.stringify(values))}
async function request(path:string, options:RequestInit={}) {const r=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...(account?{'X-Atmos-User':account.id}:{}),...options.headers}});if(!r.ok){const v=await r.json().catch(()=>({}));throw Error(typeof v.detail==='string'?v.detail:'云端请求失败（'+r.status+'）')}return r.json()}
export function getAccount(){return account}
export function getSyncStatus(){return syncError?'云端未保存：'+syncError:saving||pending?'正在保存到云端':'已保存到云端'}
export function useSyncStatus(){return useSyncExternalStore(fn=>{listeners.add(fn);return()=>listeners.delete(fn)},getSyncStatus)}
export function getState(){return state}
export async function initialize(){
 const r=await fetch('/api/auth/me',{cache:'no-store'});if(r.status===401){account=null;state=loadGuest();emit();return}
 if(!r.ok)throw Error('无法读取登录状态，请检查网络后重试');
 account=await r.json();try{const [workspace,profiles]=await Promise.all([request('/workspace'),request('/profiles')]);revision=workspace.revision;state=workspace.data?parse(JSON.stringify({...workspace.data,profiles:[]})):emptyState();state.profiles=profiles.map((p:Profile & {key_last4:string})=>({...p,key:'',key_last4:p.key_last4}));const previews=readPreview();for(const c of state.chats)c.previewData=previews[c.id]||{};emit()}catch(e){account=null;throw e}
}
async function flush(){if(!account||saving||!pending||syncError)return;saving=true;emit();try{while(pending){pending=false;const result=await request('/workspace',{method:'PUT',body:JSON.stringify({revision,data:cloudCopy(state)})});revision=result.revision}}catch(e){pending=true;syncError=(e as Error).message;error('云端保存失败，修改尚未同步：'+syncError)}finally{saving=false;emit()}}
export function retrySync(){syncError='';void flush();emit()}
export async function waitForSync(){if(!account)return;await flush();while(saving)await new Promise(r=>setTimeout(r,25));if(pending||syncError)throw Error(syncError||'云端数据尚未保存')}
export function change(mutator:(s:State)=>void) {
 if(migrating)throw Error('正在迁移本地记录，请稍候');
 if(!account)state=loadGuest();const next=structuredClone(state);mutator(next);
 try{if(account)savePreview(next);else localStorage.setItem(STORAGE_KEY,JSON.stringify(next))}catch{error('浏览器本地存储失败，修改未保存');throw Error('LocalStorage 写入失败')}
 const changed=account&&JSON.stringify(cloudCopy(state))!==JSON.stringify(cloudCopy(next));state=next;emit();if(changed){pending=true;void flush()}
}
export function replace(next:State){change(s=>Object.assign(s,next))}
export async function saveCloudProfile(p:Profile){if(!account)throw Error('请先登录');await request('/profiles/'+encodeURIComponent(p.id),{method:'PUT',body:JSON.stringify(p)});const profiles=await request('/profiles');state={...state,profiles:profiles.map((x:Profile & {key_last4:string})=>({...x,key:''}))};emit()}
export async function deleteCloudProfile(id:string){await request('/profiles/'+encodeURIComponent(id),{method:'DELETE'});state={...state,profiles:state.profiles.filter(p=>p.id!==id)};emit()}
export async function testCloudProfile(id:string){return request('/profiles/'+encodeURIComponent(id)+'/test',{method:'POST'})}
export async function logout(){try{await waitForSync()}catch(e){if(!confirm('有修改尚未保存到云端。现在退出会丢失这些未同步修改，确定退出吗？'))throw e}await request('/auth/logout',{method:'POST'});location.assign('/')}
export function guestMigrationPreview(){const s=loadGuest();return {chats:s.chats.length,folders:s.folders.length,runs:s.runs.length,notices:s.notices.length,profiles:s.profiles.length,versions:s.chats.reduce((n,c)=>n+c.versions.length,0),reports:s.chats.reduce((n,c)=>n+c.messages.filter(m=>m.kind==='research'||m.kind==='check').length,0),titles:s.chats.slice(0,10).map(c=>c.title)}}
export async function migrateGuest(){if(!account)throw Error('请先登录');if(migrating)throw Error('迁移正在进行');migrating=true;try{await waitForSync();const local=loadGuest();const ids=new Set([...state.chats.map(x=>x.id),...state.folders.map(x=>x.id),...state.runs.map(x=>x.id),...state.notices.map(x=>x.id)]);const all=[...local.chats,...local.folders,...local.runs,...local.notices];if(all.some(x=>ids.has(x.id)))throw Error('本地记录与云端存在相同编号，未执行迁移，请先处理重复记录');const next=structuredClone(state);next.chats.push(...local.chats.map(c=>({...c,previewData:{}})));next.folders.push(...local.folders);next.runs.push(...local.runs.map(r=>r.status==='running'?{...r,status:'cancelled' as const,ended:Date.now()}:r));next.notices.push(...local.notices);const result=await request('/workspace',{method:'PUT',body:JSON.stringify({revision,data:cloudCopy(next)})});revision=result.revision;state=next;emit()}finally{migrating=false}}

export function useStore(){return useSyncExternalStore(fn=>{listeners.add(fn);return()=>listeners.delete(fn)},()=>state)}
window.addEventListener('storage',e=>{if(!account&&e.key===STORAGE_KEY){try{state=loadGuest();emit()}catch{error('本地数据无法读取，请导出备份后检查')}}});
