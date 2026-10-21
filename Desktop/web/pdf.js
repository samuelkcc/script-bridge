export const PDF_LIMITS={bytes:15*1024*1024,pages:40,characters:120000};

// Keep printed line breaks and indentation. Do not rewrite calculations or strip
// apparent headers: only the model, with the full document, interprets the printout.
export function pageText(items){
 if(items.length>100000)throw Error('This PDF page is too complex. Print the script to a simpler PDF.');
 const rows=[];
 const ordered=items.filter(i=>typeof i.str==='string'&&i.str&&i.transform).sort((a,b)=>b.transform[5]-a.transform[5]||a.transform[4]-b.transform[4]);
 for(const item of ordered){
  const x=item.transform[4],y=item.transform[5];
  let row=rows.at(-1);
  if(row&&Math.abs(row.y-y)>=Math.max(1,Math.abs(item.height||0)*.15))row=null;
  if(!row){row={y,items:[]};rows.push(row);}row.items.push({...item,x});
 }
 rows.sort((a,b)=>b.y-a.y);
 const left=ordered.reduce((min,i)=>Math.min(min,i.transform[4]),Infinity);
 return rows.map(row=>{
  row.items.sort((a,b)=>a.x-b.x);let text='',end=null;
  for(const item of row.items){
   if(end!==null&&item.x-end>.7&&!/\s$/.test(text)&&!/^\s/.test(item.str))text+=' ';
   text+=item.str;end=item.x+(item.width||0);
  }
  return ' '.repeat(Math.min(40,Math.max(0,Math.round((row.items[0].x-left)/7))))+text;
 }).join('\n');
}

export async function readPdf(file,{onProgress=()=>{},signal}={}){
 if(!file||!file.name.toLowerCase().endsWith('.pdf'))throw Error('Choose a PDF printed from FileMaker’s Script Workspace.');
 if(file.size>PDF_LIMITS.bytes)throw Error('This PDF is too large. Choose a file smaller than 15 MB.');
 if(!file.size)throw Error('This PDF is empty.');
 const data=new Uint8Array(await file.arrayBuffer());
 const header=new TextDecoder('ascii').decode(data.subarray(0,1024));
 if(!header.includes('%PDF-'))throw Error('This file is not a readable PDF. Print the script to PDF again.');
 if(signal?.aborted)throw Error('PDF attachment removed.');
 const pdfjs=await import('./vendor/pdfjs/pdf.min.mjs');
 pdfjs.GlobalWorkerOptions.workerSrc=new URL('./vendor/pdfjs/pdf.worker.min.mjs',import.meta.url).href;
 const task=pdfjs.getDocument({data,isEvalSupported:false,useWasm:false,disableFontFace:true,useSystemFonts:false,enableXfa:false,stopAtErrors:true,verbosity:0,
  cMapUrl:new URL('./vendor/pdfjs/cmaps/',import.meta.url).href,cMapPacked:true,standardFontDataUrl:new URL('./vendor/pdfjs/standard_fonts/',import.meta.url).href});
 let timedOut=false;
 const abort=()=>{void task.destroy();};
 const timeout=setTimeout(()=>{timedOut=true;abort();},60000);
 signal?.addEventListener('abort',abort,{once:true});
 try{
  const pdf=await task.promise;
  if(pdf.numPages>PDF_LIMITS.pages)throw Error('Choose a PDF with 40 pages or fewer.');
  const pages=[];let length=0;
  for(let n=1;n<=pdf.numPages;n++){
   if(signal?.aborted)throw Error('PDF attachment removed.');
   onProgress(n,pdf.numPages);
   const page=await pdf.getPage(n);
   const text=pageText((await page.getTextContent({disableNormalization:true})).items);
   if(!text.trim())throw Error(`Page ${n} has no readable text. Use FileMaker’s Print to PDF; scanned pages need OCR before attaching.`);
   length+=text.length;
   if(length>PDF_LIMITS.characters)throw Error('The PDF text is too long. Attach a smaller script (up to 120,000 characters).');
   pages.push(`--- PDF page ${n} of ${pdf.numPages} ---\n${text}`);page.cleanup();
  }
  return {name:file.name,pages:pdf.numPages,text:pages.join('\n\n')};
 }catch(error){
  if(signal?.aborted)throw Error('PDF attachment removed.');
  if(timedOut)throw Error('Reading this PDF took too long. Print the script to a new PDF and try again.');
  if(error?.name==='PasswordException')throw Error('This PDF is password protected. Attach an unlocked copy.');
  throw Error(error?.message||'Could not read this PDF. Print the script to PDF again.');
 }finally{clearTimeout(timeout);signal?.removeEventListener('abort',abort);await task.destroy();}
}
