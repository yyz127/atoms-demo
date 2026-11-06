import test from 'node:test';
import assert from 'node:assert/strict';
import {cloneChat,newChat,safeJson,type Version} from './src/core.ts';

test('cloning never inherits chats, user data, links or capabilities',()=>{
 const source=newChat('Source');const version:Version={id:'v1',number:4,title:'Selected',html:'<html></html>',status:'ready',created:1};
 source.versions=[version];source.activeId='v1';source.messages=[{id:'secret-chat',role:'user',kind:'text',content:'private',created:1}];source.previewData={private:'records'};source.publication={id:'p1',secret:'owner-token',url:'https://example.test/p/1',versionId:'v1'};
 const clone=cloneChat(source,version);
 assert.equal(clone.versions[0].html,version.html);assert.equal(clone.versions[0].number,1);assert.notEqual(clone.id,source.id);assert.deepEqual(clone.messages,[]);assert.deepEqual(clone.previewData,{});assert.equal(clone.publication,undefined);assert.deepEqual(clone.references,[]);
});
test('data embedded in HTML cannot close the bootstrap script',()=>{
 const value=safeJson({data:'</script><script>alert(1)</script>'});assert.equal(value.includes('<'),false);assert.equal(JSON.parse(value).data,'</script><script>alert(1)</script>');
});
