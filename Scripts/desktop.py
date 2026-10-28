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
UNIVERSAL_MAC_BUILD = '2026102801'
HOST = 'filemaker-script-bridge-desktop' + ('.exe' if os.name == 'nt' else '')
WORKER = 'FileMakerBridgeWorker' + ('.exe' if os.name == 'nt' else '')

def run(args, **kw):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True, **kw)

def environment():
    env = os.environ.copy()
    env['CLANG_MODULE_CACHE_PATH'] = str(ROOT / '.build/desktop-module-cache')
    env['SWIFTPM_MODULECACHE_OVERRIDE'] = env['CLANG_MODULE_CACHE_PATH']
    return env

def build(debug=False, mac_arch=None, prepare_assets=True):
    mode = 'debug' if debug else 'release'
    native_triple = next(line.split(': ', 1)[1] for line in subprocess.check_output(['rustc', '-vV'], text=True).splitlines() if line.startswith('host: '))
    triple = {'arm64': 'aarch64-apple-darwin', 'x86_64': 'x86_64-apple-darwin'}[mac_arch] if mac_arch else native_triple
    scratch = ROOT / (f'.build/desktop-worker-{mac_arch}' if mac_arch else '.build/desktop-worker')
    swift_command = ['swift', 'build', '--disable-sandbox', '--build-system', 'native', '--scratch-path', scratch, '-c', mode]
    if mac_arch:
        swift_command += ['--triple', f'{mac_arch}-apple-macosx13.3']
    run(swift_command + ['--product', 'FileMakerBridgeWorker'], env=environment())
    binary_dir = subprocess.check_output([str(a) for a in swift_command + ['--show-bin-path']], cwd=ROOT, env=environment(), text=True).strip()
    destination = ROOT / f'Desktop/src-tauri/binaries/FileMakerBridgeWorker-{triple}{".exe" if os.name == "nt" else ""}'
    shutil.copy2(Path(binary_dir) / WORKER, destination)
    if prepare_assets:
        prepare_frontend(Path(binary_dir) / WORKER)
    command = ['cargo', 'build', '--locked', '--offline', '--manifest-path', MANIFEST]
    if mac_arch: command += ['--target', triple]
    if not debug: command.append('--release')
    run(command, env={**os.environ, 'MACOSX_DEPLOYMENT_TARGET': '13.3'} if sys.platform == 'darwin' else None)
    target_dir = ROOT / 'Desktop/src-tauri/target'
    if mac_arch: target_dir /= triple
    return target_dir / mode / HOST, Path(binary_dir) / WORKER

def prepare_frontend(worker):
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
    hello = subprocess.run([str(worker)], input='{"op":"hello"}\n', capture_output=True, text=True, check=True)
    catalogue = json.loads(hello.stdout)['result']['catalogue']
    (ROOT / 'Desktop/web/assets/catalogue.json').write_text(json.dumps(catalogue, indent=2) + '\n')
    shutil.copy2(ROOT / 'LICENSE', ROOT / 'Desktop/web/assets/application-LICENSE.txt')

def build_universal(debug=False):
    if sys.platform != 'darwin': raise RuntimeError('Universal builds require macOS.')
    native = 'arm64' if subprocess.check_output(['uname', '-m'], text=True).strip() == 'arm64' else 'x86_64'
    other = 'x86_64' if native == 'arm64' else 'arm64'
    slices = [build(debug, native), build(debug, other, prepare_assets=False)]
    output = ROOT / '.build/desktop-universal' / ('debug' if debug else 'release')
    output.mkdir(parents=True, exist_ok=True)
    binaries = []
    for index, name in enumerate((HOST, WORKER)):
        binary = output / name
        run(['lipo', '-create', *(pair[index] for pair in slices), '-output', binary])
        architectures = subprocess.check_output(['lipo', '-archs', str(binary)], text=True).split()
        if set(architectures) != {'arm64', 'x86_64'}:
            raise RuntimeError(f'Universal binary has incorrect architectures: {binary}: {architectures}')
        binaries.append(binary)
    return tuple(binaries)

def project_source_archive(output, archive_name='project-source.tar.gz'):
    # Include the reviewed working source, with no build caches or FileMaker data.
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0')
    with tarfile.open(output / archive_name, 'w:gz') as archive:
        for raw in names:
            if not raw: continue
            name = os.fsdecode(raw)
            path = ROOT / name
            if path.is_file() and not path.is_symlink() and path.suffix.lower() != '.fmp12':
                archive.add(path, arcname='filemaker-script-bridge/' + name, recursive=False)

def source_archives(output):
    project_source_archive(output)
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
    previous_path = output / 'release-manifest.json'
    previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    files = [p for p in output.iterdir() if p.is_file() and p.name.endswith(('.zip', '.tar.gz', '.exe'))]
    manifest = {'version': VERSION, 'platform': sys.platform, 'architecture': subprocess.check_output(['rustc', '-vV'], text=True).split('host: ')[1].splitlines()[0], 'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
    if previous.get('sourceCommit'):
        manifest['sourceCommit'] = previous['sourceCommit']
    windows_receipt = output / 'windows-build-receipt.json'
    if windows_receipt.is_file():
        manifest['windows'] = json.loads(windows_receipt.read_text())
    universal_receipt = output / 'macos-universal-build-receipt.json'
    if universal_receipt.is_file():
        manifest['macosUniversal'] = json.loads(universal_receipt.read_text())
    (output / 'release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def package(host, worker, include_sources=True, universal=False):
    # dist contains launchable deliverables only. Keep release records, source
    # archives and intermediate Windows packages in the build area.
    output = ROOT / '.build/releases' / VERSION
    output.mkdir(parents=True, exist_ok=True)
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    if sys.platform == 'darwin':
        app = dist / ('Script Bridge Universal.app' if universal else 'Script Bridge.app')
        if app.exists(): shutil.rmtree(app)
        contents = app / 'Contents'
        (contents / 'MacOS').mkdir(parents=True)
        resources = contents / 'Resources'; resources.mkdir()
        shutil.copy2(host, contents / 'MacOS/FileMakerScriptBridge')
        shutil.copy2(worker, contents / 'MacOS/FileMakerBridgeWorker')
        mac_build = UNIVERSAL_MAC_BUILD if universal else MAC_BUILD
        icon_name = f'AppIcon-{mac_build}'
        shutil.copy2(ROOT / 'Resources/AppIcon.icns', resources / f'{icon_name}.icns')
        for name in ['LICENSE', 'NOTICE.txt']: shutil.copy2(ROOT / name, resources / name)
        native_target = 'macos-arm64' if subprocess.check_output(['uname', '-m'], text=True).strip() == 'arm64' else 'macos-x64'
        for target in (('macos-arm64', 'macos-x64') if universal else (native_target,)):
            runtime = ROOT / '.build/ai-runtime' / target
            if not (runtime / 'llama-server').is_file(): raise RuntimeError(f'Prepare the pinned {target} AI runtime before packaging.')
            destination = resources / 'ai-runtime' / target if universal else resources / 'ai-runtime'
            shutil.copytree(runtime, destination, symlinks=False)
        for binary in (resources / 'ai-runtime').rglob('*'):
            if binary.suffix == '.dylib' or binary.name == 'llama-server':
                run(['codesign', '--force', '--sign', '-', binary])
        shutil.copy2(ROOT / 'Desktop/web/assets/notices.json', resources / 'component-notices.json')
        info = dict(CFBundleName='Script Bridge', CFBundleDisplayName='Script Bridge', CFBundleIdentifier='com.sckc.filemaker-script-bridge', CFBundleExecutable='FileMakerScriptBridge', CFBundlePackageType='APPL', CFBundleShortVersionString=VERSION, CFBundleVersion=mac_build, CFBundleIconFile=f'{icon_name}.icns', LSMinimumSystemVersion='13.3', NSHighResolutionCapable=True, LSApplicationCategoryType='public.app-category.developer-tools', NSHumanReadableCopyright='Copyright © 2026 SCKC. GPL-3.0-or-later.')
        (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
        run(['codesign', '--force', '--sign', '-', contents / 'MacOS/FileMakerBridgeWorker'])
        run(['codesign', '--force', '--sign', '-', app])
        run(['codesign', '--verify', '--deep', '--strict', app])
        if universal:
            spec = importlib.util.spec_from_file_location('audit_macos', ROOT / 'Scripts/audit-macos.py')
            auditor = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(auditor)
            receipt = auditor.audit(app)
        archive = output / ('Script-Bridge-macOS-Universal.zip' if universal else 'Script-Bridge-macOS.zip')
        if archive.exists(): archive.unlink()
        run(['/usr/bin/ditto', '-c', '-k', '--keepParent', '--norsrc', app, archive])
        if universal:
            receipt.update(file=archive.name, bytes=archive.stat().st_size,
                           sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                           intelHardwareTested=False, notarized=False,
                           sourceArchive='project-source-universal.tar.gz',
                           sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
            (output / 'macos-universal-build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
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
    if include_sources and universal:
        # Add matching universal source while retaining the original release's
        # ARM-only source archive and the unchanged shared dependency sources.
        for name in ('component-sources.tar.gz', 'frontend-runtime-source.tar.gz', 'inference-runtime-source.tar.gz'):
            if not (output / name).is_file(): raise RuntimeError(f'Shared release source archive missing: {name}')
        project_source_archive(output, 'project-source-universal.tar.gz')
    elif include_sources:
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
    parser.add_argument('--universal', action='store_true', help='Build both Mac architectures; package alongside the native app.')
    args = parser.parse_args()
    host, worker = build_universal(args.debug) if args.universal else build(args.debug)
    if args.action == 'run':
        # The host discovers its packaged worker beside itself.
        shutil.copy2(worker, host.parent / WORKER)
        run([host])
    elif args.action == 'package': package(host, worker, universal=args.universal)
