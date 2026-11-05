import test from 'node:test';
import assert from 'node:assert/strict';
import {nextTime,cloneChat,newChat,safeJson,type Schedule,type Version} from './src/core.ts';

const config:Pick<Schedule,'frequency'|'timezone'|'at'|'weekday'|'day'|'month'>={frequency:'daily',timezone:'UTC',at:'09:30',weekday:0,day:31,month:2};
test('hourly and weekly plans respect local calendar boundaries',()=>{
 assert.equal(new Date(nextTime({...config,frequency:'hourly'},Date.parse('2026-11-05T08:45:00Z'))).toISOString(),'2026-11-05T09:30:00.000Z');
 assert.equal(new Date(nextTime({...config,frequency:'weekly'},Date.parse('2026-11-05T10:00:00Z'))).toISOString(),'2026-11-09T09:30:00.000Z');
});
test('month end clamps without drifting following months',()=>{
 const april=nextTime({...config,frequency:'monthly'},Date.parse('2026-04-01T00:00:00Z'));
 assert.equal(new Date(april).toISOString(),'2026-04-30T09:30:00.000Z');
 assert.equal(new Date(nextTime({...config,frequency:'monthly'},april)).toISOString(),'2026-05-31T09:30:00.000Z');
});
test('leap-day yearly rules and DST gaps are deterministic',()=>{
 assert.equal(new Date(nextTime({...config,frequency:'yearly',day:29},Date.parse('2025-03-01T00:00:00Z'))).toISOString(),'2026-02-28T09:30:00.000Z');
 assert.equal(new Date(nextTime({...config,timezone:'America/New_York',at:'02:30'},Date.parse('2027-03-13T12:00:00Z'))).toISOString(),'2027-03-14T07:30:00.000Z');
});
test('DST repeated local times only use the earlier occurrence',()=>{
 assert.equal(new Date(nextTime({...config,timezone:'America/New_York',at:'01:30'},Date.parse('2026-11-01T05:45:00Z'))).toISOString(),'2026-11-02T06:30:00.000Z');
});
test('cloning never inherits chats, user data, links or capabilities',()=>{
 const source=newChat('Source');const version:Version={id:'v1',number:4,title:'Selected',html:'<html></html>',status:'ready',created:1};
 source.versions=[version];source.activeId='v1';source.messages=[{id:'secret-chat',role:'user',kind:'text',content:'private',created:1}];source.previewData={private:'records'};source.publication={id:'p1',secret:'owner-token',url:'https://example.test/p/1',versionId:'v1'};
 const clone=cloneChat(source,version);
 assert.equal(clone.versions[0].html,version.html);assert.equal(clone.versions[0].number,1);assert.notEqual(clone.id,source.id);assert.deepEqual(clone.messages,[]);assert.deepEqual(clone.previewData,{});assert.equal(clone.publication,undefined);assert.deepEqual(clone.references,[]);
});
test('data embedded in HTML cannot close the bootstrap script',()=>{
 const value=safeJson({data:'</script><script>alert(1)</script>'});assert.equal(value.includes('<'),false);assert.equal(JSON.parse(value).data,'</script><script>alert(1)</script>');
});
