# Windows x64 build — 1.1.0

The Windows app uses the same `Desktop/web/` assets as macOS. The Rust host, Swift conversion worker and llama.cpp runtime are native x64 Windows binaries. `dist/Script Bridge.exe` is a per-user installer, not the bare application executable. It installs the app, its DLLs and an uninstaller; users do not need a Swift installation. Setup downloads Microsoft WebView2 from Microsoft if it is missing. Model weights remain optional downloads.

The current installer was cross-compiled on macOS. Native Windows installation, display, FileMaker copy/paste and AI inference require acceptance testing. The package is unsigned. Windows inference currently uses the portable CPU runtime; macOS uses Metal. This affects speed, not the shared interface.

## Pinned cross-build inputs

Use a matching Swift compiler and Windows SDK. Apple's system Swift cannot load the Swift.org Windows binary modules. Save the following downloads in `.build/` under the indicated names. Their SHA-256 pins are checked by `Scripts/prepare-windows-toolchain.py`.

| File | Official source | SHA-256 |
| --- | --- | --- |
| `swift-6.4.0-windows.exe` | https://download.swift.org/swift-6.4.0-release/windows10/swift-6.4.0-RELEASE/swift-6.4.0-RELEASE-windows10.exe | `76169a85bcba82854a0cd8f9655ffb74b3758d60c35a245457510095f2823c03` |
| `swift-6.4.0-macos.pkg` | https://download.swift.org/swift-6.4.0-release/xcode/swift-6.4.0-RELEASE/swift-6.4.0-RELEASE-osx.pkg | `8fd03185b98fe27f54a54631c2449decf75d5b466ce8e34abbd414141063c6aa` |
| `7z2604-mac.tar.xz` | https://github.com/ip7z/7zip/releases/download/26.04/7z2604-mac.tar.xz | `bee04358cbcbc7106273cee0e8d72916db2696c48067a3538c34d8cd6fd16578` |

Extract the pinned 7-Zip tarball to `.build/7zip/`. Install Rust's `x86_64-pc-windows-msvc` target, cargo-xwin, LLVM/lld 20.1.8 and NSIS 3.13. Set `BRIDGE_WINDOWS_LLVM` to the LLVM `bin` directory. Ensure `lld-link` and `llvm-rc` are on PATH. Populate `.build/xwin-cache/xwin/{crt,sdk}` using cargo-xwin's Microsoft VC 14.44 / Windows SDK 10.0.26100 inputs. These are compiler inputs, never redistributed with the app.

```sh
python3 Scripts/prepare-windows-toolchain.py
python3 Scripts/build-windows-worker.py --typecheck
python3 Scripts/build-windows-worker.py
```

Preparation extracts the Mac compiler without installing it, verifies the selected Windows installer payloads against their SHA-512 Burn manifest and reconstructs the SDK/runtime file names from MSI tables. Only copies under `.build/swift-windows-headers` are adapted: SDK 26100 supplies math via `math.h`; matching Clang standard headers provide `stdalign.h` and `stdnoreturn.h`. Warning wrapper macros accommodate the newer MSVC `threads.h`; these affect diagnostics only. No system or external project headers are changed.

Prepare notices and the pinned Windows inference runtime before embedding the frontend:

```sh
python3 Scripts/collect-desktop-notices.py
python3 Scripts/prepare-ai-runtime.py --fetch --target windows-x64
python3 Scripts/collect-ai-notices.py
python3 Scripts/collect-platform-notices.py
python3 Scripts/collect-pdf-notices.py
```

The platform notice originals and their provenance are checked in. `fetch-platform-notices.py` is a maintainer tool for refreshing them, not an offline build requirement. The Swift packages are obtained from the URLs above and checked against the recorded hashes; code-signature verification of those toolchain downloads was not established during this cross-build.

```sh
XWIN_CACHE_DIR="$PWD/.build/xwin-cache" \
TAURI_CONFIG='{"bundle":{"externalBin":[]}}' \
RUSTFLAGS='-C target-feature=+crt-static' \
cargo xwin rustc --offline --locked --release \
  --manifest-path Desktop/src-tauri/Cargo.toml \
  --target x86_64-pc-windows-msvc -- \
  -C "link-arg=$PWD/.build/xwin-cache/xwin/sdk/lib/ucrt/x86_64/libucrt.lib" \
  -C "link-arg=$PWD/.build/xwin-cache/xwin/crt/lib/x86_64/libvcruntime.lib" \
  -C "link-arg=$PWD/.build/xwin-cache/xwin/crt/lib/x86_64/libcpmt.lib"
```

The explicit static CRT inputs resolve WebView2's static loader dependencies. `externalBin` is suppressed during cross-linking because the installer stages the cross-compiled worker itself.

Save Microsoft's WebView2 bootstrapper as `.build/MicrosoftEdgeWebview2Setup.exe` from https://go.microsoft.com/fwlink/p/?LinkId=2124703. The installer builder checks its recorded SHA-256 `f414de01c4680f0bb0694d1ea7803c6968f3a81bf6bad01b89bfc65dce14c2a2`; review changed upstream content before changing that pin.

```sh
python3 Scripts/package-windows.py
```

Packaging checks every staged app/runtime EXE and DLL is AMD64 PE32+, resolves regular and delayed imports recursively, and fails for missing non-system dependencies. It includes the required Swift/Foundation/ICU and Microsoft VC redistributable DLLs, their original licence texts, the app licence and full component inventory. The zlib-compressed NSIS installer creates a Start menu shortcut and registered uninstaller without requiring administrator rights. Uninstall removes package-owned files and retains model data; use Remove model in the playground to reclaim models.

Staging, file hashes, the dependency audit and build receipt are retained in `.build/releases/1.1.0/`; only the final `.exe` is placed in `dist`. Build matching source archives with the desktop packager when distributing a release. The Mac build writes its `.app` beside the installer and source archives outside `dist`.

## Windows acceptance

1. Install on x64 Windows 10/11, launch from Start, check the purple icon, navigation order, themes, resizing and About/licences.
2. Load the workspace example. Choose Copy to FileMaker, select an insertion point in a test solution's Script Workspace, and press Ctrl+V. Verify steps, values and calculations.
3. Copy native steps in FileMaker. Use FileMaker → Text in the bridge. Check round trips with non-ASCII text, multiline calculations, Smart Fix and locked preserved steps in the same session.
4. Check invalid scripts block export. Confirm template comments and strict mode behave as described in the guide.
5. Optionally select a Qwen model and test download/cancel/resume, generation, review, unloading and removal. Check the inference process exits with the app.
6. Test uninstall and reinstall, including a machine without WebView2. Record Windows and FileMaker versions and actual results before a public Windows release.
