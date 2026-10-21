## Script Bridge 1.1.0 (21 October 2026)

The independent app is now **Script Bridge**, for use with FileMaker Pro. This release restores workspace syntax colours, adds local PDF script attachments with preview/removal and full-replacement draft instructions, and adds Google Gemma 4 E4B alongside Qwen 9B and 35B. About, model notices and matching component sources are updated.

Generated scripts require comparison with the original, syntax review and database testing. The long private PDF test exposed limitations in Qwen 9B; do not treat a completed AI response as verified business logic. Windows native acceptance remains pending.

The repository's former name and the release titles below are retained as history.

## FileMaker Script Bridge 1.0.0 (20 October 2026)

- Mac build 2026102004: compile the app icon with Apple's icon compiler and use an explicit, build-specific icon filename to fix Finder's generic application placeholder.
- Update the purple bridge app icon on both platforms, place Script workspace before AI playground, and make Copy to FileMaker a prominent labelled action with a new clipboard/arrow symbol.
- Provide a Windows x64 installer with the native host, conversion worker and required runtime DLLs; native Windows acceptance remains pending.
- Add model selection with automatic download/resume, plus removal of installed models or partial downloads to free disk space.
- Add two draft entry paths: paste from another AI tool, or use the Qwen playground with optional verified 9B/35B downloads.
- Ground generation in the bridge syntax guide and supported-step catalogue, with optional database context, streamed drafts, validation and one repair attempt.
- Add separate Qwen/llama.cpp licence notices and update About to describe downloads and local AI operation. Remove the “Made to stay local” sidebar note.
- Adopt semantic version 1.0.0 consistently in the app, package manifests and GitHub-facing documentation.
- Build 2026102003: fix the unnecessary outer window scrollbar by containing the app shell and anchoring the screen-reader announcement element. Content panels still scroll when needed.

- Add an AniCanto-inspired shared Tauri/Rust desktop shell with welcome, workspace, searchable step reference and quick guide.
- Add light, dark and system appearance; About presents the independent SCKC hobby project and local privacy model.
- Preserve GPL-3.0-or-later and include a full offline application licence, original application, inference engine and model notices, provenance checks and matching source archives.
- Run the existing Swift engine through a persistent JSON-lines worker, retaining Smart Fix questions, strict mode and session-bound native XML preservation.
- Add native Rust clipboard adapters for macOS and Windows, including Windows FileMaker length-prefixed payload handling. The host recompiles immediately before exporting native steps.
- Provide native build/package scripts and a manual Mac/Windows CI workflow. The Mac build targets Apple Silicon; Windows host and worker cross-compilation pass and an x64 installer is provided for native Windows and FileMaker acceptance testing.
- Automated checks: 107 existing Swift tests, 5 JavaScript/worker tests and 10 Rust host/knowledge/codec tests pass locally. Separate integration checks cover download resume and checksum rejection, plus real Qwen 9B generation through the Swift validator. The 35B model has not been inference-tested. See `Documentation/DESKTOP_ARCHITECTURE.md` for the Rust assessment, measurements and release boundary.

## Unreleased local patch — build 2026092902

- Block calculation comments while allowing script Comment steps and quoted literal data.
- Smart Fix removes outer block-comment wrappers without deleting the enclosed calculation; ambiguous cases require manual review.
- Show the bundle version and build in About.
- Prevent line joining from inserting a space after `::` in field references. FileMaker treats that space as part of the field name and may comment out the calculation on paste.
- Smart Fix repairs existing separator whitespace and outer calculation wrappers together, preserving quoted text and spaces within field names.
- All 107 automated tests pass. Five affected field calculations passed a native FileMaker paste/copy check without comment wrappers; the temporary paste was undone.

# FileMaker Script Bridge 2026.09.29

Adds XLSX export options, whole-file data reads, and guided Smart Fix questions for incomplete AI-generated steps.

## Changes

- Export Records now supports worksheet-name calculations and common AI option labels. Smart Fix repairs unambiguous multiline field lists while preserving field order.
- Read from Data File supports whole-file reads as Bytes, UTF-8, or UTF-16, with variable or field targets. Binary reads retain XLSX attachment data.
- Smart Fix asks for missing paths, field order, column-heading choices, file IDs, targets, and encodings instead of guessing. Safe defaults and inferred settings are shown for review.
- Existing TODO comments can be recovered through the same review workflow.
- Numbered custom-dialog buttons are accepted without inserting an extra OK button.
- Duplicate and unknown export options are rejected rather than silently ignored; unrecognized native XML remains preserved.
- Coverage increases to 98 editable subsets across 216 official script steps.

## Validation

- All 96 automated tests passed.
- Export and read steps passed native FileMaker paste/copy round-trip checks, including worksheet names, headings, binary reads, UTF-8, and a UTF-16 field target.
- Universal Apple Silicon and Intel app; bundle signature verified.
- Runtime export, read, and email execution was not tested as part of clipboard verification.

## Known limitation

Non-empty Read from Data File amounts require manual setup in FileMaker. The observed native clipboard omitted that parameter, so the bridge blocks these drafts rather than silently converting them to whole-file reads. Blank or omitted Amount reads the whole file, subject to FileMaker's 64 MB per-read limit.

## Download and requirements

Download **FileMaker Script Bridge.app.zip**, extract it, and move the app to Applications.

- macOS 13 or later; Apple Silicon and Intel.
- FileMaker Pro 26 for the documented native clipboard compatibility.
- Fully local operation; no accounts, analytics, or network requests.
- Ad-hoc signed, not Apple-notarized. macOS may require Control-clicking the app and choosing **Open** on first launch.
- Preservation markers retain their original XML only during the same app session.

Released under GPL-3.0-or-later. This independent project is not affiliated with or endorsed by Claris International Inc.

---

# FileMaker Script Bridge 2026.09.23

## Highlights

- Adds local Smart Fix review for flagged script lines and missing dialog defaults. Review suggested repairs, edit replacements, keep unresolved items, or explicitly omit a step with a comment preserving the original text.
- Validates replacements as native steps before applying them and requires a separate Update FileMaker Clipboard action after review.
- Recovers the bridge’s exported two-comment TODO drafts for review and repair.
- Improves Show Custom Dialog parsing and validation, including positional title/message forms, ordered button definitions, and rejection of unsupported or duplicate options. Missing default-button suggestions use `Default Button: "OK", Commit: No` and require review.
- Expands coverage since the first release from 92 to 97 editable subsets across the 216-step reference. Adds native data-file operations and Insert from URL, improves wrapped record/find options, and fixes Go to Record exit-option XML.
- Provides completion-template comments for the remaining 119 official steps, with optional strict native-only export.
- Improves universal app packaging with optional SDK and build-system overrides.

## Validation

The universal release build completed for Apple Silicon and Intel, and its ad-hoc signature and bundle version were verified. Automated tests could not run on the release machine: Command Line Tools lacks XCTest, and the installed Xcode requires license acceptance.

## Download and requirements

Download **FileMaker Script Bridge.app.zip**, extract it, and move the app to Applications.

- macOS 13 or later; universal Apple Silicon and Intel build.
- FileMaker Pro 26 for the documented script-step catalogue.
- Fully local operation; no accounts, analytics, or network requests.
- Ad-hoc signed and not Apple-notarized. macOS may require Control-clicking the app and choosing **Open** on first launch.
- Preservation markers retain their original XML only during the same app session. Complete unresolved TODO steps in FileMaker before using the script.

Released under GPL-3.0-or-later. This independent project is not affiliated with or endorsed by Claris International Inc.

---

# FileMaker Script Bridge 2026.08.11

This is the first public release of FileMaker Script Bridge, a native offline macOS clipboard bridge for FileMaker Pro Script Workspace and readable script text.

## Highlights

- Converts selected FileMaker steps (`XMSS`) and complete scripts (`XMSC`) into readable text.
- Validates readable text and creates native FileMaker clipboard data for paste-back.
- Covers all 216 official FileMaker Pro 26 steps in the in-app reference.
- Provides 92 tested editable subsets and lossless same-session preservation for other imported steps.
- Includes syntax colouring, issue navigation, review/XML views, and strict blocking of lossy AI-authored exports.
- Ships as a universal macOS application for Apple Silicon and Intel.
- Runs fully offline with no accounts, analytics, or network requests.

## Requirements

- macOS 13 or later
- FileMaker Pro 26 for the documented and tested script-step catalogue

## Installation note

The downloadable build is ad-hoc signed and is not Apple-notarized. macOS may require Control-clicking the app and choosing **Open** on first launch.

## Licence and independence

Released under GPL-3.0-or-later. This independent community project is not affiliated with or endorsed by Claris International Inc.
