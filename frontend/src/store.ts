import { useSyncExternalStore } from 'react';
import { emptyState, type State } from './core';
export const STORAGE_KEY='atmos.workspace.v1';
const listeners=new Set<()=>void>();
function load():State {
  const raw=localStorage.getItem(STORAGE_KEY);
  if(!raw) return emptyState();
  try {const data=JSON.parse(raw);if(data.schema!==1||!Array.isArray(data.chats)||!Array.isArray(data.profiles)||!Array.isArray(data.schedules)||!Array.isArray(data.runs)) throw Error();return data;}
  catch {throw new Error('本地工作空间数据无法读取。请先备份浏览器中的 atmos.workspace.v1，避免覆盖。');}
}
let state=load();
export function getState(){return state;}
export function change(mutator:(s:State)=>void) {
  state=load();
  const next=structuredClone(state);mutator(next);
  try {localStorage.setItem(STORAGE_KEY,JSON.stringify(next));}
  catch {window.dispatchEvent(new CustomEvent('atmos:error',{detail:'浏览器存储空间不足，修改未保存。请导出工作空间备份，再清理不需要的项目。'}));throw new Error('LocalStorage 写入失败');}
  state=next;listeners.forEach(fn=>fn());
}
export function replace(next:State){change(s=>Object.assign(s,next));}
export function useStore(){return useSyncExternalStore(fn=>{listeners.add(fn);return()=>listeners.delete(fn)},()=>state);}
window.addEventListener('storage',e=>{if(e.key===STORAGE_KEY){try{state=load();listeners.forEach(fn=>fn())}catch{window.dispatchEvent(new CustomEvent('atmos:error',{detail:'其他页面更改的数据无法读取，请导出备份后检查'}))}}});
