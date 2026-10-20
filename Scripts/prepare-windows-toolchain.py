#!/usr/bin/env python3
"""Prepare pinned Swift 6.4 Windows inputs without installing a toolchain.

Requires the downloaded inputs named in Documentation/WINDOWS_BUILD.md,
7zz at .build/7zip/7zz and the xwin SDK in .build/xwin-cache/xwin.
All extracted or adapted headers remain under .build.
"""
from pathlib import Path
import hashlib, shutil, struct, subprocess, xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1] / '.build'
INPUTS = {
 'swift-6.4.0-windows.exe':'76169a85bcba82854a0cd8f9655ffb74b3758d60c35a245457510095f2823c03',
 'swift-6.4.0-macos.pkg':'8fd03185b98fe27f54a54631c2449decf75d5b466ce8e34abbd414141063c6aa',
 '7z2604-mac.tar.xz':'bee04358cbcbc7106273cee0e8d72916db2696c48067a3538c34d8cd6fd16578',
}
def digest(path, algorithm='sha256'):
 h=hashlib.new(algorithm)
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def extract(source, destination, *names):
 destination.mkdir(parents=True,exist_ok=True)
 subprocess.run([str(ROOT/'7zip/7zz'),'x','-y',str(source),'-o'+str(destination),*names],check=True,stdout=subprocess.DEVNULL)

def reconstruct(tables,raw_folders,dest):
 pool=(tables/'!_StringPool').read_bytes();data=(tables/'!_StringData').read_bytes();ss=[''];off=0
 for i in range(4,len(pool),4):
  length,refs=struct.unpack_from('<HH',pool,i)
  ss.append(data[off:off+length].decode('cp1252'));off+=length
 assert off==len(data)
 def table(name,widths):
  b=(tables/('!'+name)).read_bytes();assert len(b)%sum(widths)==0
  n=len(b)//sum(widths);offset=0;cols=[]
  for w in widths:cols.append(struct.unpack_from('<'+('H' if w==2 else 'I')*n,b,offset));offset+=w*n
  return list(zip(*cols))
 dirs={ss[a]:(ss[b],ss[c]) for a,b,c in table('Directory',[2,2,2])}
 components={ss[r[0]]:ss[r[2]] for r in table('Component',[2,2,2,2,2,2])}
 def path(d):
  if not d:return Path()
  parent,name=dirs[d];name=name.split(':')[0].split('|')[-1]
  assert name not in ('..','/') and '/' not in name and chr(92) not in name
  return path(parent)/(name if name not in ('.','SourceDir') else '')
 count=0
 for row in table('File',[2,2,2,4,2,2,2,4]):
  source=next((folder/ss[row[0]] for folder in raw_folders if (folder/ss[row[0]]).is_file()),None)
  if source is None:continue
  assert source.stat().st_size==row[3]-2147483648
  name=ss[row[2]].split('|')[-1]
  target=dest/path(components[ss[row[1]]])/name
  target.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(source,target);count+=1
 print('Reconstructed',count,'files into',dest)

def prepare():
 for name,expected in INPUTS.items():
  if digest(ROOT/name)!=expected:raise RuntimeError('Pinned input checksum mismatch: '+name)
 compiler_root=ROOT/'swift-6.4.0-macos-expanded'
 if not compiler_root.exists():
  subprocess.run(['pkgutil','--expand-full',str(ROOT/'swift-6.4.0-macos.pkg'),str(compiler_root)],check=True)
 bootstrap=ROOT/'swift-windows-bootstrap'
 extract(ROOT/'swift-6.4.0-windows.exe',bootstrap)
 attached=ROOT/'swift-windows-attached.cab'
 if not attached.exists():
  # Burn container offset is specific to the SHA-256-pinned installer above.
  with (ROOT/'swift-6.4.0-windows.exe').open('rb') as source,attached.open('wb') as target:
   source.seek(1312800);shutil.copyfileobj(source,target)
 packages=ROOT/'swift-windows-packages'
 selected=['a10','a12','a23','a29','a31']
 extract(attached,packages,*selected)
 manifest=ET.parse(bootstrap/'0').getroot()
 found=set()
 for entry in manifest.iter():
  name=entry.get('SourcePath')
  if name not in selected:continue
  path=packages/name
  if path.stat().st_size!=int(entry.get('FileSize')) or digest(path,'sha512').upper()!=entry.get('Hash'):
   raise RuntimeError('Swift payload checksum mismatch: '+name)
  found.add(name)
 if found!=set(selected):raise RuntimeError('Incomplete Swift payload manifest')
 for source,dest in [('a12','swift-windows-tables'),('a10','swift-windows-runtime-tables'),('a29','swift-windows-common-raw'),('a31','swift-windows-sdk-raw'),('a23','swift-windows-runtime-raw')]:
  extract(packages/source,ROOT/dest)
 reconstruct(ROOT/'swift-windows-tables',[ROOT/'swift-windows-common-raw',ROOT/'swift-windows-sdk-raw'],ROOT/'swift-windows-sdk')
 reconstruct(ROOT/'swift-windows-runtime-tables',[ROOT/'swift-windows-runtime-raw'],ROOT/'swift-windows-runtime')
 sdk=ROOT/'swift-windows-sdk/LocalApp/Programs/Swift/Platforms/6.4.0/Windows.platform/Developer/SDKs/Windows.sdk'
 headers=ROOT/'swift-windows-headers'
 for name in ['crt','ucrt','shared','um','winrt']:
  source=ROOT/'xwin-cache/xwin'/('crt/include' if name=='crt' else 'sdk/include/'+name)
  shutil.copytree(source,headers/name,dirs_exist_ok=True,symlinks=False)
 for source,dest in [('vcruntime','crt'),('ucrt','ucrt'),('winsdk_shared','shared'),('winsdk_um','um')]:
  shutil.copy2(sdk/'usr/share'/f'{source}.modulemap',headers/dest/'module.modulemap')
 modulemap=headers/'ucrt/module.modulemap'
 modulemap.write_text(modulemap.read_text().replace('header "corecrt_math.h"',''))
 # SDK 26100 already declares math through math.h. Swift's newer module map
 # additionally expects these standard Clang headers, supplied by its compiler.
 clang=compiler_root/'swift-6.4.0-RELEASE-osx-package.pkg/Payload/usr/lib/clang/21/include'
 for name in ['stdalign.h','stdnoreturn.h']:shutil.copy2(clang/name,headers/'ucrt'/name)
 print('Prepared and verified Swift Windows SDK/runtime and local header adaptations.')

if __name__=='__main__':prepare()
