import {highlightScript} from './syntax.js';
import {playground,mountPlayground,stopPlayground} from './playground.js';
import {APP_VERSION} from './version.js';
import {icon,hydrateIcons} from './icons.js';
import {routes,themes,escapeHTML as e,canExport,filterCatalogue,lineSelection,noticeMatches} from './model.js';
import * as views from './views.js';
const $=id=>document.getElementById(id);
const native=Boolean(window.__TAURI__?.core?.invoke);
const state={route:'home',mode:'to',source:'',templates:true,result:null,example:'',catalogue:[],pending:false,busy:false,ready:false,revision:0,importedXML:null,theme:'light',notices:null,review:null};
let compileTimer,toastTimer;
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,7000);$('announcer').textContent=message;}
async function rpc(op,payload={}){if(!native)throw new Error('Design preview only. Open the desktop app to convert scripts or access the native clipboard.');return window.__TAURI__.core.invoke('bridge',{op,payload});}
function report(error){toast(String(error?.message||error));}
function readPreference(){try{return localStorage.getItem('bridge-appearance')||'light';}catch{return 'light';}}
function setTheme(theme){state.theme=themes.includes(theme)?theme:'light';try{localStorage.setItem('bridge-appearance',state.theme);}catch{}const dark=state.theme==='dark'||state.theme==='system'&&matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',dark);$('theme-label').textContent=state.theme[0].toUpperCase()+state.theme.slice(1);}
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{if(state.theme==='system')setTheme('system');});
function route(name){
 stopPlayground();
 if(!routes[name])name='home';state.route=name;
 document.querySelectorAll('#navigation [data-route],.sidebar-bottom [data-route]').forEach(b=>{const active=b.dataset.route===name;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
 $('page-name').textContent=routes[name];$('page').innerHTML=name==='playground'?playground():views[name](state);hydrateIcons($('page'));$('page').scrollTop=0;
 if(name==='workspace'){bindEditor();updateWorkspace();}
 if(name==='playground')mountPlayground({rpc,notify:toast,existingScript:()=>state.source,useDraft:source=>{setSource(source);route('workspace');compile();toast('Generated draft loaded. Review its details before creating the native FileMaker clipboard.');}});
 if(name==='reference'){bindReference();}
 document.querySelectorAll('.paste-shortcut').forEach(el=>el.textContent=navigator.platform.includes('Mac')?'⌘V':'Ctrl+V');
 $('page').focus({preventScroll:true});
}
function setSource(source,{result=null,importedXML=null}={}){
 state.revision++;state.source=source;state.result=result;state.importedXML=importedXML;
 if($('script-editor'))$('script-editor').value=source;
 updateLines();updateWorkspace();
}
function updateLines(){const editor=$('script-editor');if(!editor)return;const count=state.source.split('\n').length;$('line-count').textContent=`${count} ${count===1?'line':'lines'}`;$('line-numbers').textContent=Array.from({length:count},(_,i)=>i+1).join('\n');$('script-highlight').innerHTML=highlightScript(state.source)+' ';syncEditorPaint();}
function syncEditorPaint(){const editor=$('script-editor'),paint=$('script-highlight');if(!editor||!paint)return;paint.style.width=editor.clientWidth+'px';paint.style.height=editor.clientHeight+'px';paint.scrollTop=editor.scrollTop;paint.scrollLeft=editor.scrollLeft;$('line-numbers').scrollTop=editor.scrollTop;}
function bindEditor(){
 const editor=$('script-editor');
 editor.addEventListener('input',()=>{setSource(editor.value);scheduleCompile();});
 editor.addEventListener('scroll',syncEditorPaint);
 const observer=new ResizeObserver(()=>{if(!editor.isConnected){observer.disconnect();return;}syncEditorPaint();});observer.observe(editor);
 editor.addEventListener('keydown',event=>{if(event.key==='Tab'){event.preventDefault();const a=editor.selectionStart,b=editor.selectionEnd;editor.setRangeText('    ',a,b,'end');editor.dispatchEvent(new Event('input'));}});
 $('templates').addEventListener('change',event=>{state.templates=event.target.checked;state.result=null;state.revision++;scheduleCompile();});updateLines();
}
function scheduleCompile(){clearTimeout(compileTimer);state.pending=true;updateWorkspace();compileTimer=setTimeout(()=>compile().catch(report),240);}
async function compile(){
 clearTimeout(compileTimer);const revision=state.revision,source=state.source,templates=state.templates;state.pending=true;updateWorkspace();
 try{const result=await rpc('compile',{source,templates});if(revision!==state.revision)return;state.result=result;}
 catch(error){if(revision===state.revision){state.result=null;report(error);}}
 finally{if(revision===state.revision){state.pending=false;updateWorkspace();}}
}
function updateWorkspace(){
 if(state.route!=='workspace'||!$('stats'))return;
 const r=state.result,pending=state.pending||state.busy,canCopy=state.ready&&canExport(r,state.source,pending);
 const issues=r?.errorCount||r?.reviewOnlyCount;
 const hasSource=state.source.trim().length>0;
 $('stats').innerHTML=[['Native',r?.supportedCount??'—'],['Templates',r?.templateCount??'—'],['Preserved',r?.preservedCount??'—']].map(([label,value])=>`<div><strong>${value}</strong><span>${label}</span></div>`).join('');
 const badge=$('validation-tag');badge.className='tag';
 let title='Start with a script.',description='Your script is checked as you edit. All conversion stays on this computer.';
 if(pending){badge.textContent='Checking…';title='Checking your script…';description='Reviewing the supported syntax and native options.';}
 else if(r&&hasSource){if(issues){badge.textContent='Needs attention';badge.classList.add('error');title='A few details need your attention.';description='Resolve blocking issues before creating the FileMaker clipboard.';}else if(r.warningCount||r.preservedCount){badge.textContent='Review';badge.classList.add('warning');title='Ready, with details to review.';description='Check the warnings and finish any TODO steps in FileMaker.';}else{badge.textContent='Validated';badge.classList.add('success');title='The supported syntax looks good.';description='Review the script logic in FileMaker before using it.';}}
 else badge.textContent='Waiting';
 $('validation-summary').innerHTML=`<div>${icon(issues?'warning':r&&hasSource?'check':'shield')}${e(title)}</div><p>${e(description)}</p>`;
 $('issues').innerHTML=views.issueRows(r);
 $('secondary-action').disabled=!canCopy;
 $('copy-native-help').textContent=canCopy?'Paste in Script Workspace':pending?'Checking your script…':'Validate a script to enable';
 $('secondary-action').title=canCopy?'Copy native steps, then paste them into FileMaker Script Workspace.':'Paste or load a script and resolve blocking issues to enable copying.';
 $('primary-action').disabled=state.busy||!state.ready;
 $('secondary-action').hidden=state.mode==='from';
 $('primary-action').classList.toggle('primary',state.mode==='from');
 $('primary-action').innerHTML=`${icon('clipboard')}${state.mode==='to'?'Paste AI draft & copy':'Read FileMaker clipboard'}`;
 $('workflow-hint').textContent=state.mode==='to'?'Readable draft → reviewed native steps':'Copied native steps → readable text';
 $('action-title').textContent=pending?'Checking the latest changes…':issues?'Resolve the blocking issues.':canCopy?'Your script is ready to copy.':'Ready when you are.';
 $('action-help').textContent=state.mode==='to'?'Copy to FileMaker, then switch to Script Workspace and paste.':"Copy native steps in FileMaker first. We'll copy the readable text for you.";
 document.querySelectorAll('[data-action="smart-fix"],[data-action="xml"]').forEach(b=>b.disabled=state.busy||!state.ready||!hasSource);
 document.querySelectorAll('[data-action="example"],[data-action="clear"],#templates').forEach(b=>b.disabled=state.busy||!state.ready);
 $('script-editor').readOnly=state.busy||!state.ready;
}
async function busy(action){if(state.busy)return;clearTimeout(compileTimer);state.busy=true;state.pending=false;updateWorkspace();try{await action();}catch(error){report(error);}finally{state.busy=false;updateWorkspace();}}
async function primary(){await busy(async()=>{
 if(state.mode==='from'){
  const r=await rpc('import',{templates:state.templates});setSource(r.source,{result:r,importedXML:r.importedXML});
  toast(r.textCopied?'Readable text copied. Paste it into your editor or AI tool.':`Script imported. ${r.clipboardError} Use Copy text to try again.`);
 }else{
  const {text}=await rpc('pasteText');if(!text?.trim())throw new Error('Copy readable script text first.');
  setSource(text);const r=await rpc('compile',{source:text,templates:state.templates});state.result=r;
  if(!r.canCopy){toast('Draft pasted. Resolve the blocking issues before creating the FileMaker clipboard.');return;}
  await rpc('copyNative',{source:text,templates:state.templates});toast(`Native FileMaker clipboard created. Choose the insertion point in Script Workspace and press ${navigator.platform.includes('Mac')?'⌘V':'Ctrl+V'}.`);
 }
});}
async function copyNative(){await busy(async()=>{const r=await rpc('copyNative',{source:state.source,templates:state.templates});state.result=r;toast('Native FileMaker clipboard updated. Paste into Script Workspace.');});}
function bindReference(){const update=()=>{
 const rows=filterCatalogue(state.catalogue,$('reference-search').value,$('reference-filter').value);
 $('reference-count').textContent=`${rows.length} steps`;
 $('reference-list').innerHTML=rows.map(row=>`<div class="reference-row"><div><a href="${e(row.url)}" target="_blank" rel="noreferrer">${e(row.name)}${icon('external')}</a><small>${e(row.category)}</small></div><span class="tag ${row.support==='editableSubset'?'teal':''}">${row.support==='editableSubset'?'Editable subset':'Completion template'}</span></div>`).join('')||'<p class="muted">No matching steps.</p>';
 };$('reference-search').addEventListener('input',update);$('reference-filter').addEventListener('change',update);update();}
let focusBeforeDrawer;
function openDrawer(title,body,footer=''){
 focusBeforeDrawer=document.activeElement;$('drawer-title').textContent=title;$('drawer-body').innerHTML=body;$('drawer-footer').innerHTML=footer;hydrateIcons($('drawer'));
 if(!$('drawer').open)$('drawer').showModal();$('close-drawer').focus();
}
$('close-drawer').addEventListener('click',()=>$('drawer').close());
$('drawer').addEventListener('close',()=>{state.review=null;if(focusBeforeDrawer?.isConnected)focusBeforeDrawer.focus();});
function xml(){if(!state.result)return;openDrawer(state.importedXML?'Original FileMaker XML':'Compiled clipboard XML',`<div class="xml-note">Raw XML is for inspection. Copying it as text does not create native script steps. ${state.importedXML?'This is the original imported XML.':'This is the current compiled output.'}</div><pre>${e(state.importedXML||state.result.xml)}</pre>`,`<button data-action="copy-xml">${icon('clipboard')} Copy XML as text</button>`);}
async function smartFix(){await busy(async()=>{
 const r=await rpc('review',{source:state.source});state.review=r;
 const items=r.items.map((item,index)=>`<article class="fix-item" data-fix-index="${index}"><div class="fix-title"><strong>Line ${item.line}${item.endLine!==item.line?'–'+item.endLine:''}</strong><select class="fix-action" aria-label="Action for line ${item.line}"><option value="keep">Keep for later</option><option value="replace">Use replacement</option>${item.questions.length?'<option value="answers">Use my answers</option>':''}<option value="omit">Omit step</option></select></div><pre>${e(item.original)}</pre><p>${e(item.reason)}</p><label>Replacement<textarea class="fix-replacement" spellcheck="false">${e(item.replacement)}</textarea></label>${item.questions.map(q=>`<label>${e(q.prompt)}${q.choices.length?`<select data-answer="${e(q.key)}"><option value="">Choose an answer…</option>${q.choices.map(c=>`<option value="${e(c)}">${e(c)}</option>`).join('')}</select>`:`<input data-answer="${e(q.key)}" type="text" autocomplete="off">`}</label>`).join('')}</article>`).join('');
 openDrawer('Review Smart Fix',`<p>Choose each repair explicitly. Replacements must compile as native steps. Omissions leave a comment with the original text. Applying changes does not update the clipboard.</p>${items||'<div class="empty-review good">'+icon('check')+'<strong>No fixes to review.</strong><p>Your supported syntax has no suggested repairs.</p></div>'}`,r.items.length?'<button data-action="suggested">Select suggested fixes</button><button class="primary" data-action="apply-fixes">Apply reviewed changes</button>':'');
});}
async function applyFixes(){
 const review=state.review;if(!review)return;
 const choices=[...$('drawer-body').querySelectorAll('[data-fix-index]')].map(el=>{const item=review.items[Number(el.dataset.fixIndex)];return {line:item.line,action:el.querySelector('.fix-action').value,replacement:el.querySelector('.fix-replacement').value,answers:Object.fromEntries([...el.querySelectorAll('[data-answer]')].map(input=>[input.dataset.answer,input.value]))};});
 const button=$('drawer-footer').querySelector('[data-action="apply-fixes"]');button.disabled=true;
 try{const r=await rpc('applyFixes',{source:state.source,templates:state.templates,choices});setSource(r.source,{result:r});$('drawer').close();toast('Smart Fix applied. Review the result, then update the FileMaker clipboard.');}catch(error){report(error);}finally{button.disabled=false;}
}
async function licences(){
 openDrawer('Licences & acknowledgements','<p>Loading the bundled licence inventory…</p>');
 try{
  if(!state.notices){const [gpl,notices]=await Promise.all([fetch('assets/application-LICENSE.txt').then(r=>{if(!r.ok)throw Error('Application licence is missing.');return r.text();}),fetch('assets/notices.json').then(r=>{if(!r.ok)throw Error('Component notices are missing. Rebuild the desktop package.');return r.json();})]);state.notices={gpl,entries:notices.entries};}
  if(!$('drawer').open)return;
  $('drawer-body').innerHTML=`<div class="licence-intro"><h3>Free software. Clear attribution.</h3><p>FileMaker Script Bridge is licensed under GPL version 3 or later. Third-party components retain their own licences. Optional Qwen models use Apache-2.0, and the bundled llama.cpp engine uses MIT. Their terms and third-party notices remain separate from the application licence. This software is supplied without warranty; read the complete terms below.</p></div><div class="notice-tabs"><button class="active" data-notice-tab="app">Application licence</button><button data-notice-tab="components">App components</button><button data-notice-tab="ai">AI models & runtime</button></div><section id="licence-content"></section>`;
  licenceTab('app');
 }catch(error){$('drawer-body').textContent=String(error.message||error);}
}
function licenceTab(tab){
 document.querySelectorAll('[data-notice-tab]').forEach(b=>b.classList.toggle('active',b.dataset.noticeTab===tab));
 if(tab==='app'){$('licence-content').innerHTML=`<p class="muted">Copyright © 2026 SCKC · SPDX: GPL-3.0-or-later</p><br><pre>${e(state.notices.gpl)}</pre>`;return;}
 const entries=state.notices.entries.filter(row=>tab==='ai'?['model','runtime','runtime-component'].includes(row.kind):!row.kind||['platform-runtime','frontend-library'].includes(row.kind));
 $('licence-content').innerHTML=`<p class="muted">${tab==='ai'?'The inference engine is bundled. Qwen 9B and 35B model weights are optional downloads from pinned Unsloth conversions of Qwen’s original models. Expected checksums identify the chosen files; they do not imply endorsement or guarantee output quality. Read the full model and component terms below.':'Application dependencies, build tools and platform runtimes. Each entry retains its original licence and recorded source.'}</p><br><label class="search-field notice-search">${icon('search')}<input id="notice-search" type="search" placeholder="Search name, version or licence" aria-label="Search component licences"></label><div id="notice-list"></div>`;
 const update=()=>{$('notice-list').innerHTML=entries.filter(row=>noticeMatches(row,$('notice-search').value)).map(row=>`<details class="notice-entry"><summary><strong>${e(row.name)}</strong> <span>${e(row.version)} · ${e(row.license)}</span></summary><pre>${e(row.text)}</pre>${row.repository?`<a href="${e(row.repository)}" target="_blank" rel="noreferrer">Original component source ↗</a>`:''}</details>`).join('')||'<p class="muted">No matching components.</p>';};$('notice-search').addEventListener('input',update);update();
}
document.addEventListener('click',async event=>{
 if(event.target.closest('.brand')){event.preventDefault();route('home');return;}
 const anchor=event.target.closest('a[href^="https://"]');if(anchor&&native){event.preventDefault();try{await rpc('openLink',{url:anchor.href});}catch(error){report(error);}return;}
 const routeButton=event.target.closest('[data-route]');if(routeButton){route(routeButton.dataset.route);return;}
 const modeButton=event.target.closest('[data-mode]');if(modeButton){state.mode=modeButton.dataset.mode;route('workspace');return;}
 const lineButton=event.target.closest('[data-line]');if(lineButton){const editor=$('script-editor');const [start,end]=lineSelection(state.source,lineButton.dataset.line);editor.focus();editor.setSelectionRange(start,end);editor.scrollTop=Math.max(0,(Number(lineButton.dataset.line)-3)*22.8);$('line-numbers').scrollTop=editor.scrollTop;return;}
 const tab=event.target.closest('[data-notice-tab]');if(tab){licenceTab(tab.dataset.noticeTab);return;}
 const action=event.target.closest('[data-action]')?.dataset.action;
 try{switch(action){
  case 'start':state.mode='to';route('workspace');break;
  case 'review-mode':state.mode='from';route('workspace');break;
  case 'primary':await primary();break;
  case 'copy-native':await copyNative();break;
  case 'copy-readable':await rpc('copyText',{text:state.source});toast('Readable script text copied.');break;
  case 'copy-xml':await rpc('copyText',{text:state.importedXML||state.result?.xml||''});toast('XML copied as plain text for inspection.');break;
  case 'example':setSource(state.example);await compile();break;
  case 'clear':await busy(async()=>{const r=await rpc('reset',{templates:state.templates});setSource('',{result:r});});break;
  case 'inspect':{const r=await rpc('inspect');openDrawer('Clipboard formats',`<p>Clipboard metadata on this computer. No clipboard content is shown here.</p><pre>${e(r.types.join('\n')||'The clipboard is empty.')}</pre>`);break;}
  case 'xml':xml();break;
  case 'smart-fix':await smartFix();break;
  case 'apply-fixes':await applyFixes();break;
  case 'suggested':$('drawer-body').querySelectorAll('[data-fix-index]').forEach(el=>{if(state.review.items[Number(el.dataset.fixIndex)].suggestion)el.querySelector('.fix-action').value='replace';});break;
  case 'licences':await licences();break;
 }}catch(error){report(error);}
});
$('help').addEventListener('click',()=>route('guide'));
$('appearance').addEventListener('click',()=>setTheme(themes[(themes.indexOf(state.theme)+1)%themes.length]));
window.addEventListener('hashchange',()=>{if(location.hash==='#home')route('home');});
$('app-version').textContent=`DESKTOP · ${APP_VERSION}`;
setTheme(readPreference());hydrateIcons();route('home');
async function start(){
 if(!native){const banner=document.createElement('div');banner.className='preview-banner';banner.textContent='Design preview · Open the desktop app for local conversion and native clipboard access.';$('page').before(banner);$('engine-state').innerHTML='<span class="status-dot waiting"></span>Design preview · Desktop engine disconnected';
  try{state.catalogue=await fetch('assets/catalogue.json').then(r=>r.json());}catch{}return;}
 try{const hello=await rpc('hello');state.ready=true;state.catalogue=hello.catalogue;state.example=hello.example;
  $('engine-state').innerHTML=`<span class="status-dot"></span>Local engine ready · ${navigator.platform.includes('Mac')?'macOS':'Windows'} · Swift + Rust`;
  if(state.route==='reference')bindReference();updateWorkspace();
 }catch(error){$('engine-state').innerHTML='<span class="status-dot waiting"></span>Conversion engine unavailable';report(error);}
}
start();
