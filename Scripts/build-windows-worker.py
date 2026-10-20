#!/usr/bin/env python3
"""Cross-compile the existing Swift engine using the matching Swift.org SDK.

Toolchains and Windows headers are prepared under .build; no Mac installation
or application is changed. See Documentation/WINDOWS_BUILD.md for the pinned inputs.
"""
from pathlib import Path
import argparse, os, subprocess
ROOT = Path(__file__).resolve().parents[1]
SWIFT = ROOT / '.build/swift-6.4.0-macos-expanded/swift-6.4.0-RELEASE-osx-package.pkg/Payload/usr/bin/swiftc'
SDK = ROOT / '.build/swift-windows-sdk/LocalApp/Programs/Swift/Platforms/6.4.0/Windows.platform/Developer/SDKs/Windows.sdk'
OUTPUT = ROOT / '.build/windows-worker'
LLVM = Path(os.environ.get('BRIDGE_WINDOWS_LLVM', Path.home() / '.local/opt/hpi-windows-toolchain/llvm@20/20.1.8/bin'))

def build(typecheck=False):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    flags = ['-target','x86_64-unknown-windows-msvc','-sdk',str(SDK),
        '-resource-dir',str(SDK/'usr/lib/swift'),'-module-cache-path',str(ROOT/'.build/swift-win-module-cache'),
        '-swift-version','6','-O','-file-prefix-map',str(ROOT)+'=/src/filemaker-script-bridge']
    for name in ['crt','ucrt','shared','um','winrt']:
        flags += ['-Xcc','-isystem','-Xcc',str(ROOT/'.build/swift-windows-headers'/name)]
    # These affect diagnostics only when using the SDK 26100 UCRT headers with
    # the newer MSVC threads.h header. The application ABI is unchanged.
    for define in ['_CRT_USE_BUILTIN_OFFSETOF','_UCRT_DISABLE_CLANG_WARNINGS=','_UCRT_RESTORE_CLANG_WARNINGS=']:
        flags += ['-Xcc','-D'+define]
    sources = sorted((ROOT/'Sources/FileMakerBridgeCore').glob('*.swift'))
    env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(ROOT/'.build/swift-win-module-cache'))
    if typecheck:
        subprocess.run([str(SWIFT),*flags,'-typecheck','-'],input='import Foundation\nimport FoundationXML\n',text=True,check=True,env=env)
        return
    subprocess.run([str(SWIFT),*flags,'-parse-as-library','-module-name','FileMakerBridgeCore',
        '-whole-module-optimization','-emit-module','-emit-module-path',str(OUTPUT/'FileMakerBridgeCore.swiftmodule'),
        '-emit-object',*map(str,sources),'-o',str(OUTPUT/'FileMakerBridgeCore.obj')],check=True,env=env)
    link = ['-tools-directory',str(LLVM),'-use-ld=lld', '-L',str(SDK/'usr/lib/swift/windows/x86_64')]
    for relative in ['crt/lib/x86_64','sdk/lib/um/x86_64','sdk/lib/ucrt/x86_64']:
        link += ['-L',str(ROOT/'.build/xwin-cache/xwin'/relative)]
    subprocess.run([str(SWIFT),*flags,*link,'-I',str(OUTPUT),str(ROOT/'Sources/FileMakerBridgeWorker/main.swift'),
        str(OUTPUT/'FileMakerBridgeCore.obj'),'-o',str(OUTPUT/'FileMakerBridgeWorker.exe')],check=True,env=env)
    print('Windows conversion worker:',OUTPUT/'FileMakerBridgeWorker.exe')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--typecheck',action='store_true');a=p.parse_args();build(a.typecheck)
