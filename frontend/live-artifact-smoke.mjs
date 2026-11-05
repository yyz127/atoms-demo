// Validate actual model-produced HTML; no API key or mocked model response.
// Usage: node live-artifact-smoke.mjs /path/to/generated.html /path/to/iterated.html
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {parse} from 'acorn';
import {exportHtml} from './src/core.ts';

const [initialPath, iterationPath]=process.argv.slice(2);
if(!initialPath||!iterationPath)throw Error('Provide generated and iterated HTML paths');
const initial=await fs.readFile(initialPath,'utf8'),iteration=await fs.readFile(iterationPath,'utf8');
assert.notEqual(initial,iteration,'Iteration must change the HTML');
for(const html of [initial,iteration]){
 assert.ok(!/<script[^>]+src=/i.test(html));
 for(const script of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)){
  if(/type=["']application\/ld\+json/.test(script[1]))continue;
  parse(script[2],{ecmaVersion:'latest',sourceType:/type=["']module/.test(script[1])?'module':'script'});
 }
}
const output='/private/tmp/atmos-live-qa';await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
try{
 const context=await browser.newContext();const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const file=output+'/initial-export.html';
 await fs.writeFile(file,exportHtml({previewData:{}},{html:initial},false));
 await page.goto('file://'+file);
 assert.equal(await page.locator('#task-list li').count(),0);
 await page.locator('#task-input').fill('验证真实模型生成的交互');await page.locator('#add-task').click();
 assert.equal(await page.locator('#task-list li').count(),1);
 await page.locator('#task-list input[type=checkbox]').first().check();await page.reload();
 assert.equal(await page.locator('#task-list li').count(),1);
 assert.equal(await page.locator('#task-list input[type=checkbox]').first().isChecked(),true);
 const data=await page.evaluate(()=>Object.fromEntries(Array.from({length:localStorage.length},(_,i)=>{const k=localStorage.key(i);return[k,localStorage.getItem(k)]})));
 const updated=output+'/iterated-export.html';
 await fs.writeFile(updated,exportHtml({previewData:data},{html:iteration},true));
 await page.goto('file://'+updated);
 assert.match(await page.locator('#iteration-proof').innerText(),/^第二版 · 专注今天。?$/);
 assert.equal(await page.locator('#task-list li').count(),1);
 await page.locator('#clear-completed').click();
 assert.equal(await page.locator('#task-list li').count(),0);
 await page.locator('#task-input').fill('第二版继续保存');await page.locator('#add-task').click();await page.reload();
 assert.equal(await page.locator('#task-list li').count(),1);
 await page.screenshot({path:output+'/live-app.png',fullPage:true});
 assert.deepEqual(errors,[]);
 const result={passed:true,checks:['real HTML syntax','empty initial data','add task','complete task','refresh persistence','actual iteration change','seeded export preserves data','clear completed','iterated app persistence','no browser errors']};
 await fs.writeFile(output+'/browser-report.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await browser.close()}
