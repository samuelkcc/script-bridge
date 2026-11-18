# Recovery and disk housekeeping

Audited on 18 November 2026. This guide concerns the current Tauri desktop app.
Keep the older SwiftUI source for maintenance, but use `Scripts/desktop.py` for
the current release. See also [architecture](DESKTOP_ARCHITECTURE.md) and the
[Windows build guide](WINDOWS_BUILD.md).

## What must be kept

- `Sources/`, `Desktop/`, `Tests/`, `Resources/`, `Scripts/`, `Documentation/`,
  `Package.swift`, the root documentation and licence files, and `.github/`.
- `Desktop/src-tauri/Cargo.lock`: the exact Rust dependency versions.
- The checked-in PDF.js JavaScript, worker, fonts and CMaps under
  `Desktop/web/vendor/pdfjs/`; the application uses these assets at runtime.
- `Desktop/ai/catalogue.json`, component provenance and original notices:
  these pin inference runtime, model and PDF-reader source downloads.
- Git history and release tags, normally recovered by cloning GitHub.

The GitHub repository is <https://github.com/samuelkcc/script-bridge>.
At the audit, local `main` and live GitHub `main` both pointed to
`9a229094b943fb7e5ec6c021bcf9ee393ee7e20f`. The project has no Git LFS assets
or submodules requiring a second source checkout. A clean Git status alone does
not cover ignored files or unfinished work in another worktree.

## Restore the current app on a new Mac

1. Install Xcode with Command Line Tools, Rust with Cargo, Python 3.12 or later,
   and Node.js for the JavaScript tests. The recovery check used Swift 6.4.2,
   Rust/Cargo 1.97.0, Python 3.14.7 and Node.js 26.7.0 on Apple Silicon.
2. Clone the repository. In GitHub Desktop, use **File → Clone Repository**,
   select `samuelkcc/script-bridge`, and choose a local development folder.
   The local folder name does not have to match the GitHub repository name.
3. In a terminal inside the cloned repository, run:

```sh
mkdir -p .build
cargo fetch --locked --manifest-path Desktop/src-tauri/Cargo.toml
python3 Scripts/prepare-ai-runtime.py --fetch
python3 Scripts/prepare-pdf-sources.py --download
python3 Scripts/desktop.py package
```

This rebuilds the Swift worker, generates component notices and frontend data,
builds the Rust host, and packages `dist/Script Bridge.app`. It also writes
matching source archives and release checksums into `.build/releases/1.1.0/`
(the version comes from `Desktop/src-tauri/Cargo.toml`). No AI model is required
to build or use script conversion.

The recovery audit reproduced a macOS 27 release-build failure caused by stripped
Rust compiler-plugin libraries (`E0463` / `mis-aligned LINKEDIT string pool`).
`Desktop/src-tauri/Cargo.toml` now disables stripping for compile-time build
dependencies only, while retaining stripping for the shipped application.
See the [Rust issue](https://github.com/rust-lang/rust/issues/157750) and
[Cargo build profile documentation](https://doc.rust-lang.org/cargo/reference/profiles.html#build-dependencies).

Build the worker/frontend before running Rust tests: Tauri checks the generated
worker binary during its build. After packaging, verify:

```sh
CLANG_MODULE_CACHE_PATH="$PWD/.build/test-module-cache" \
SWIFTPM_MODULECACHE_OVERRIDE="$PWD/.build/test-module-cache" \
swift test --disable-sandbox --scratch-path .build/desktop-tests
BRIDGE_TEST_WORKER="$PWD/.build/desktop-worker/release/FileMakerBridgeWorker" \
node --test Desktop/tests/*.test.mjs
cargo test --locked --offline --manifest-path Desktop/src-tauri/Cargo.toml
```

For a universal Mac edition, install both Rust targets, fetch the other runtime,
and build the native package above first (it creates the shared source archives):

```sh
rustup target add aarch64-apple-darwin x86_64-apple-darwin
python3 Scripts/prepare-ai-runtime.py --fetch --target macos-x64
python3 Scripts/prepare-ai-runtime.py --fetch --target macos-arm64
python3 Scripts/desktop.py package --universal
```

See `WINDOWS_BUILD.md` for Windows and Mac-to-Windows cross-builds. The old local
cross-build had `.build/xwin-cache/xwin/{crt,sdk}` symlinked into another project's
build cache, and its LLVM fallback pointed into `~/.local/opt/hpi-windows-toolchain/`.
Neither location comes from cloning this repository. Recreate the SDK cache as
documented and set `BRIDGE_WINDOWS_LLVM` to the installed LLVM `bin` directory;
do not rely on those old machine-specific links. Compiler installers and
extracted SDKs are toolchain inputs, not application source assets.

## Local recovery kit and published releases

`Recovery/` is deliberately ignored by Git. The housekeeping operation created:

- `project-history.bundle`: Git history and refs, including the older worktree
  base. Check with `git bundle verify Recovery/project-history.bundle`.
- `work-in-progress-c6b2.tar.gz`: a full source snapshot of the older detached
  Codex worktree, including its new `DataAndURLStepTests.swift` file.
- Its base commit, status and binary patch. The patch covers tracked edits;
  restore the full archive to include the untracked test.
- `cargo-locked-sources.tar.gz`: all 442 locked registry crates, checked against
  `Cargo.lock`. This is source storage, not a preconfigured offline Cargo cache;
  a normal new-machine build still runs `cargo fetch` to establish the cache/index.
- The historical handover, cleanup receipt, checksums and verification records.

To restore local history without GitHub, clone the bundle into a new directory:

```sh
git clone Recovery/project-history.bundle recovered-script-bridge
```

Extract the WIP archive into a **separate** directory to inspect unfinished work.
It was based on `c3926d049c98583d32802b7d22b4740226d3a05e`, predates the current
desktop release, and must be reviewed before merging. The original worktree was
left intact. A local recovery kit protects against accidental edits, but a copy
on the same computer does not protect against losing that computer.

The [1.1.0 GitHub release](https://github.com/samuelkcc/script-bridge/releases/tag/v1.1.0)
contains the Mac and Windows packages, project source archives, Rust component
sources, inference runtime source, PDF-reader source, build receipts and checksums.
The local `.build/releases/1.1.0/` archives were retained. The compact local
`Recovery/` kit and any private QA material need a separate off-computer backup.
Private PDF fixtures, generated business scripts and FileMaker databases are not
required to compile the application and must not be added to the public repository.

## What can be cleaned

The project folder fell from approximately **29.2 GB to 1.22 GB** (decimal disk
units), reclaiming approximately **28.0 GB**. The retained total includes the
local recovery kit, launchable apps and release/dependency source archives.

The large items removed during this audit were optional AI QA model weights,
Swift and Rust build products, compiler/module caches, extracted Windows SDK and
Swift toolchains, downloadable compiler installers, duplicate staging apps and
the duplicate Windows installer payload directory. Rebuilding recreates outputs;
compiler installers and optional models can be downloaded from their pinned sources.

Retained: all project source and documentation, the historical handover, icons,
vendored PDF assets, local dependency source archives, release archives and
receipts, launchable `dist/` apps/installer, small QA results/screenshots, and the
separate `.build/website-update` Git checkout. Small QA evidence may contain
private material and remains local.

Do not indiscriminately delete `.build/`: this project also used it for release
source archives, QA evidence and a separate website checkout. Audit its contents
before future cleanups. `Recovery/cleanup-plan-2026-11-18.json` records the exact
allowlist used for this cleanup, and the receipt records the space reclaimed.

## GitHub Desktop backup habit

GitHub Desktop recognised this project as `script-bridge`, with the local worktree
`sam-filemaker-script-bridge`, branch `main`, and no changes before housekeeping.
The remote URL and branch tracking were correct; a separate clone from GitHub
confirmed access to the published source. The Desktop UI check did not test a new
push. A terminal `git push --dry-run` to a proposed `codex/recovery-2026-11-18`
branch succeeded, confirming current push access without creating that branch.
Authentication on a replacement computer must still be established separately.

After each maintenance session, review changes, commit them, then **Push origin**.
**Fetch origin** only downloads remote updates. Check GitHub's latest commit and
keep private fixtures/backups separately. Review `git worktree list` too: changes
in another worktree do not appear in the selected worktree's Changes list.
The existing GitHub Actions workflow is manually triggered; it is not an automatic
backup and does not run on every push. Keeping GitHub Desktop installed alone does
not upload changed files.

## Recovery verification on 18 November 2026

A separate clone was downloaded directly from GitHub. Its Swift tests passed
**107/107**, JavaScript/worker tests **9/9**, and Rust tests **12/12** (three
optional model/network integration tests remained ignored). After applying only
the Cargo build-profile fix described above, a complete Apple Silicon release
build and package succeeded, including generated notices, dependency source
archives and strict deep code-signature verification. The pinned inference runtime
was downloaded afresh and checked; the PDF-reader source archives were restored
from the retained local copies and checked against their recorded hashes.

All **12** retained 1.1.0 release assets matched the live GitHub release sizes and
SHA-256 digests. Both retained Mac apps passed signature verification; the retained
universal app also passed its architecture/dependency audit. This session did not
rebuild Windows or the universal edition, run model inference, or perform a live
FileMaker paste test. Logs and audit receipts are kept locally in `Recovery/`.
