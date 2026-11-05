import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const output='/private/tmp/atmos-qa';await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const base='http://127.0.0.1:8000';
const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>Counter</title><style>body{font-family:system-ui;padding:50px;background:#f7f8fc;color:#343344}button{background:#8d75b7;color:white;border:0;padding:12px 22px;border-radius:9px}#count{font-size:40px;margin:20px 0}</style></head><body><h1>我的计数器</h1><p>真实交互与本地持久化</p><div id="count"></div><button id="add">增加</button><script>let n=Number(localStorage.getItem('count')||0);const el=document.getElementById('count');el.textContent=n;document.getElementById('add').onclick=()=>{n++;localStorage.setItem('count',n);el.textContent=n};</script></body></html>`;
const fixture=output+'/计数器.html';await fs.writeFile(fixture,html);
const state=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('atmos.workspace.v1')));
async function waitFor(fn){for(let i=0;i<80;i++){if(await fn())return;await page.waitForTimeout(100)}throw Error('Condition did not become true')}
try{
 await page.goto(base);await page.getByText('让想法，').waitFor();await page.screenshot({path:output+'/home.png',fullPage:true});
 await page.locator('input[type=file]').first().setInputFiles(fixture);
 await page.frameLocator('iframe[title="应用实时预览"]').locator('#count').waitFor();
 const frame=page.frameLocator('iframe[title="应用实时预览"]');await frame.locator('#add').click();
 await waitFor(async()=>(await state()).chats[0].previewData.count==='1');
 const originalId=(await state()).chats[0].id;
 await page.reload();await page.frameLocator('iframe[title="应用实时预览"]').locator('#count').waitFor();assert.equal(await page.frameLocator('iframe[title="应用实时预览"]').locator('#count').innerText(),'1');
 const isolated=await page.frames().find(f=>f.url()==='about:srcdoc').evaluate(()=>{try{void parent.localStorage;return false}catch{return true}});assert.equal(isolated,true);
 await page.screenshot({path:output+'/workspace.png',fullPage:true});
 // Export both choices; opening downloaded HTML verifies its actual standalone runtime.
 await page.getByTitle('导出 HTML').click();await page.getByRole('button',{name:'带预览数据',exact:false}).click();
 const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载 HTML',exact:true}).click()]);await download.saveAs(output+'/with-data.html');
 const standalone=await context.newPage();await standalone.goto('file://'+output+'/with-data.html');assert.equal(await standalone.locator('#count').innerText(),'1');await standalone.locator('#add').click();await standalone.reload();assert.equal(await standalone.locator('#count').innerText(),'2');await standalone.close();
 await page.getByTitle('导出 HTML').click();
 const [emptyDownload]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载 HTML',exact:true}).click()]);await emptyDownload.saveAs(output+'/empty.html');
 const blank=await context.newPage();await blank.goto('file://'+output+'/empty.html');assert.equal(await blank.locator('#count').innerText(),'0');await blank.close();
 // A protocol fixture exercises the UI pipeline; this is not a real vendor evaluation.
 await page.getByRole('button',{name:'设置与模型',exact:false}).click();
 await page.getByLabel('模型名称',{exact:true}).fill('test-model');await page.getByPlaceholder('输入你的 API Key').fill('test-only-key');await page.getByRole('button',{name:'保存模型',exact:true}).click();await page.getByRole('button',{name:'关闭',exact:true}).click();
 const requests=[];
 await page.route('**/api/run',async route=>{const body=route.request().postDataJSON();requests.push(body);const events=body.mode==='build'?[{type:'stage',text:'测试协议：生成单个 HTML'},{type:'artifact',html:html.replace('我的计数器','改进的计数器')}]:[{type:'result',text:body.mode==='plan'?'1. 保留本地数据\n2. 修改页面标题':'# 检查报告\n测试协议返回，未进行真实网络研究。'}];await route.fulfill({status:200,contentType:'text/event-stream',body:[...events,{type:'done'}].map(e=>'data: '+JSON.stringify(e)+'\n\n').join('')})});
 await page.getByLabel('描述你的需求').fill('修改计数器标题');await page.getByRole('button',{name:'发送需求'}).click();
 await waitFor(async()=>(await state()).chats.find(c=>c.id===originalId).versions.length===2);
 await page.getByTitle('历史记录').click();assert.equal(await page.locator('.history-row').count(),2);await page.locator('.history-row').last().getByRole('button',{name:'恢复',exact:false}).click();
 assert.equal((await state()).chats.find(c=>c.id===originalId).activeId,(await state()).chats.find(c=>c.id===originalId).versions[0].id);
 await page.getByLabel('构建模式').selectOption('plan');await page.getByLabel('描述你的需求').fill('先给出实施计划');await page.getByRole('button',{name:'发送需求'}).click();
 await page.getByRole('button',{name:'确认并执行'}).waitFor();assert.equal(requests.at(-1).mode,'plan');
 const before=requests.length;await page.waitForTimeout(100);assert.equal(requests.length,before);
 await page.getByLabel('编辑实施计划').fill('只修改标题，保留数据。');await page.getByRole('button',{name:'确认并执行'}).click();
 await waitFor(()=>requests.at(-1).mode==='build');assert.equal(requests.at(-1).plan,'只修改标题，保留数据。');await waitFor(async()=>(await state()).runs[0].status==='succeeded');
 // Publish using the actual Python service, then use the actual public viewer.
 await page.getByRole('button',{name:'发布',exact:true}).click();await page.getByLabel('将当前预览数据一起公开为初始数据').check();await page.getByRole('button',{name:'发布并获取链接'}).click();await page.locator('.published-link a').waitFor();
 const url=await page.locator('.published-link a').getAttribute('href');const visitor=await browser.newContext();const publicPage=await visitor.newPage();await publicPage.goto(url);await publicPage.frameLocator('iframe').locator('#count').waitFor();assert.equal(await publicPage.frameLocator('iframe').locator('#count').innerText(),'1');await visitor.close();
 await page.getByRole('button',{name:'关闭',exact:true}).first().click();
 // Clone via project cards, including independence from history and data.
 await page.locator('nav').getByRole('button',{name:'项目',exact:false}).click();await page.getByRole('button',{name:'项目操作'}).first().click();await page.getByRole('button',{name:'克隆',exact:true}).click();
 const clone=(await state()).chats.find(c=>c.id!==originalId);assert.equal(clone.messages.length,0);assert.deepEqual(clone.previewData,{});assert.equal(clone.versions.length,1);assert.equal(clone.publication,undefined);
 await page.frameLocator('iframe[title="应用实时预览"]').locator('#count').waitFor();assert.equal(await page.frameLocator('iframe[title="应用实时预览"]').locator('#count').innerText(),'0');
 // Schedule creation, pause, resume, deletion and history retention.
 await page.getByTitle('对话自动化设置').click();await page.getByLabel('任务名称',{exact:true}).fill('定时检查测试');await page.getByLabel('每次运行要检查的内容').fill('检查公开文档并汇报');await page.getByRole('button',{name:'保存任务'}).click();
 await page.locator('nav').getByRole('button',{name:'定时任务',exact:true}).click();await page.getByTitle('暂停',{exact:true}).click();assert.equal((await state()).schedules[0].paused,true);await page.getByTitle('恢复',{exact:true}).click();assert.equal((await state()).schedules[0].paused,false);
 // Trigger due during this page's lifetime, and verify checks cannot create versions.
 const countBefore=(await state()).chats.find(c=>c.id===clone.id).versions.length;
 await page.evaluate(()=>{const key='atmos.workspace.v1',s=JSON.parse(localStorage.getItem(key));s.schedules[0].next=Date.now()-5;localStorage.setItem(key,JSON.stringify(s));window.dispatchEvent(new StorageEvent('storage',{key}))});
 await waitFor(async()=>(await state()).runs.some(r=>r.mode==='check'&&r.status==='succeeded'));
 assert.equal((await state()).chats.find(c=>c.id===clone.id).versions.length,countBefore);
 page.once('dialog',d=>d.accept());await page.getByTitle('删除任务').click();assert.equal((await state()).schedules.length,0);assert.ok((await state()).runs.some(r=>r.mode==='check'));
 // Reload with an overdue task: record missed, do not run in the background.
 const profileId=(await state()).profileId;
 await page.evaluate(({profileId,chatId})=>{const key='atmos.workspace.v1',s=JSON.parse(localStorage.getItem(key));s.schedules.push({id:'missed-test',chatId,name:'错过执行',prompt:'Check',profileId,frequency:'daily',timezone:'Asia/Shanghai',at:'09:00',weekday:0,day:1,month:1,paused:false,next:Date.now()-60000,notifySuccess:true,notifyFailure:true});localStorage.setItem(key,JSON.stringify(s))},{profileId,chatId:clone.id});
 const checksBefore=requests.filter(r=>r.mode==='check').length;await page.reload();await waitFor(async()=>(await state()).runs.some(r=>r.scheduleId==='missed-test'&&r.status==='missed'));assert.equal(requests.filter(r=>r.mode==='check').length,checksBefore);
 page.once('dialog',d=>d.accept('测试文件夹'));await page.getByRole('button',{name:'创建文件夹',exact:true}).click();
 const folderId=(await state()).folders[0].id;
 await page.locator('.recent-list').getByRole('button',{name:'计数器 · 副本',exact:true}).click();
 await page.getByLabel('对话文件夹',{exact:true}).selectOption(folderId);
 await page.locator('.folder-row > button').first().click();
 assert.equal(await page.locator('.folder-chat-title').count(),1);
 await page.getByRole('button',{name:'新建对话',exact:true}).click();assert.equal((await state()).chats[0].folderId,folderId);
 await page.locator('nav').getByRole('button',{name:'首页',exact:true}).click();
 await page.setViewportSize({width:390,height:844});await page.reload();await page.screenshot({path:output+'/mobile.png',fullPage:true});
 assert.equal(errors.length,0,'Browser runtime errors: '+errors.join('; '));
 console.log(JSON.stringify({passed:true,checks:['import','interactive preview','opaque-origin isolation','reload persistence','seeded export','empty export','standalone HTML persistence','generation protocol fixture','version restoration','editable plan confirmation','real publication','public seeded viewer','clone isolation','schedule pause/resume/delete','read-only timed run','missed-run handling','folder move and conversation listing','new conversation in folder','mobile layout'],screenshots:output,realModelCalls:0},null,2));
}finally{await browser.close()}
