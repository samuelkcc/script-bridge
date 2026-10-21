# Changelog

## 1.1.0 — 21 October 2026

- Rename the independent app to **Script Bridge**, with FileMaker Pro compatibility text and a prominent non-affiliation notice.
- Add optional Google Gemma 4 E4B (4.59 GB Q4_0, Apache-2.0) with automatic download, checksum verification and removal.
- Restore script syntax colours in the shared Mac and Windows workspace, with
  theme-aware colours for steps, comments, strings, variables, fields and calculations.
  Editing, selection, scrolling and clipboard text retain the underlying plain script.
- Attach a FileMaker script PDF in AI playground, preview its extracted text, and
  replace or remove it. Selectable text is read locally using bundled Mozilla PDF.js.
- Ask Qwen to amend the attached script and return a complete replacement for review
  in Script workspace. Existing workspace scripts remain an optional context source.
- Expand local inference context, measure actual prompt tokens and reserve room for
  the whole replacement. Oversized requests and interrupted output receive clear errors;
  incomplete output cannot be copied as a finished replacement.
- Update About, offline component licences and corresponding-source packaging for
  PDF.js, its compatibility library, CMaps and fonts.

AI drafts still need review. A PDF lacks hidden native step options and scans need
OCR first. Syntax validation cannot establish correct database names or business logic.
Windows packages require native Windows/FileMaker acceptance testing.
