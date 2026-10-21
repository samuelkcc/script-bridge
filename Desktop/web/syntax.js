import {escapeHTML} from './model.js';

// A paint layer only: the accessible textarea remains the source of truth.
// Scan strings/comments first so code-like text inside them keeps its colour.
const tokens=/(#[^\n]*|\/\/[^\n]*)|("(?:\\[\s\S]|[^"\\])*"?|“[^”]*”?|‘[^’]*’?)|(\$\$?[\p{L}_][\p{L}\p{N}_]*)|([\p{L}_][\p{L}\p{N}_ .]*::[\p{L}_][\p{L}\p{N}_ .]*)|(\b\d+(?:\.\d+)?\b)|(\b(?:True|False|Yes|No|On|Off|Always|Minimum|Never)\b)|([\[\]();])|([\p{L}_][\p{L}\p{N}_]*(?=\s*\())/gu;
export function highlightScript(source){
 tokens.lastIndex=0;
 let html='',offset=0;
 const names=['comment','string','variable','field','number','constant','punctuation','function'];
 for(const match of source.matchAll(tokens)){
  const plain=source.slice(offset,match.index);
  html+=paintSteps(plain,offset===0||source[offset-1]==='\n');
  const kind=names[match.slice(1).findIndex(v=>v!==undefined)];
  html+=`<span class="syntax-${kind}">${escapeHTML(match[0])}</span>`;
  offset=match.index+match[0].length;
 }
 return html+paintSteps(source.slice(offset),offset===0||source[offset-1]==='\n');
}
function paintSteps(text,atStart){
 return text.split('\n').map((line,i)=>{
  if(i===0&&!atStart)return escapeHTML(line);
  const match=/^(\s*)([A-Za-z][A-Za-z0-9 /-]*?)(\s*)$/.exec(line);
  return match?escapeHTML(match[1])+`<span class="syntax-step">${escapeHTML(match[2])}</span>`+escapeHTML(match[3]):escapeHTML(line);
 }).join('\n');
}
