#!/usr/bin/env python3
"""Regenerate PNG, macOS ICNS and Windows ICO from the original purple mark."""
from pathlib import Path
import os, shutil, struct, subprocess
ROOT = Path(__file__).resolve().parents[1]
stage = ROOT / '.build/app-icons'
stage.mkdir(parents=True, exist_ok=True)
png = ROOT / 'Resources/AppIcon.png'
env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(ROOT / '.build/desktop-module-cache'), SWIFTPM_MODULECACHE_OVERRIDE=str(ROOT / '.build/desktop-module-cache'))
subprocess.run(['swift', ROOT / 'Scripts/DrawAppIcon.swift', png], check=True, env=env)
iconset = stage / 'AppIcon.iconset'
iconset.mkdir(exist_ok=True)
for base in [16, 32, 128, 256, 512]:
    for retina in [False, True]:
        size = base * (2 if retina else 1)
        dest = iconset / f'icon_{base}x{base}{"@2x" if retina else ""}.png'
        subprocess.run(['sips', '-z', str(size), str(size), png, '--out', dest], check=True, stdout=subprocess.DEVNULL)
# Use Apple's complete icon representations and metadata. A hand-written ICNS
# may decode as an image while Finder still displays a generic application icon.
# iconutil needs access to macOS image services; do not substitute a container
# if a restricted build environment prevents it from running.
subprocess.run(['/usr/bin/iconutil', '-c', 'icns', iconset, '-o', ROOT / 'Resources/AppIcon.icns'], check=True)
icons = ROOT / 'Desktop/src-tauri/icons'
shutil.copy2(png, icons / 'icon.png')
shutil.copy2(ROOT / 'Resources/AppIcon.icns', icons / 'icon.icns')
images = []
for size in [16, 24, 32, 48, 64, 128, 256]:
    dest = stage / f'windows-{size}.png'
    subprocess.run(['sips', '-z', str(size), str(size), png, '--out', dest], check=True, stdout=subprocess.DEVNULL)
    images.append((size, dest.read_bytes()))
offset = 6 + 16 * len(images)
directory = bytearray(struct.pack('<HHH', 0, 1, len(images)))
for size, data in images:
    directory.extend(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
    offset += len(data)
(icons / 'icon.ico').write_bytes(directory + b''.join(data for _, data in images))
print('Updated macOS, Windows and PNG app icons.')
