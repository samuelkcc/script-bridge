#!/usr/bin/env python3
"""Merge the verified checked-in platform/runtime notices into the app viewer."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def collect():
    directory=ROOT/'Desktop/notices/platform'
    entries=[]
    for row in json.loads((directory/'inventory.json').read_text())['entries']:
        original=(directory/row['file']).read_bytes()
        if hashlib.sha256(original).hexdigest()!=row['sha256']:raise RuntimeError('Platform notice checksum mismatch: '+row['file'])
        entries.append(dict(kind='platform-runtime',name=row['name'],version=row['version'],license=row['license'],repository=row['source'],
            text=f'Windows platform/runtime notice.\nOriginal notice source: {row["source"]}\n\n'+original.decode('utf-8')))
    path=ROOT/'Desktop/web/assets/notices.json';data=json.loads(path.read_text())
    data['entries']=[e for e in data['entries'] if e.get('kind')!='platform-runtime']+entries
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('Included platform/runtime notices:',len(entries))
if __name__=='__main__':collect()
