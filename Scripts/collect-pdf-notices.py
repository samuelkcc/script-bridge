#!/usr/bin/env python3
"""Verify bundled offline PDF reader assets and include their original notices."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def collect():
    directory=ROOT/'Desktop/notices/pdfjs'
    source=json.loads((directory/'SOURCE.json').read_text())
    assets=ROOT/'Desktop/web/vendor/pdfjs'
    for name,sha in source['files'].items():
        if hashlib.sha256((assets/name).read_bytes()).hexdigest()!=sha:
            raise RuntimeError('PDF reader asset checksum mismatch: '+name)
    core=(directory/'core-js-LICENSE.txt').read_bytes()
    if hashlib.sha256(core).hexdigest()!=source['coreJSLicenseSHA256']:
        raise RuntimeError('PDF reader polyfill licence checksum mismatch')
    entries=[]
    for name,file,license in [('Mozilla PDF.js','LICENSE','Apache-2.0'),('PDF.js CMaps','cmaps/LICENSE','BSD-3-Clause'),('PDF.js Foxit fonts','standard_fonts/LICENSE_FOXIT','BSD-3-Clause'),('PDF.js Liberation fonts','standard_fonts/LICENSE_LIBERATION','OFL-1.1')]:
        entries.append(dict(kind='frontend-library',name=name,version=source['version'],license=license,repository=source['source'],text=(assets/file).read_text()))
    entries.append(dict(kind='frontend-library',name='core-js (PDF.js compatibility build)',version=source['coreJSVersion'],license='MIT',repository=source['coreJSSource'],text=core.decode()))
    output=ROOT/'Desktop/web/assets/notices.json';data=json.loads(output.read_text())
    data['entries']=[e for e in data['entries'] if e.get('kind')!='frontend-library']+entries
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('Verified PDF reader assets and included',len(entries),'PDF/library notices.')
if __name__=='__main__':collect()
