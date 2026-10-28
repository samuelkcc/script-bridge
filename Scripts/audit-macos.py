#!/usr/bin/env python3
"""Audit a universal app's slices, runtime dependencies and deployment targets."""
import argparse
import json
from pathlib import Path
import plistlib
import re
import subprocess


def output(*args):
    return subprocess.check_output([str(arg) for arg in args], text=True)


def audit(app):
    app = Path(app).resolve()
    contents = app / 'Contents'
    info = plistlib.loads((contents / 'Info.plist').read_bytes())
    expected = {
        contents / 'MacOS/FileMakerScriptBridge': {'arm64', 'x86_64'},
        contents / 'MacOS/FileMakerBridgeWorker': {'arm64', 'x86_64'},
    }
    for target, arch in [('macos-arm64', 'arm64'), ('macos-x64', 'x86_64')]:
        runtime = contents / 'Resources/ai-runtime' / target
        if not (runtime / 'llama-server').is_file():
            raise RuntimeError(f'Missing {target} inference server')
        for path in runtime.iterdir():
            if path.name == 'llama-server' or path.suffix == '.dylib':
                expected[path] = {arch}
    checked = {}
    minimum = tuple(map(int, info['LSMinimumSystemVersion'].split('.')))
    for path, architectures in expected.items():
        actual = set(output('lipo', '-archs', path).strip().split())
        if actual != architectures:
            raise RuntimeError(f'Wrong architectures for {path}: {actual}')
        for arch in sorted(architectures):
            loads = output('otool', '-arch', arch, '-l', path)
            match = re.search(r'^\s+(?:minos|version) (\d+\.\d+(?:\.\d+)?)\s*$', loads, re.MULTILINE)
            if not match:
                raise RuntimeError(f'Missing deployment target for {path} ({arch})')
            target = tuple(map(int, match[1].split('.')))
            if target + (0,) * (3-len(target)) > minimum + (0,) * (3-len(minimum)):
                raise RuntimeError(f'{path} requires macOS {match[1]}, above the advertised minimum')
            for line in output('otool', '-arch', arch, '-L', path).splitlines():
                if not line.startswith('\t'): continue
                dependency = line.strip().split(' (', 1)[0]
                if dependency.startswith(('/usr/lib/', '/System/Library/')): continue
                if dependency.startswith(('@rpath/', '@loader_path/')):
                    candidate = path.parent / dependency.split('/', 1)[1]
                    if candidate.is_file():
                        if arch not in output('lipo', '-archs', candidate).split():
                            raise RuntimeError(f'{path.name} needs a missing {arch} dependency: {dependency}')
                        continue
                raise RuntimeError(f'Unresolved non-system dependency for {path}: {dependency}')
        checked[path.relative_to(app).as_posix()] = sorted(architectures)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    return {'version': info['CFBundleShortVersionString'], 'build': info['CFBundleVersion'],
            'architectures': ['arm64', 'x86_64'], 'minimumMacOS': info['LSMinimumSystemVersion'],
            'auditedMachOFiles': len(checked), 'files': checked}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    print(json.dumps(audit(parser.parse_args().app), indent=2))
