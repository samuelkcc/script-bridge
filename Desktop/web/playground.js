import {icon} from './icons.js';
import {escapeHTML as e} from './model.js';
const $=id=>document.getElementById(id);
const state={question:'',schema:'',includeExisting:false,selected:'9b',status:null,draft:'',complete:false,validation:null,sections:[],error:'',submitting:false};
let api=null,timer=null,refreshing=false;
try{state.selected=localStorage.getItem('bridge-ai-model')||'9b';}catch{}
if(!['9b','35b'].includes(state.selected))state.selected='9b';
const size=n=>n>=1e9?`${(n/1e9).toFixed(2)} GB`:`${(n/1e6).toFixed(0)} MB`;
export function playground(){return `<section class="playground-page"><div class="page-heading"><div><span class="eyebrow">FROM A QUESTION TO A REVIEWABLE SCRIPT</span><h1>Your FileMaker playground.</h1><p>Ask Qwen to draft a script, then review the result in your workspace.</p></div><button data-route="workspace">${icon('clipboard')} Paste from another AI</button></div><div class="playground-grid"><div class="playground-main"><article class="card prompt-card"><div class="prompt-title"><h2>${icon('sparkle')} What would you like to build?</h2><span class="tag">QWEN · ON DEVICE</span></div><label class="ai-field">Your question<textarea id="ai-question" spellcheck="true" placeholder="For each order in the current found set, mark orders over £1,000 as needing approval. Show a summary when finished.">${e(state.question)}</textarea></label><div class="prompt-examples"><button data-ai-example="draft">Draft an approval script</button><button data-ai-example="explain">Review my existing script</button><button data-ai-example="export">Export records to Excel</button></div><details class="schema-context" ${state.schema?'open':''}><summary>Database names & requirements <span>Optional, but helps avoid invented fields</span></summary><label class="ai-field">Tables, fields, layouts and script names<textarea id="ai-schema" spellcheck="false" placeholder="Orders::Total — number\nOrders::Status — text\nOrders::OrderID — unique ID\nLayout: Order List\nKeep the current found set and sort order.">${e(state.schema)}</textarea></label></details><label class="include-script"><input id="ai-include-existing" type="checkbox" ${state.includeExisting?'checked':''}><span>Include the current workspace script<small>Only the script you choose is supplied. The app does not read your FileMaker database.</small></span></label><div class="prompt-actions"><span id="ai-prompt-hint" class="muted">Choose and download a model to start.</span><button id="ai-generate" class="primary">${icon('sparkle')} Generate script</button></div></article><article class="card draft-card"><div class="prompt-title"><div><h2>Generated draft</h2><p id="ai-draft-status" class="muted">Your draft will appear here.</p></div><span id="ai-draft-badge" class="tag">Awaiting a question</span></div><div id="ai-empty" class="ai-empty">${icon('code')}<strong>A useful starting point, ready for your review.</strong><p>The model uses the bridge’s syntax guide and step reference. Supply your actual database names for a more specific draft.</p></div><textarea id="ai-output" readonly spellcheck="false" aria-label="Generated FileMaker script" hidden></textarea><div id="ai-validation" class="ai-validation" hidden></div><div class="draft-actions"><button id="ai-copy" disabled>${icon('clipboard')} Copy draft text</button><button id="ai-use" class="primary" disabled>Review in workspace ${icon('arrow')}</button></div></article></div><aside class="ai-sidebar"><article class="card model-panel"><div class="prompt-title"><h2>Choose your model</h2><span class="tag">4-BIT</span></div><p class="model-intro">Select a model to download it automatically. Keep both, or remove downloads to free disk space.</p><label class="ai-field model-picker">Select model (auto-download)<select id="ai-model-select" aria-label="Select model, automatically download if needed"><option value="">Choose a model…</option></select></label><div id="ai-models"><p class="muted">Checking model availability…</p></div><div id="ai-operation" class="ai-operation" hidden></div><button id="ai-cancel" class="ai-cancel" hidden>Cancel operation</button><div class="model-resources" id="ai-resources"></div><button id="ai-unload" class="small quiet" hidden>${icon('moon')} Release model from memory</button></article><article class="card knowledge-panel"><span class="eyebrow">A REFERENCE, BUILT INTO THE QUESTION</span><h3>FileMaker-aware guidance</h3><p>Generation includes the bridge’s supported syntax, editable step list and relevant examples. Your question selects the most useful sections.</p><div class="knowledge-stats"><span><strong>216</strong> referenced steps</span><span><strong>98</strong> editable subsets</span></div><div id="ai-knowledge" class="knowledge-sections"></div><p class="knowledge-note">The validator checks each draft and can request one repair. It cannot verify your database schema or business logic.</p><button class="small quiet" data-route="reference">Explore the step reference ${icon('arrow')}</button></article><p class="model-license">Qwen models: Apache-2.0 · llama.cpp: MIT<br>Model conversions: Unsloth. <button class="text-button" data-action="licences">View full notices</button></p></aside></div></section>`;}
export function stopPlayground(){clearInterval(timer);timer=null;}
export function mountPlayground(options){
 api=options;stopPlayground();
 $('ai-question').addEventListener('input',ev=>state.question=ev.target.value);
 $('ai-schema').addEventListener('input',ev=>state.schema=ev.target.value);
 $('ai-include-existing').addEventListener('change',ev=>state.includeExisting=ev.target.checked);
 $('ai-generate').addEventListener('click',generate);
 $('ai-cancel').addEventListener('click',()=>action('ai_cancel'));
 $('ai-unload').addEventListener('click',()=>action('ai_unload'));
 $('ai-copy').addEventListener('click',async()=>{try{await api.rpc('copyText',{text:state.draft});api.notify('Generated draft copied as readable text.');}catch(err){api.notify(String(err));}});
 $('ai-use').addEventListener('click',()=>{if(state.complete&&!state.status?.busy)api.useDraft(state.draft);});
 $('page').querySelectorAll('[data-ai-example]').forEach(button=>button.addEventListener('click',()=>{
  const examples={draft:'Loop through the current found set of orders. If Orders::Total is over 1000, set Orders::Status to "Needs approval". Otherwise set it to "Approved". Show a count of the orders that need approval.',explain:'Review the included workspace script. Return a revised script that preserves its intent and locked steps. Add # comments explaining any changes or assumptions.',export:'Export the current found set to an XLSX file using $exportPath. Export Orders::OrderID, Orders::Total and Orders::Status, with field names as column headings and a worksheet named "Orders".'};
  state.question=examples[button.dataset.aiExample];$('ai-question').value=state.question;
  if(button.dataset.aiExample==='explain'){state.includeExisting=true;$('ai-include-existing').checked=true;}
 }));
 const chooseModel=async event=>{
  if(!event.target.value||state.submitting||state.status?.busy)return;
  state.selected=event.target.value;try{localStorage.setItem('bridge-ai-model',state.selected);}catch{}
  const chosen=state.status?.models.find(m=>m.id===state.selected);
  if(chosen&&!chosen.installed)await action('ai_download',{model:state.selected});else renderStatus();
 };
 $('ai-model-select').addEventListener('change',chooseModel);
 $('ai-models').addEventListener('click',async event=>{
  const remove=event.target.closest('[data-remove-model]');if(remove&&!state.status?.busy)await action('ai_remove',{model:remove.dataset.removeModel});
 });
 renderStatus();refresh();timer=setInterval(refresh,700);
}
async function refresh(){if(!$('ai-models')||refreshing)return;refreshing=true;try{const latest=await api.rpc('ai_status');if((latest.revision||0)<(state.status?.revision||0))return;state.status=latest;state.error='';const operation=state.status.operation||{};
 if(typeof operation.script==='string'){state.draft=operation.script;state.sections=operation.sections||state.sections;}
 if(operation.phase==='complete'&&operation.validation){state.complete=true;state.validation=operation.validation;}
 renderStatus();
 }catch(error){state.error=String(error?.message||error);renderStatus();}finally{refreshing=false;}}
async function action(op,payload={}){if(state.submitting)return;state.submitting=true;renderStatus();try{state.status=await api.rpc(op,payload);state.error='';}catch(error){state.error=String(error?.message||error);api.notify(state.error);}finally{state.submitting=false;renderStatus();}}
async function generate(){
 if(!state.question.trim()){api.notify('Enter a question for the model first.');$('ai-question').focus();return;}
 if(state.submitting||state.status?.busy)return;
 state.submitting=true;state.error='';renderStatus();
 try{
  const status=await api.rpc('ai_generate',{model:state.selected,question:state.question,schema:state.schema,existing:state.includeExisting?api.existingScript():''});
  state.status=status;state.draft='';state.validation=null;state.complete=false;state.sections=[];
 }catch(error){state.error=String(error?.message||error);api.notify(state.error);}finally{state.submitting=false;renderStatus();}
}
function renderStatus(){
 if(!$('ai-models'))return;
 const status=state.status,busy=Boolean(status?.busy||state.submitting),op=status?.operation||{},models=status?.models||[];
 const selected=models.find(m=>m.id===state.selected);
 const picker=$('ai-model-select');
 const options='<option value="">Choose a model…</option>'+models.map(m=>`<option value="${e(m.id)}">${e(m.name)} — ${m.installed?'downloaded':`${m.partialBytes?'resume':'auto-download'} (${size(m.bytes)})`}</option>`).join('');
 if(picker.dataset.options!==options){picker.innerHTML=options;picker.dataset.options=options;}
 picker.disabled=busy||!models.length;
 // A status poll must not reset an open native picker before WebKit commits
 // its change event. Reset missing selections only when the picker loses focus.
 if(document.activeElement!==picker)picker.value=selected?.installed||(busy&&op.model===state.selected)?state.selected:'';
 const markup=models.map(m=>`<article class="model-choice ${state.selected===m.id&&(m.installed||(busy&&op.model===m.id))?'selected':''}"><div class="model-summary"><strong>${e(m.name)}</strong><small>${m.id==='9b'?'A smaller download and memory footprint.':'A larger model for computers with more memory.'}</small></div><div class="model-details"><span>${size(m.bytes)} download</span><span>${m.recommendedRAMGB} GB RAM recommended</span></div><div class="model-choice-footer"><span class="tag ${m.installed?'teal':''}">${m.installed?'Downloaded & verified':m.partialBytes?'Partial download':'Not downloaded'}</span>${m.hasFiles?`<button class="small remove-model" data-remove-model="${e(m.id)}" aria-label="Remove ${e(m.name)} ${m.installed?'downloaded model':'download files'}" ${busy?'disabled':''}>${m.installed?'Remove model':'Remove download'}</button>`:''}</div>${status.systemMemoryGB&&status.systemMemoryGB<m.recommendedRAMGB?`<p class="memory-warning">This computer has ${Math.round(status.systemMemoryGB)} GB RAM. Use a smaller model for more headroom.</p>`:''}</article>`).join('');
 if($('ai-models').innerHTML!==markup)$('ai-models').innerHTML=markup||`<p class="muted">${e(state.error||'Checking available models…')}</p>`;
 $('ai-generate').disabled=busy||!selected?.installed||!status?.runtimeReady;
 $('ai-question').readOnly=busy;$('ai-schema').readOnly=busy;$('ai-include-existing').disabled=busy;
 $('ai-prompt-hint').textContent=selected?.installed?`Using ${selected.name}. Your draft will be validated.`:'Select a model above. Its download starts automatically.';
 const operation=$('ai-operation');operation.hidden=!state.error&&!op.message;
 const total=op.total||0,received=op.received||0,percent=total?Math.min(100,100*received/total):0;
 operation.classList.toggle('has-error',Boolean(state.error||op.phase==='error'));
 operation.innerHTML=`<strong>${e(state.error||op.message||'')}</strong>${total&&busy?`<progress max="100" value="${percent}"></progress><span>${size(received)} / ${size(total)} · ${Math.floor(percent)}%</span>`:''}`;
 $('ai-cancel').hidden=!status?.busy;$('ai-cancel').disabled=state.submitting;
 $('ai-unload').hidden=!status?.loadedModel;$('ai-unload').disabled=busy;
 $('ai-resources').textContent=status?`${status.systemMemoryGB?Math.round(status.systemMemoryGB)+' GB system memory · ':''}${typeof status.freeDiskBytes==='number'?size(status.freeDiskBytes)+' free disk · ':''}llama.cpp ${status.runtimeVersion}`:'';
 if(status&&!status.runtimeReady)$('ai-resources').textContent+=' · AI runtime missing from this package';
 $('ai-empty').hidden=Boolean(state.draft);$('ai-output').hidden=!state.draft;
 const output=$('ai-output');if(output.value!==state.draft){const nearEnd=output.scrollTop+output.clientHeight>=output.scrollHeight-40;output.value=state.draft;if(nearEnd)output.scrollTop=output.scrollHeight;}
 $('ai-use').disabled=busy||!state.complete||!state.draft;$('ai-copy').disabled=busy||!state.draft;
 $('ai-draft-status').textContent=busy?op.message||'Working…':state.complete?'Review the draft before sending it to FileMaker.':state.draft?'Generation did not complete. Try the question again.':'Your draft will appear here.';
 const validation=state.validation;$('ai-draft-badge').textContent=busy?'Working…':state.complete?(validation?.errorCount?'Needs review':'Draft ready'):'Awaiting a question';
 $('ai-draft-badge').className='tag '+(state.complete?(validation?.errorCount?'warning':'teal'):'');
 $('ai-validation').hidden=!validation||busy;
 $('ai-validation').innerHTML=validation?`${icon(validation.errorCount?'warning':'check')}<span>${validation.errorCount?`${validation.errorCount} blocking syntax issues. Revise the draft in the workspace.`:`${validation.stepCount} compiled steps. The supported syntax passes validation.`}</span>`:'';
 $('ai-knowledge').innerHTML=state.sections.map(s=>`<span>${e(s)}</span>`).join('');
}
