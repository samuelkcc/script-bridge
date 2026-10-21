#!/usr/bin/env python3
"""Build/run/package the shared desktop with installed Swift + Rust toolchains."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'Desktop/src-tauri/Cargo.toml'
VERSION = tomllib.loads(MANIFEST.read_text())['package']['version']
MAC_BUILD = '2026102104'
HOST = 'filemaker-script-bridge-desktop' + ('.exe' if os.name == 'nt' else '')
WORKER = 'FileMakerBridgeWorker' + ('.exe' if os.name == 'nt' else '')

def run(args, **kw):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True, **kw)

def environment():
    env = os.environ.copy()
    env['CLANG_MODULE_CACHE_PATH'] = str(ROOT / '.build/desktop-module-cache')
    env['SWIFTPM_MODULECACHE_OVERRIDE'] = env['CLANG_MODULE_CACHE_PATH']
    return env

def build(debug=False):
    mode = 'debug' if debug else 'release'
    run(['swift', 'build', '--disable-sandbox', '--build-system', 'native', '--scratch-path', '.build/desktop-worker', '-c', mode, '--product', 'FileMakerBridgeWorker'], env=environment())
    binary_dir = subprocess.check_output(['swift', 'build', '--disable-sandbox', '--build-system', 'native', '--scratch-path', str(ROOT / '.build/desktop-worker'), '-c', mode, '--show-bin-path'], cwd=ROOT, env=environment(), text=True).strip()
    triple = next(line.split(': ', 1)[1] for line in subprocess.check_output(['rustc', '-vV'], text=True).splitlines() if line.startswith('host: '))
    destination = ROOT / f'Desktop/src-tauri/binaries/FileMakerBridgeWorker-{triple}{".exe" if os.name == "nt" else ""}'
    shutil.copy2(Path(binary_dir) / WORKER, destination)
    # Keep visible and package versions aligned with the Cargo manifest.
    (ROOT / 'Desktop/web/version.js').write_text('// Generated from Desktop/src-tauri/Cargo.toml by Scripts/desktop.py.\nexport const APP_VERSION = ' + json.dumps(VERSION) + ';\n')
    for filename in ('Desktop/package.json', 'Desktop/src-tauri/tauri.conf.json'):
        path = ROOT / filename
        data = json.loads(path.read_text())
        data['version'] = VERSION
        path.write_text(json.dumps(data, indent=2) + '\n')
    # All needed cached package sources must be available, including Windows notices.
    run([sys.executable, 'Scripts/collect-desktop-notices.py'])
    run([sys.executable, 'Scripts/prepare-ai-runtime.py'])
    run([sys.executable, 'Scripts/collect-ai-notices.py'])
    run([sys.executable, 'Scripts/collect-platform-notices.py'])
    run([sys.executable, 'Scripts/collect-pdf-notices.py'])
    hello = subprocess.run([str(Path(binary_dir) / WORKER)], input='{"op":"hello"}\n', capture_output=True, text=True, check=True)
    catalogue = json.loads(hello.stdout)['result']['catalogue']
    (ROOT / 'Desktop/web/assets/catalogue.json').write_text(json.dumps(catalogue, indent=2) + '\n')
    shutil.copy2(ROOT / 'LICENSE', ROOT / 'Desktop/web/assets/application-LICENSE.txt')
    command = ['cargo', 'build', '--locked', '--offline', '--manifest-path', MANIFEST]
    if not debug: command.append('--release')
    run(command)
    return ROOT / 'Desktop/src-tauri/target' / mode / HOST, Path(binary_dir) / WORKER

def source_archives(output):
    # Include the reviewed working source, with no build caches or FileMaker data.
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0')
    with tarfile.open(output / 'project-source.tar.gz', 'w:gz') as archive:
        for raw in names:
            if not raw: continue
            name = os.fsdecode(raw)
            path = ROOT / name
            if path.is_file() and not path.is_symlink() and path.suffix.lower() != '.fmp12':
                archive.add(path, arcname='filemaker-script-bridge/' + name, recursive=False)
    inventory = json.loads((ROOT / 'Desktop/web/assets/notices.json').read_text())
    cache = Path(os.environ.get('CARGO_HOME', Path.home() / '.cargo')) / 'registry/cache'
    lock = {(p['name'], p['version']): p for p in tomllib.loads((ROOT / 'Desktop/src-tauri/Cargo.lock').read_text())['package']}
    with tarfile.open(output / 'component-sources.tar.gz', 'w:gz') as archive:
        for entry in inventory['entries']:
            if entry.get('kind'): continue
            filename = f'{entry["name"]}-{entry["version"]}.crate'
            candidates = list(cache.glob('*/' + filename))
            if not candidates: raise RuntimeError(f'Matching component source missing: {filename}. Run cargo fetch first.')
            source = candidates[0]
            expected = lock[entry['name'], entry['version']]['checksum']
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected: raise RuntimeError(f'Source checksum mismatch: {filename}')
            archive.add(source, arcname=filename)
    # PDF.js uses its original JS sources; include the exact preferred source
    # archives with the binary's other corresponding-source materials.
    run([sys.executable, 'Scripts/prepare-pdf-sources.py'])
    pdf_sources = json.loads((ROOT / 'Desktop/notices/pdfjs/SOURCE.json').read_text())['sourceArchives']
    with tarfile.open(output / 'frontend-runtime-source.tar.gz', 'w:gz') as archive:
        for row in pdf_sources:
            path = ROOT / '.build/pdf-runtime-sources' / row['file']
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise RuntimeError('Matching PDF reader source missing: ' + row['file'] + '. Fetch its pinned URL in Desktop/notices/pdfjs/SOURCE.json.')
            archive.add(path, arcname=row['file'])


def release_manifest(output):
    files = [p for p in output.iterdir() if p.is_file() and p.name.endswith(('.zip', '.tar.gz', '.exe'))]
    manifest = {'version': VERSION, 'platform': sys.platform, 'architecture': subprocess.check_output(['rustc', '-vV'], text=True).split('host: ')[1].splitlines()[0], 'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
    windows_receipt = output / 'windows-build-receipt.json'
    if windows_receipt.is_file():
        manifest['windows'] = json.loads(windows_receipt.read_text())
    (output / 'release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def package(host, worker, include_sources=True):
    # dist contains launchable deliverables only. Keep release records, source
    # archives and intermediate Windows packages in the build area.
    output = ROOT / '.build/releases' / VERSION
    output.mkdir(parents=True, exist_ok=True)
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    if sys.platform == 'darwin':
        app = dist / 'Script Bridge.app'
        if app.exists(): shutil.rmtree(app)
        contents = app / 'Contents'
        (contents / 'MacOS').mkdir(parents=True)
        resources = contents / 'Resources'; resources.mkdir()
        shutil.copy2(host, contents / 'MacOS/FileMakerScriptBridge')
        shutil.copy2(worker, contents / 'MacOS/FileMakerBridgeWorker')
        icon_name = f'AppIcon-{MAC_BUILD}'
        shutil.copy2(ROOT / 'Resources/AppIcon.icns', resources / f'{icon_name}.icns')
        for name in ['LICENSE', 'NOTICE.txt']: shutil.copy2(ROOT / name, resources / name)
        native_target = 'macos-arm64' if subprocess.check_output(['uname', '-m'], text=True).strip() == 'arm64' else 'macos-x64'
        runtime = ROOT / '.build/ai-runtime' / native_target
        if not (runtime / 'llama-server').is_file(): raise RuntimeError('Prepare the pinned native AI runtime before packaging.')
        shutil.copytree(runtime, resources / 'ai-runtime', symlinks=False)
        for binary in (resources / 'ai-runtime').iterdir():
            if binary.suffix == '.dylib' or binary.name == 'llama-server':
                run(['codesign', '--force', '--sign', '-', binary])
        shutil.copy2(ROOT / 'Desktop/web/assets/notices.json', resources / 'component-notices.json')
        info = dict(CFBundleName='Script Bridge', CFBundleDisplayName='Script Bridge', CFBundleIdentifier='com.sckc.filemaker-script-bridge', CFBundleExecutable='FileMakerScriptBridge', CFBundlePackageType='APPL', CFBundleShortVersionString=VERSION, CFBundleVersion=MAC_BUILD, CFBundleIconFile=f'{icon_name}.icns', LSMinimumSystemVersion='13.3', NSHighResolutionCapable=True, LSApplicationCategoryType='public.app-category.developer-tools', NSHumanReadableCopyright='Copyright © 2026 SCKC. GPL-3.0-or-later.')
        (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
        run(['codesign', '--force', '--sign', '-', contents / 'MacOS/FileMakerBridgeWorker'])
        run(['codesign', '--force', '--sign', '-', app])
        run(['codesign', '--verify', '--deep', '--strict', app])
        archive = output / 'Script-Bridge-macOS.zip'
        if archive.exists(): archive.unlink()
        run(['/usr/bin/ditto', '-c', '-k', '--keepParent', '--norsrc', app, archive])
    elif os.name == 'nt':
        # Windows developer package requires an installed official Swift runtime/toolchain.
        # Shipping an incomplete DLL set would produce a broken standalone app.
        app = output / 'Script-Bridge-Windows-developer'
        app.mkdir(exist_ok=True)
        shutil.copy2(host, app / 'FileMakerScriptBridge.exe')
        shutil.copy2(worker, app / WORKER)
        shutil.copytree(ROOT / '.build/ai-runtime/windows-x64', app / 'ai-runtime', dirs_exist_ok=True)
        for name in ['LICENSE', 'NOTICE.txt']: shutil.copy2(ROOT / name, app / name)
        shutil.copy2(ROOT / 'Desktop/web/assets/notices.json', app / 'component-notices.json')
        (app / 'WINDOWS-DEVELOPER.txt').write_text('Requires the official Swift 6.4 x64 toolchain/runtime on PATH and Microsoft Edge WebView2 Runtime. Native FileMaker paste/copy acceptance remains required. This package is unsigned.\nhttps://www.swift.org/install/windows/\n')
        shutil.make_archive(str(output / 'Script-Bridge-Windows-developer'), 'zip', output, app.name)
    else:
        raise RuntimeError('Packaging targets macOS and Windows only.')
    if include_sources:
        source_archives(output)
        runtime_manifest = json.loads((ROOT / 'Desktop/ai/catalogue.json').read_text())['runtime']
        shutil.copy2(ROOT / '.build' / runtime_manifest['sourceArchiveFile'], output / 'inference-runtime-source.tar.gz')
    release_manifest(output)
    print(f'Packaged desktop app: {app}')
    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run', 'package'])
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    host, worker = build(args.debug)
    if args.action == 'run':
        # The host discovers its packaged worker beside itself.
        shutil.copy2(worker, host.parent / WORKER)
        run([host])
    elif args.action == 'package': package(host, worker)
