#!/usr/bin/env python3
"""Append pinned AI runtime and optional model notices to the offline inventory."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def collect():
    catalogue=json.loads((ROOT/'Desktop/ai/catalogue.json').read_text());runtime=catalogue['runtime']
    source=ROOT/'.build'/runtime['sourceArchiveFile']
    if not source.is_file():raise RuntimeError('Matching llama.cpp source archive is required for AI notices and packaging.')
    actual=hashlib.sha256(source.read_bytes()).hexdigest()
    if runtime.get('sourceArchiveSHA256')!=actual:raise RuntimeError('Inference source checksum mismatch.')
    entries=[]
    with tarfile.open(source) as archive:
        prefix='llama.cpp-'+runtime['revision']+'/'
        for member in archive.getmembers():
            if not member.isfile():continue
            relative=member.name.removeprefix(prefix)
            basename=Path(relative).name
            if not basename.upper().startswith(('LICENSE','COPYING','NOTICE')):continue
            original=archive.extractfile(member).read().decode('utf-8',errors='replace')
            entries.append({'kind':'runtime' if relative=='LICENSE' else 'runtime-component','name':'llama.cpp' if relative=='LICENSE' else 'llama.cpp / '+relative,'version':runtime['version'],'license':'MIT' if relative=='LICENSE' else 'See original licence text','repository':runtime['sourceURL'],'text':f'Original source: {runtime["sourceURL"]}/{relative}\nSource revision: {runtime["revision"]}\n\n{original}'})
    model_license=(ROOT/'Desktop/web/assets/ai/Qwen-LICENSE.txt').read_text()
    for model in catalogue['models']:
        entries.append({'kind':'model','name':model['name']+' (optional Q4_K_M download)','version':model['revision'][:12],'license':model['license'],'repository':model['sourceURL'],'text':f'Publisher: Qwen\nQuantized conversion publisher: {model["converter"]}\nConversion source: https://huggingface.co/{model["repository"]}/tree/{model["revision"]}\nExact file: {model["filename"]}\nDownload bytes: {model["bytes"]}\nExpected SHA-256: {model["sha256"]}\n\nModel weights are downloaded only when chosen. They are not included in the app. FileMaker Script Bridge is independent of Qwen and Unsloth.\n\nOriginal Qwen model licence:\n\n{model_license}'})
    output=ROOT/'Desktop/web/assets/notices.json';data=json.loads(output.read_text());data['entries']=[e for e in data['entries'] if not e.get('kind')]+entries
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f'Included {len(entries)} AI/model/source notices.')
if __name__=='__main__':collect()
