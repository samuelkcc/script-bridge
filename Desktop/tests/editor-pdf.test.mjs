import test from 'node:test';
import assert from 'node:assert/strict';
import {highlightScript} from '../web/syntax.js';
import {pageText,readPdf} from '../web/pdf.js';

const unpaint=html=>html.replace(/<[^>]+>/g,'').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
test('syntax colours preserve a large script and escape all user markup',()=>{
 const source=Array.from({length:509},(_,i)=>`Set Variable [ $value${i} ; Value: "<img src=x> # On $notAVariable" & ¶ & Orders::Total ]`).join('\n')+'\n';
 const html=highlightScript(source);
 assert.equal(unpaint(html),source);
 for(const type of ['step','variable','string','field','punctuation'])assert.ok(html.includes(`syntax-${type}`),type);
 assert.ok(!html.includes('<img'));
 assert.ok(!html.includes('syntax-comment'));
});
test('comments, strings and unicode remain separate from executable tokens',()=>{
 const source='# Set Variable $ignored\nSet Variable [ $$變數 ; Value: "Line 1\nLine 2 \\"quoted\\"" ]\nIf [ Get ( LastError ) ≠ 0 ]\nEnd If';
 const html=highlightScript(source);
 assert.equal(unpaint(html),source);
 assert.match(html,/<span class="syntax-comment"># Set Variable \$ignored<\/span>/);
 assert.match(html,/syntax-variable">\$\$變數/);
 assert.match(html,/syntax-function">Get/);
});
test('printed PDF fragments keep order, indentation, wrapped lines and literal text',()=>{
 const item=(str,x,y,width=10)=>({str,transform:[1,0,0,1,x,y],width,height:10});
 assert.equal(pageText([item('"<html> & ¶" ]',40,80),item('Set Variable',10,100,50),item('[ $x ; Value:',62,100,60),item('Exit Script',10,60,50)]), 'Set Variable [ $x ; Value:\n    "<html> & ¶" ]\nExit Script');
 assert.equal(pageText([]),'');
});
test('PDF picker rejects unsupported, empty and oversized attachments before parsing',async()=>{
 await assert.rejects(readPdf({name:'script.txt',size:10}),/Choose a PDF/);
 await assert.rejects(readPdf({name:'script.pdf',size:0}),/empty/);
 await assert.rejects(readPdf({name:'script.pdf',size:16*1024*1024}),/15 MB/);
 await assert.rejects(readPdf({name:'script.pdf',size:8,arrayBuffer:async()=>new TextEncoder().encode('not pdf!').buffer}),/not a readable PDF/);
});
