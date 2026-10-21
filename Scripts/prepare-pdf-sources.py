#!/usr/bin/env python3
"""Cache and verify the exact preferred sources for the bundled PDF reader."""
from pathlib import Path
import argparse,hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parents[1]
def prepare(download=False):
    rows=json.loads((ROOT/'Desktop/notices/pdfjs/SOURCE.json').read_text())['sourceArchives']
    directory=ROOT/'.build/pdf-runtime-sources';directory.mkdir(parents=True,exist_ok=True)
    for row in rows:
        path=directory/row['file']
        if not path.is_file():
            if not download:raise RuntimeError('Missing PDF reader source. Run python3 Scripts/prepare-pdf-sources.py --download before packaging.')
            data=urllib.request.urlopen(row['url'],timeout=120).read()
            if hashlib.sha256(data).hexdigest()!=row['sha256']:raise RuntimeError('PDF source checksum mismatch: '+row['file'])
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('PDF source checksum mismatch: '+row['file'])
    print('Verified PDF reader and compatibility-library sources.')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--download',action='store_true')
    prepare(parser.parse_args().download)
