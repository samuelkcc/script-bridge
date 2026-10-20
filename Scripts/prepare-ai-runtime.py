#!/usr/bin/env python3
"""Prepare the pinned official llama.cpp runtime; optional network fetch."""
import argparse, hashlib, json, os, platform, shutil, tarfile, urllib.request, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CATALOGUE=json.loads((ROOT/'Desktop/ai/catalogue.json').read_text())
def target():
    if platform.system()=='Darwin':return 'macos-arm64' if platform.machine()=='arm64' else 'macos-x64'
    if platform.system()=='Windows' and platform.machine().lower() in ('amd64','x86_64'):return 'windows-x64'
    raise RuntimeError('AI runtime supports macOS ARM/Intel and Windows x64.')
def prepare(fetch=False, selected=None):
    selected=selected or target(); runtime=CATALOGUE['runtime']; asset=runtime['assets'][selected]
    archive=ROOT/'.build'/asset['filename']; dest=ROOT/'.build/ai-runtime'/selected
    source=ROOT/'.build'/runtime['sourceArchiveFile']
    if not source.is_file() and fetch:
        with urllib.request.urlopen(runtime['sourceArchiveURL'],timeout=120) as response, source.open('wb') as output:shutil.copyfileobj(response,output)
    if not source.is_file():raise RuntimeError('Matching inference source missing. Run Scripts/prepare-ai-runtime.py --fetch.')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=runtime['sourceArchiveSHA256']:raise RuntimeError('Inference source checksum mismatch.')
    if not archive.is_file():
        if not fetch:raise RuntimeError('Pinned AI runtime archive missing. Run python3 Scripts/prepare-ai-runtime.py --fetch first.')
        with urllib.request.urlopen(asset['url'],timeout=60) as response, archive.open('wb') as output:shutil.copyfileobj(response,output)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=asset['sha256']:raise RuntimeError('AI runtime archive checksum mismatch.')
    stage=dest.with_name(dest.name+'-stage')
    if stage.exists():shutil.rmtree(stage)
    stage.mkdir(parents=True)
    if archive.name.endswith('.zip'):
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                candidate=(stage/member.filename).resolve()
                if not candidate.is_relative_to(stage.resolve()):raise RuntimeError('Unsafe runtime archive path.')
            z.extractall(stage)
    else:
        with tarfile.open(archive) as tar:tar.extractall(stage,filter='data')
    name='llama-server.exe' if selected.startswith('windows') else 'llama-server'
    candidates=list(stage.rglob(name))
    if len(candidates)!=1:raise RuntimeError('Runtime archive has no unique llama-server.')
    source=candidates[0].parent
    prepared=dest.with_name(dest.name+'-prepared')
    if prepared.exists():shutil.rmtree(prepared)
    prepared.mkdir()
    # Keep native libraries, Metal kernels and original notices. Exclude other tools.
    for p in source.iterdir():
        if p.name==name or p.suffix in ('.dylib','.dll','.metal','.metallib') or p.name.upper().startswith(('LICENSE','COPYING','NOTICE')):
            if p.is_file():shutil.copy2(p,prepared/p.name)
    (prepared/'SOURCE.json').write_text(json.dumps(runtime,indent=2)+'\n')
    if dest.exists():shutil.rmtree(dest)
    prepared.rename(dest);shutil.rmtree(stage)
    print('Prepared checked AI runtime:',dest)
    return dest
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fetch',action='store_true');p.add_argument('--target',choices=list(CATALOGUE['runtime']['assets']));args=p.parse_args();prepare(args.fetch,args.target)
