#!/usr/bin/env python3
"""Stage and audit the x64 app, Swift DLL closure and pinned inference engine.

Produces one per-user NSIS installer in dist; weights remain optional downloads.
"""
from pathlib import Path
import argparse, hashlib, json, os, shutil, struct, subprocess, tomllib
ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT/'Desktop/src-tauri/Cargo.toml').read_text())['package']['version']
OUTPUT = ROOT/'.build/releases'/VERSION
STAGE = OUTPUT/'windows-x64'
SYSTEM = set('kernel32 kernelbase ntdll user32 advapi32 ole32 oleaut32 shell32 shlwapi version crypt32 bcrypt bcryptprimitives ws2_32 normaliz ucrtbase winmm userenv iphlpapi psapi winhttp wininet urlmon rpcrt4 secur32 sspicli dnsapi dbghelp dbgcore gdi32 gdiplus comctl32 comdlg32 dwmapi dwrite d3d11 dxgi d3dcompiler_47 uxtheme imm32 msimg32 propsys setupapi cfgmgr32 netapi32 wintrust imagehlp powrprof shcore winspool drvstore wtsapi32'.split())
SYSTEM.add('combase')

def pe_imports(path):
    data = path.read_bytes()
    if data[:2] != b'MZ': raise RuntimeError(f'Not a Windows executable: {path.name}')
    pe = struct.unpack_from('<I',data,0x3c)[0]
    if data[pe:pe+4] != b'PE\0\0': raise RuntimeError('Invalid PE signature')
    machine, count = struct.unpack_from('<HH',data,pe+4)
    if machine != 0x8664: raise RuntimeError(f'Expected AMD64 code: {path.name}')
    optional = pe+24
    if struct.unpack_from('<H',data,optional)[0] != 0x20b: raise RuntimeError('Expected PE32+')
    optional_size = struct.unpack_from('<H',data,pe+20)[0]
    sections = []
    for i in range(count):
        start = optional+optional_size+40*i
        virtual_size, address, size, offset = struct.unpack_from('<IIII',data,start+8)
        sections.append((address,max(virtual_size,size),offset))
    def at(rva):
        for address,size,offset in sections:
            if address <= rva < address+size: return offset+rva-address
        raise RuntimeError(f'Invalid import address: {path.name}')
    import_rva, import_size = struct.unpack_from('<II',data,optional+112+8)
    imports = []
    def add_name(rva):
        name = at(rva); end = data.index(0,name)
        imports.append(data[name:end].decode('ascii'))
    if import_rva:
        offset = at(import_rva)
        for i in range(1024):
            values = struct.unpack_from('<IIIII',data,offset+20*i)
            if not any(values): break
            add_name(values[3])
        else: raise RuntimeError('Unbounded PE import table')
    delay_rva, _ = struct.unpack_from('<II',data,optional+112+13*8)
    if delay_rva:
        offset = at(delay_rva)
        base = struct.unpack_from('<Q',data,optional+24)[0]
        for i in range(1024):
            values = struct.unpack_from('<8I',data,offset+32*i)
            if not any(values): break
            add_name(values[1] if values[0]&1 else values[1]-base)
        else: raise RuntimeError('Unbounded PE delay import table')
    return sorted(set(imports))

def is_system(name):
    lower = name.lower()
    return lower.startswith(('api-ms-win-','ext-ms-win-')) or lower.removesuffix('.dll') in SYSTEM

def close_dependencies(entrypoints,pool):
    queue = list(entrypoints); checked = set()
    while queue:
        path = queue.pop()
        if path in checked: continue
        checked.add(path)
        for name in pe_imports(path):
            if is_system(name): continue
            target = path.parent/name
            existing = next((p for p in path.parent.iterdir() if p.name.lower()==name.lower()),None)
            if existing is None:
                source = pool.get(name.lower())
                if source is None: raise RuntimeError(f'Unresolved DLL: {path.name} requires {name}')
                shutil.copy2(source,target)
                existing = target
            queue.append(existing)
    return checked

def package():
    host = ROOT/'Desktop/src-tauri/target/x86_64-pc-windows-msvc/release/filemaker-script-bridge-desktop.exe'
    worker = ROOT/'.build/windows-worker/FileMakerBridgeWorker.exe'
    runtime = ROOT/'.build/ai-runtime/windows-x64'
    for path in [host,worker,runtime/'llama-server.exe',ROOT/'.build/MicrosoftEdgeWebview2Setup.exe']:
        if not path.is_file(): raise RuntimeError(f'Required package input missing: {path}')
    bootstrapper = ROOT/'.build/MicrosoftEdgeWebview2Setup.exe'
    if hashlib.sha256(bootstrapper.read_bytes()).hexdigest() != 'f414de01c4680f0bb0694d1ea7803c6968f3a81bf6bad01b89bfc65dce14c2a2':
        raise RuntimeError('WebView2 bootstrapper checksum mismatch; review a changed upstream download before updating its pin.')
    if STAGE.exists(): shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    shutil.copy2(host,STAGE/'FileMakerScriptBridge.exe')
    shutil.copy2(worker,STAGE/worker.name)
    shutil.copytree(runtime,STAGE/'ai-runtime')
    for name in ['LICENSE','NOTICE.txt']:
        shutil.copy2(ROOT/name,STAGE/name)
    shutil.copy2(ROOT/'Desktop/web/assets/notices.json',STAGE/'component-notices.json')
    shutil.copytree(ROOT/'Desktop/notices/platform',STAGE/'licences')
    (STAGE/'Windows testing.txt').write_text(
        f'Script Bridge {VERSION} — Windows x64 test build\n\n'
        'Install the app, then launch it from the Start menu. The conversion worker and required DLLs are included; a Swift toolchain is not needed. Setup installs Microsoft WebView2 from Microsoft if it is missing (internet required).\n\n'
        '1. Open Script workspace and load the example. Choose Copy to FileMaker.\n'
        '2. In a test FileMaker solution, open Script Workspace, choose the insertion point and press Ctrl+V. Check the steps and calculations.\n'
        '3. Copy those steps in FileMaker. Choose FileMaker → Text in the bridge and read the clipboard.\n'
        '4. Check accented/Chinese text, multiline calculations, Smart Fix and preserved native steps in the same session.\n'
        '5. Optionally choose a Gemma or Qwen model in AI playground. Check download/cancel/resume, generation, review and model removal.\n\n'
        'This executable was cross-compiled on macOS. Native Windows display, installation, FileMaker clipboard acceptance and inference still need your test. It is unsigned.\n'
        'The installer does not bundle model weights. Removing the application retains downloaded models in the per-user app data folder; remove models in the playground first if desired.\n',encoding='utf-8')
    pool = {p.name.lower():p for p in (ROOT/'.build/swift-windows-runtime').glob('*.dll')}
    pool.update({p.name.lower():p for p in runtime.glob('*.dll')})
    checked = close_dependencies([p for p in STAGE.rglob('*') if p.suffix.lower() in ('.exe','.dll')],pool)
    files = sorted(p for p in STAGE.rglob('*') if p.is_file())
    manifest = {p.relative_to(STAGE).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
    (OUTPUT/'windows-payload-manifest.json').write_text(json.dumps({'version':VERSION,'architecture':'x86_64','nativeWindowsTested':False,'auditedPEFiles':len(checked),'files':manifest},indent=2)+'\n')
    # Delete only package-owned files on uninstall; keep user model data.
    lines = [f'Delete "$INSTDIR\\{name.replace(chr(47),chr(92))}"' for name in manifest]
    directories = sorted({p.parent.relative_to(STAGE).as_posix() for p in files if p.parent!=STAGE},key=lambda s:s.count('/'),reverse=True)
    lines += [f'RMDir "$INSTDIR\\{name.replace(chr(47),chr(92))}"' for name in directories]
    (OUTPUT/'windows-uninstall-files.nsh').write_text('\n'.join(lines)+'\n')
    dest = ROOT/'dist/Script Bridge.exe'
    dest.parent.mkdir(exist_ok=True)
    subprocess.run(['makensis',f'-DROOT={ROOT}',f'-DSTAGE={STAGE}',f'-DVERSION={VERSION}',f'-DOUTPUT={dest}',f'-DUNINSTALL_FILES={OUTPUT / "windows-uninstall-files.nsh"}',str(ROOT/'Desktop/windows/installer.nsi')],check=True)
    receipt = {'version':VERSION,'architecture':'x86_64','type':'per-user installer','file':dest.name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'nativeWindowsTested':False,'swiftToolchainRequired':False,'modelsBundled':False}
    (OUTPUT/'windows-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    shutil.copy2(dest,OUTPUT/'Script-Bridge-Windows-x64.exe')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__': package()
