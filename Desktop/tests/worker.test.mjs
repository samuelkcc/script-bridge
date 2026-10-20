import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {resolve} from 'node:path';
import {existsSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
const path=process.env.BRIDGE_TEST_WORKER||resolve(import.meta.dirname,'../../.build/desktop-worker/debug/FileMakerBridgeWorker'+(process.platform==='win32'?'.exe':''));
function session(){
 const child=spawn(path,[],{stdio:['pipe','pipe','inherit']});
 const lines=createInterface({input:child.stdout})[Symbol.asyncIterator]();
 return {close:()=>child.kill(),async call(op,params={}){child.stdin.write(JSON.stringify({op,...params})+'\n');const line=await lines.next();assert.equal(line.done,false,'worker unexpectedly exited');return JSON.parse(line.value);}};
}
test('worker IPC preserves native coverage, locked steps and review safety',{timeout:15000},async t=>{
 assert.ok(existsSync(path),`Build the worker first, or set BRIDGE_TEST_WORKER: ${path}`);
 const worker=session();t.after(()=>worker.close());
 const hello=await worker.call('hello');assert.equal(hello.result.protocol,1);assert.equal(hello.result.catalogue.length,216);
 const example=await worker.call('compile',{source:hello.result.example});assert.equal(example.ok,true);assert.equal(example.result.canCopy,true);
 const strict=await worker.call('compile',{source:'Configure NFC Reading [ ]',templates:false});assert.equal(strict.result.canCopy,false);
 const template=await worker.call('compile',{source:'Configure NFC Reading [ ]',templates:true});assert.ok(template.result.templateCount>0);assert.match(template.result.xml,/TODO/);
 const imported=await worker.call('decompile',{xml:'<fmxmlsnippet type="FMObjectList"><Step enable="True" id="9876" name="Future Native Step"><Options><Keep>廣東話 &amp; 🎵</Keep></Options></Step></fmxmlsnippet>'});
 assert.equal(imported.ok,true);assert.equal(imported.result.preservedCount,1);
 const back=await worker.call('compile',{source:imported.result.source});assert.equal(back.result.preservedCount,1);assert.match(back.result.xml,/Future Native Step/);assert.match(back.result.xml,/<Keep>廣東話 &amp; 🎵<\/Keep>/);
 await worker.call('reset');
 const lost=await worker.call('compile',{source:imported.result.source});assert.equal(lost.result.canCopy,false);
 const source='Show Custom Dialog [ Message: "Hello" ]';
 const review=await worker.call('review',{source});assert.ok(review.result.items[0].suggestion);
 const stale=await worker.call('applyFixes',{source:source+'\n# changed',choices:[]});assert.equal(stale.ok,false);assert.match(stale.error,/changed/);
 const applied=await worker.call('applyFixes',{source,choices:[{line:1,action:'replace',replacement:review.result.items[0].suggestion}]});assert.equal(applied.ok,true);assert.match(applied.result.source,/Commit: No/);
 const malformed=await worker.call('decompile',{xml:'<not-filemaker>'});assert.equal(malformed.ok,false);
 const alive=await worker.call('hello');assert.equal(alive.ok,true);
});
