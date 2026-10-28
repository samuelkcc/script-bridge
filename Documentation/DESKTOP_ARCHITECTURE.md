# Shared desktop architecture — 1.1.0

The desktop app adopts the approach inspected in AniCanto's current `studio/`: a shared HTML/CSS/JavaScript interface in a Tauri 2 Rust host. Its welcome screen, navigation, themed panels, About drawer and searchable offline licence viewer informed this design. No AniCanto application code, models, fonts or artwork are incorporated.

## Structure

| Location | Responsibility |
| --- | --- |
| `Desktop/web/` | Shared welcome, workspace, reference, guide, About, light/dark/system appearance and accessible review drawers |
| `Desktop/src-tauri/src/main.rs` | Fixed desktop operations, validation before clipboard writes, external HTTPS links |
| `Desktop/src-tauri/src/clipboard.rs` | Native macOS pasteboard and Windows clipboard implementations |
| `Desktop/src-tauri/src/ai.rs` | Pinned model downloads, resumable verified files, authenticated loopback inference, cancellation and model lifecycle |
| `Desktop/src-tauri/src/knowledge.rs` | Retrieval of bundled syntax sections, grounded generation rules and script-only output cleanup |
| `Desktop/ai/catalogue.json` | Exact Qwen and llama.cpp versions, sources, hashes and licence metadata |
| `Desktop/src-tauri/src/codec.rs` | Bounded XML decoding and Windows FileMaker length-prefix encoding |
| `Desktop/src-tauri/src/worker.rs` | Persistent worker lifecycle, protocol handshake, timeout and session failure handling |
| `Sources/FileMakerBridgeWorker/` | Versioned JSON-lines interface to the existing Swift engine; session preservation and Smart Fix state |
| `Sources/FileMakerBridgeCore/` | Existing parser, compiler, decompiler, step catalogue and Smart Fix implementation |
| `Sources/FileMakerScriptBridgeApp/` | Retained SwiftUI app and existing release path |
| `Desktop/notices/` | Original dependency notices omitted from published crates, with pinned revision/checksum provenance |
| `Scripts/desktop.py` | Native build, run, signed Mac/Windows developer packaging and matching source archives |
| `Scripts/collect-desktop-notices.py` | Fail-closed offline inventory for active macOS arm64/Intel and Windows x64 dependencies |

The frontend has no npm runtime dependencies or build framework. System fonts and original SVG symbols keep the bundle small. Tauri uses the system webview: WKWebView on macOS and WebView2 on Windows. See [Tauri architecture](https://v2.tauri.app/concept/architecture/).

## Platform status

| Item | macOS | Windows x64 |
| --- | --- | --- |
| Shared interface | Running and visually checked | Same bundled interface; native display needs Windows verification |
| Rust host | Built locally | Native x64 PE executable cross-linked on macOS; native execution pending |
| Swift conversion worker | Built and exercised locally | Native x64 PE worker cross-compiled with matching Swift 6.4 SDK; runtime acceptance pending |
| Native clipboard | macOS aliases retained in Rust | `Mac-XMSS`/`Mac-XMSC` implementation, four-byte little-endian length prefix |
| FileMaker acceptance | Existing engine/native XML evidence retained; new shell needs manual FileMaker acceptance | Requires real Windows FileMaker copy/paste captures and acceptance |
| Packaging | Separate Apple Silicon and universal (Apple Silicon + Intel) apps and ZIPs; ad-hoc signed | Per-user x64 installer includes required runtime DLLs; setup installs WebView2 if missing |

The current desktop has separate **Apple Silicon-only** and **universal** downloads. The universal host and Swift conversion worker each contain `arm64` and `x86_64` slices. Its official, pinned inference runtimes remain intact in `Resources/ai-runtime/macos-arm64` and `macos-x64`; the host selects its compiled architecture. Apple Silicon uses Metal; Intel uses CPU inference. Flat runtime directories remain supported by the Apple Silicon-only and Windows packages. Intel hardware and FileMaker acceptance testing remain pending.

The desktop edition retains the original `com.sckc.filemaker-script-bridge` application identity when replacing the old app, including its macOS bundle identifier and Tauri per-user data namespace.

Windows has a distinct clipboard transport. It cannot use macOS pasteboard aliases or raw XML alone. The Windows encoder writes the UTF-8 byte length (not character count) before XML, and registers `Mac-XMSS`. Reads accept `Mac-XMSS` and `Mac-XMSC`, bound the allocation and declared length, and decode only the declared payload. The format evidence comes from [Daniel Smith's original FileMaker clipboard converter](https://github.com/dansmith65/FileMaker-PowerShell-Clipboard/blob/master/Convert-FMClip.ps1); no converter source was copied. Native acceptance is still necessary for the intended FileMaker versions.

## Why retain Swift while adopting Rust?

**Use Rust for the desktop host and operating-system integration now. Retain the tested Swift engine until a measured bottleneck or distribution requirement justifies a complete port.**

Both Swift and Rust compile to native machine code. Rewriting in Rust does not by itself demonstrate a performance improvement. The engine contains over 4,000 lines of parser/compiler/decompiler logic, 98 editable subsets, multiline calculations, option defaults and preservation rules backed by real FileMaker captures. A wholesale rewrite risks losing those details.

A local debug-worker measurement on 20 October 2026, including JSON IPC, compiled 100 repeated Set Variable steps at a median **6.85 ms**, and 1,000 steps at **70.35 ms** (ten measured calls after two warmups; no clipboard access). These are synthetic measurements on this Mac, not a cross-language benchmark or a general performance guarantee. The frontend's 240 ms debounce avoids conversion on every keystroke, and Rust dispatches conversion outside the UI thread.

Rust's clearest future benefit here is simpler Windows distribution without a separate Swift runtime. A complete Rust engine is feasible, but should be a separate migration with a strict parity gate:

1. Export golden text/native XML/diagnostic fixtures from every existing supported option profile.
2. Compare Swift and Rust compile/decompile results structurally, including Unicode, CDATA, multiline calculations, TODO counts and error locations.
3. Preserve opaque XML and session-bound markers, stale-review rejection and strict-mode blocking.
4. Run native FileMaker acceptance on both platforms for every changed family.
5. Benchmark startup, large-script latency, memory and final package size before switching the default engine.

Until then, the persistent worker uses a protocol-1 handshake and preserves opaque steps only in its process memory. A crash or 30-second timeout ends the conversion session and asks for a restart/re-import. It does not silently restart and discard preserved XML. The host recompiles the latest source before every native clipboard export; it never trusts webview-provided XML or a `canCopy` flag.

## Build and run

Install Rust/Cargo, Node.js 22+ for tests, Python 3.12+ for packaging scripts, and Swift 6+. On Windows, use the [official Swift installation instructions](https://www.swift.org/install/windows/), including Visual Studio C++/Windows SDK dependencies. WebView2 must be available. No web server is used by the packaged app.

```sh
# Fetch locked Rust packages once, with network access.
cargo fetch --locked --manifest-path Desktop/src-tauri/Cargo.toml
python3 Scripts/prepare-ai-runtime.py --fetch

# Build and run the shared interface with a persistent native worker.
python3 Scripts/desktop.py run --debug

# Native release build + matching source archives.
python3 Scripts/desktop.py package

# Additional universal Mac package; retain the native-only app and ZIP.
rustup target add aarch64-apple-darwin x86_64-apple-darwin
python3 Scripts/prepare-ai-runtime.py --fetch --target macos-arm64
python3 Scripts/prepare-ai-runtime.py --fetch --target macos-x64
python3 Scripts/desktop.py package --universal
python3 Scripts/audit-macos.py "dist/Script Bridge Universal.app"
```

Without `--universal`, the commands build for the current host architecture. The universal option builds both architectures with a macOS 13.3 deployment target and merges the host and worker using `lipo`. Packaging audits the slices, deployment targets, runtime dependency closure and bundle signature before writing `Script-Bridge-macOS-Universal.zip` and `macos-universal-build-receipt.json`. `Desktop/package.json` offers equivalent native `npm run dev` / `npm run build` wrappers; npm install is unnecessary. `npm run preview` serves the layout for design inspection only, with clipboard and conversion unavailable.

For restricted Mac environments, the script directs Swift module caches into `.build/`. If the selected Command Line Tools cannot run XCTest or SwiftUI plugins, select a working Xcode installation, for example `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`. `BRIDGE_MACOS_SDK` and `BRIDGE_BUILD_SYSTEM` remain options on the original SwiftUI packaging script only.

On Windows the developer ZIP contains the Rust EXE and conversion worker. It deliberately does not claim to be standalone: install the official Swift toolchain/runtime and ensure its DLL directories are on PATH. A consumer installer must bundle a verified matching runtime set and its notices before this requirement can be removed. The Windows package is unsigned; the Mac app is ad-hoc signed and not notarized. No public release is published by these scripts.

## Verification

```sh
swift test --disable-sandbox --scratch-path .build/desktop-tests
node --test Desktop/tests/*.test.mjs
cargo test --locked --offline --manifest-path Desktop/src-tauri/Cargo.toml
```

Build the debug worker first. `BRIDGE_TEST_WORKER` may point the integration test to a release worker or a Windows build location. Integration tests fail if the specified worker is missing.

Local results: **100 core Swift tests + 7 SwiftUI model tests**, **5 JavaScript/worker tests**, **10 Rust host/knowledge/codec tests**. Two separately gated integration tests check resumed downloads and checksum rejection, and actual Qwen 9B generation of dialog and XLSX-export scripts through strict validation. The 35B model has not been inference-tested. Windows-target type checking passes. Cross-checking deliberately excludes sidecar packaging because a Windows worker is not present on this Mac:

```sh
TAURI_CONFIG='{"bundle":{"externalBin":[]}}' \
  cargo check --locked --offline --target x86_64-pc-windows-msvc \
  --manifest-path Desktop/src-tauri/Cargo.toml
```

This is a type check, not a Windows package or runtime test. The manual GitHub Actions workflow provides native Mac/Windows build and test jobs. It has not been executed remotely by this change.

Before a public release, record native FileMaker paste/copy for simple and multiline scripts, whole-script XMSC import, unsupported locked steps returning unchanged in the same session, invalid marker blocking, completion-template review and strict-mode blocking. Confirm the clipboard after a worker failure and repeat with non-ASCII text. Record platform, FileMaker build and expected/actual outcomes.

## Licences and corresponding source

The existing **GPL-3.0-or-later** licence remains unchanged. About explains the hobby-project origin, local operation, warranty disclaimer and independent Claris trademark status. `NOTICE.txt` identifies this modified desktop edition. The full application licence and versioned third-party licence texts are available offline.

The collector uses Cargo.lock and the active dependency trees for macOS ARM/Intel and Windows x64, including build tools. For notices missing from crate packages, checked-in originals are accepted only when their recorded crate version, VCS revision and SHA-256 match. Missing source or notice evidence stops packaging. The inventory is generated before embedding the web assets; rebuild the app after changes.

Native Mac packaging writes the launchable app to `dist/Script Bridge.app`; universal packaging writes `dist/Script Bridge Universal.app` alongside it. ZIPs, matching project and component sources, and release records are stored in `.build/releases/1.1.0/`, keeping `dist` free of intermediate files. The universal edition adds `project-source-universal.tar.gz` and a build receipt while retaining the original ARM-only archive and its source. Both editions use the same locked dependency sources. The Windows installer is `dist/Script Bridge.exe`; its staged payload, DLL audit, hashes and build receipt are retained beside the archives. See [Windows build and acceptance](WINDOWS_BUILD.md). Component crate archives are checked against Cargo.lock checksums. Keep the binary and its matching source archives together when distributing this version. The source includes the frontend, worker, Rust code, build scripts and supplemental notices. Use the compiler/platform tools identified above to rebuild. Original Swift and operating-system runtime/toolchain components retain their own terms.

See [GNU GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html), [Tauri sidecar packaging](https://v2.tauri.app/develop/sidecar/) and [Tauri capabilities](https://v2.tauri.app/security/capabilities/).

## Optional on-device AI generation

The welcome screen has two draft entry paths: external AI text and the AI playground. Both finish in the same workspace and authoritative Swift validator. Generation cannot write the native clipboard or execute a FileMaker script.

Qwen3.5 9B and 35B-A3B are offered as pinned Unsloth Q4_K_M conversions of Qwen models under Apache-2.0. The native runtime is the official llama.cpp b11669 build (source revision `620d2225cc436ab0b001e3200e590e3b286ef9ab`), under MIT with original component notices. Apple Silicon uses Metal; Intel Mac and Windows use CPU runtimes. Intel hardware and Windows runtime speed and full application acceptance still require native verification.

The runtime is packaged inside the app. Weights are optional user downloads and remain outside it in the per-user app data folder. Models have separate pinned byte counts, revisions and SHA-256 digests. Transfers use HTTPS, enforce size, verify the complete digest before installation, retain partial files for resume and use an exclusive download lock. Verified receipts include file size, digest and modification time. A resumed server response must match its requested range, or a full response restarts cleanly. Cancellation is checked while reading chunks; generation cancellation kills the local model process.

The inference server binds to 127.0.0.1 on an allocated port with a random per-process bearer key and no web UI. The frontend talks only to fixed Rust commands; it cannot supply a model URL, filesystem destination or inference endpoint. Prompts are not sent to an external AI service. The app does not persist questions or drafts; chosen model files and verified download receipts persist. Model unload and normal app exit stop the child process. Selecting a missing model starts or resumes its download. Removal is restricted to catalogue model IDs, uses the download file lock, stops the selected model process, and deletes that model’s weights, partial download and verification receipt. Active jobs block removal; other model files remain untouched.

Grounding supplies the bridge's editable step names and selected sections of `SUPPORTED_SYNTAX.md`. Variable/field, control-flow and dialog guidance is always included; the question ranks additional sections. Database context is supplied explicitly by the user, with an optional snapshot of their current workspace script. Prompt size and output limits are bounded. The model must preserve locked markers and use comments for assumptions or unavoidable manual setup. This is reference grounding, not FileMaker-specific fine-tuning or database introspection.

Generation streams into a draft pane, runs strict validation, and can request one repair using the actual diagnostics. Remaining errors remain visible. Choosing Review in workspace is explicit; copying native steps still recompiles authoritatively. The engine cannot establish schema validity or business correctness.

`Scripts/prepare-ai-runtime.py --fetch` obtains the pinned native archive and corresponding source once. Offline packaging checks their hashes. `Scripts/collect-ai-notices.py` adds original runtime, vendored-source and optional-model notices to the viewer. Releases retain `inference-runtime-source.tar.gz` with the Rust/component and project sources. The 9B real-model integration test is gated because it needs the 5.68 GB fixture and local inference permissions; normal unit tests do not download model weights.


## PDF amendments and syntax colours (1.1.0)

The shared editor retains a native textarea for input, selection and accessible text.
An escaped token paint layer provides theme-aware script colours; both scroll axes,
line numbers and native scrollbar dimensions stay synchronized. Clipboard text is unchanged.

The playground accepts one FileMaker script PDF (15 MB, 40 pages, 120,000 extracted
characters maximum). Bundled Mozilla PDF.js 6.4.299 reads selectable text locally,
with scripting, eval, XFA and image decoding disabled. Text is grouped by printed
position; page boundaries, wrap breaks and metadata remain visible in the preview.
The generation prompt distinguishes print metadata from executable steps and requests
a complete replacement, including unchanged code. Scans need OCR first; encrypted,
empty, unreadable and oversized documents receive an explicit error. Extraction does
not establish that the original script is correct or restore native saved options.

PDF text stays in playground memory across navigation, and can be previewed, replaced
or removed. It is sent only to the local inference server when Generate is selected.
The host independently validates its metadata and text limits. The server uses a
32,768-token context; actual chat-template token counts reserve up to 16,384 output
tokens with source-size headroom. Oversized requests fail instead of truncating source.
Cut-off/interrupted output cannot be copied as a completed replacement. The existing
validator/review/native clipboard path remains authoritative for supported syntax.
PDF.js, its compatibility polyfills, CMaps and standard fonts have verified original
licence notices in the application component viewer. No user PDFs belong in source,
release archives, screenshots or test fixtures committed to the repository.


Before source-inclusive packaging on a new checkout, run
`python3 Scripts/prepare-pdf-sources.py --download` once. Both source archives are
pinned by SHA-256 and retained in `.build/pdf-runtime-sources/`; subsequent checks
are offline. Packaging includes them in `frontend-runtime-source.tar.gz` beside
the project, Rust component and inference-engine source archives.


## Independent branding and model selection

The public app name and download bundles are **Script Bridge**, with **for use
with FileMaker Pro** as compatibility text. The stable Tauri identifier,
conversion-worker protocol, old preservation/TODO markers and Windows registry
identifiers remain for upgrade and session compatibility; these are not the
public product name. Windows setup replaces the old Start menu shortcut and
checks that either version's window is closed before updating.

Google Gemma 4 E4B joins the optional model catalogue as a pinned ggml-org Q4_0
conversion (4,590,807,392 bytes; SHA-256 in the catalogue). It uses Apache-2.0,
with separate Google publisher and ggml-org converter attribution. Its 12 GB
memory recommendation includes headroom; E4B denotes effective parameters,
not total weights or a guarantee for 4 GB computers. Both the simple dialog
and XLSX export inference fixtures passed the authoritative Swift validator
on the development Mac. Model quality and Windows acceptance are separate.

The packaged macOS inference libraries require macOS 13.3; the bundle minimum
and download requirements reflect that limit. See the promotion/licensing
review for remaining interoperability and publication considerations.
