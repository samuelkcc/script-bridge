export const routes={home:'Welcome',playground:'AI playground',workspace:'Script workspace',reference:'Step reference',guide:'Quick guide',about:'About & licences'};
export const themes=['light','dark','system'];
export function escapeHTML(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
export function canExport(result,source,pending){return !pending && result?.canCopy===true && result.source===source;}
export function filterCatalogue(entries,query='',support='all'){
 const term=query.toLocaleLowerCase().trim();
 return entries.filter(row=>(support==='all'||row.support===support)&&`${row.name} ${row.category}`.toLocaleLowerCase().includes(term));
}
export function lineSelection(source,line){
 const lines=source.split('\n');const n=Math.max(0,Math.min(lines.length-1,Number(line)-1));
 const start=lines.slice(0,n).reduce((sum,l)=>sum+l.length+1,0);return [start,start+lines[n].length];
}
export function noticeMatches(row,query){return `${row.name} ${row.version} ${row.license}`.toLocaleLowerCase().includes(query.toLocaleLowerCase().trim());}
