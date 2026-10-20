import test from 'node:test';
import assert from 'node:assert/strict';
import {canExport,filterCatalogue,lineSelection,escapeHTML,noticeMatches} from '../web/model.js';
test('native export cannot use a stale result or bypass pending validation',()=>{
 const r={source:'Set Variable [ $x ; Value: 1 ]',canCopy:true};
 assert.equal(canExport(r,r.source,false),true);
 assert.equal(canExport(r,r.source+'\nUnknown step',false),false);
 assert.equal(canExport(r,r.source,true),false);
 assert.equal(canExport({...r,canCopy:false},r.source,false),false);
});
test('reference filters match support boundaries as well as categories',()=>{
 const rows=[{name:'If',category:'Control',support:'editableSubset'},{name:'Commit Transaction',category:'Control',support:'preserveOnly'}];
 assert.equal(filterCatalogue(rows,'control','editableSubset').length,1);
 assert.equal(filterCatalogue(rows,'TRANSACTION')[0].support,'preserveOnly');
});
test('diagnostic navigation uses UTF-16 offsets for non-ASCII scripts',()=>{
 const source='# 🎵 廣東話\nSet Variable [ $x ; Value: 1 ]';
 const [a,b]=lineSelection(source,2);assert.equal(source.slice(a,b),'Set Variable [ $x ; Value: 1 ]');
});
test('script and licence text cannot inject markup',()=>{
 assert.equal(escapeHTML('<script>"&'), '&lt;script&gt;&quot;&amp;');
 assert.equal(noticeMatches({name:'tauri',version:'2.12.4',license:'MIT OR Apache-2.0'},'apache'),true);
});
