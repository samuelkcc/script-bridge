#!/usr/bin/env python3
"""Bundle exact offline Cargo component texts; fail rather than omit a notice."""
import hashlib
import subprocess
import json
import os
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'Desktop/src-tauri/Cargo.lock'
REGISTRY = Path(os.environ.get('CARGO_HOME', Path.home() / '.cargo')) / 'registry/src'
entries = []
missing = []
needed = set()
for target in ('aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-pc-windows-msvc'):
    tree = subprocess.check_output(['cargo', 'tree', '--manifest-path', str(ROOT / 'Desktop/src-tauri/Cargo.toml'), '--offline', '--locked', '--target', target, '--prefix', 'none', '--format', '{p}'], text=True)
    for line in tree.splitlines():
        match = re.match(r'([\w-]+) v([^ ]+)', line)
        if match: needed.add(match.groups())
for package in tomllib.loads(LOCK.read_text())['package']:
    if not package.get('source', '').startswith('registry+'):
        continue
    name, version = package['name'], package['version']
    if (name, version) not in needed: continue
    folders = list(REGISTRY.glob(f'*/{name}-{version}'))
    if not folders:
        missing.append(f'{name} {version}: package source is not cached')
        continue
    folder = folders[0]
    manifest = tomllib.loads((folder / 'Cargo.toml').read_text())['package']
    files = []
    if manifest.get('license-file'):
        f = folder / manifest['license-file']
        if f.is_file(): files.append(f)
    for f in sorted(folder.iterdir()):
        if f.is_file() and re.match(r'(?i)^(licen[sc]e|copying|copyright|notice)([.\-_]|$)', f.name):
            files.append(f)
        elif f.is_dir() and f.name.lower() in ('licenses', 'licences'):
            files.extend(sorted(p for p in f.rglob('*') if p.is_file()))
    files = list(dict.fromkeys(files))
    supplemental = ROOT / 'Desktop/notices' / f'{name}-{version}'
    provenance = None
    if not files and (supplemental / 'SOURCE.json').is_file():
        provenance = json.loads((supplemental / 'SOURCE.json').read_text())
        vcs = json.loads((folder / '.cargo_vcs_info.json').read_text())
        if provenance['crate'] != name or provenance['version'] != version or provenance['revision'] != vcs['git']['sha1']:
            raise SystemExit(f'Supplemental notice revision mismatch: {name} {version}')
        for record in provenance['sources']:
            f = supplemental / record['file']
            if hashlib.sha256(f.read_bytes()).hexdigest() != record['sha256']:
                raise SystemExit(f'Supplemental notice checksum mismatch: {f}')
            files.append(f)
    if not files:
        missing.append(f'{name} {version}: no original licence text found')
        continue
    text = '\n\n'.join(f'--- {f.name} ---\n{f.read_text(errors="replace")}' for f in files)
    entries.append({'name': name, 'version': version, 'license': manifest.get('license', 'See original text'),
                    'repository': manifest.get('repository', f'https://crates.io/crates/{name}/{version}'), 'provenance': provenance, 'text': text})
if missing:
    raise SystemExit('Cannot package incomplete notices:\n' + '\n'.join(missing))
# System Swift runtime is supplied by macOS. Windows preview requires the user's
# official Swift runtime/toolchain; it is not silently copied into this inventory.
output = ROOT / 'Desktop/web/assets/notices.json'
output.write_text(json.dumps({'schema': 1, 'scope': 'Cargo.lock active macOS (arm64/Intel) and Windows x64 dependencies, including build tools',
                             'entries': sorted(entries, key=lambda p: (p['name'], p['version']))}, ensure_ascii=False, indent=2) + '\n')
print(f'Bundled {len(entries)} original component notice entries: {output}')
