#!/usr/bin/env python3
"""Fetch original Windows platform/runtime notices once and record their hashes.

Downloaded notices are checked into Desktop/notices/platform. Offline builds
verify that inventory rather than needing access to any licence website.
"""
from pathlib import Path
import base64, hashlib, json, shutil, urllib.request, xml.etree.ElementTree as ET, zipfile
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'Desktop/notices/platform';DEST.mkdir(parents=True,exist_ok=True)
entries=[]
def save(name,version,license,filename,data,url):
    (DEST/filename).write_bytes(data)
    entries.append(dict(name=name,version=version,license=license,file=filename,source=url,sha256=hashlib.sha256(data).hexdigest()))
def fetch(name,version,license,filename,url):
    with urllib.request.urlopen(url,timeout=60) as response:data=response.read()
    save(name,version,license,filename,data,url)
def blob(name,version,license,filename,repository,sha):
    url=f'https://api.github.com/repos/{repository}/git/blobs/{sha}'
    with urllib.request.urlopen(url,timeout=60) as response:data=base64.b64decode(json.load(response)['content'])
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==sha
    save(name,version,license,filename,data,url)

save('Swift Windows runtime','6.4.0','Apache-2.0 WITH Swift-exception','Swift-LICENSE.txt',
    (ROOT/'.build/swift-6.4.0-macos-expanded/swift-6.4.0-RELEASE-osx-package.pkg/Payload/usr/share/swift/LICENSE.txt').read_bytes(),
    'https://download.swift.org/swift-6.4.0-release/windows10/swift-6.4.0-RELEASE/swift-6.4.0-RELEASE-windows10.exe')
fetch('Swift Corelibs Foundation / FoundationXML','6.4.0','Apache-2.0 WITH Swift-exception','Foundation-LICENSE.txt',
    'https://raw.githubusercontent.com/swiftlang/swift-corelibs-foundation/swift-6.4.0-RELEASE/LICENSE')
blob('Swift Foundation Essentials / Internationalization','Runtime supplied with Swift 6.4.0','Apache-2.0 WITH Swift-exception','Foundation-Essentials-LICENSE.md',
    'swiftlang/swift-foundation','004d67aff35d05d06650d50bf14a7ac789557e7c')
blob('Swift Foundation attribution','Upstream notice snapshot','See Foundation licence','Foundation-NOTICE.txt',
    'swiftlang/swift-foundation','3db00abbfd019be6e9325437d4cc6e2287f79867')
blob('Swift Foundation ICU wrapper','Runtime supplied with Swift 6.4.0','Apache-2.0 WITH Swift-exception','Foundation-ICU-LICENSE.md',
    'swiftlang/swift-foundation-icu','004d67aff35d05d06650d50bf14a7ac789557e7c')
fetch('ICU and Unicode components','Upstream licence snapshot 77.1; bundled via Swift 6.4.0','Unicode-3.0 and original third-party notices','ICU-LICENSE.txt',
    'https://raw.githubusercontent.com/unicode-org/icu/release-77-1/LICENSE')
fetch('Swift Dispatch / Blocks runtime','6.4.0','Apache-2.0 WITH Swift-exception','Dispatch-LICENSE.txt',
    'https://raw.githubusercontent.com/swiftlang/swift-corelibs-libdispatch/swift-6.4.0-RELEASE/LICENSE')
fetch('libxml2 embedded by FoundationXML','Upstream copyright snapshot 2.14.6; bundled via Swift 6.4.0','MIT','libxml2-Copyright.txt',
    'https://raw.githubusercontent.com/GNOME/libxml2/v2.14.6/Copyright')
fetch('LLVM OpenMP (libomp.dll)','Bundled in llama.cpp b11669; upstream licence snapshot 20.1.8','Apache-2.0 WITH LLVM-exception','OpenMP-LICENSE.txt',
    'https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-20.1.8/openmp/LICENSE.TXT')
source=ROOT/'.build/Visual-C-Runtime-License.docx'
shutil.copy2(source,DEST/'Visual-C-Runtime-License.docx')
with zipfile.ZipFile(source) as archive:
    document=ET.fromstring(archive.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    text='\n'.join(''.join(p.itertext()) for p in document.findall('.//w:p',ns))+'\n'
save('Microsoft Visual C++ runtime','Runtime DLLs distributed by Swift 6.4.0','Microsoft Visual C++ Runtime terms','Visual-C-Runtime-LICENSE.txt',text.encode(),
    'https://visualstudio.microsoft.com/wp-content/uploads/2021/09/Visual-C-Runtime-2015-2022-License-1.docx')
save('NSIS installer stub and zlib compression','3.13','Zlib; complete original NSIS notices included','NSIS-COPYING.txt',
    Path('/opt/homebrew/share/nsis/COPYING').read_bytes(),'https://nsis.sourceforge.io/License')
(DEST/'inventory.json').write_text(json.dumps({'entries':entries},ensure_ascii=False,indent=2)+'\n')
print(f'Retained {len(entries)} original platform/runtime notice entries.')
