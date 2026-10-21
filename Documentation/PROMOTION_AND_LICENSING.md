# Promotion and licensing review

Reviewed 21 October 2026 for Script Bridge 1.1.0. This is a repository and
publication-readiness review, not legal clearance or a legal opinion.

## Product identity

Use **Script Bridge** as the product name. Use **for use with FileMaker Pro** as
compatibility text. The repository is `samuelkcc/script-bridge`; the previous
repository name and older release titles are historical identifiers.

Use this statement on the project page and in About:

> Script Bridge is an independent SCKC project for use with FileMaker Pro. It is
> not authorized, sponsored, endorsed by, supported by or affiliated with Claris
> International Inc. FileMaker and FileMaker Pro are trademarks of Claris
> International Inc.

Claris's [trademark guidelines](https://www.claris.com/company/legal/trademark-guidelines.html)
distinguish compatibility references from product branding and request an
independence disclaimer. The new name, original bridge icon and compatibility
subtitle address those concerns. They do not establish clearance of the name
against other parties' trademarks. No Claris or Google logos are used.

## Software and model licences

| Component | Licence / handling |
| --- | --- |
| Script Bridge original code | GPL-3.0-or-later; keep the licence, copyright and warranty notices. |
| Qwen3.5 9B / 35B-A3B | Apache-2.0; optional, pinned Unsloth conversions; publisher and converter identified separately. |
| Google Gemma **4** E4B | Apache-2.0; optional, pinned ggml-org conversion. This is not Gemini and is not Gemma 3n. |
| llama.cpp | MIT plus its original component notices and matching source archive. |
| PDF.js and compatibility assets | Apache-2.0, MIT, BSD and OFL notices; exact preferred source archives retained. |
| Rust, Swift and Windows dependencies | Original component/platform terms remain applicable; offline notices and build inventories are included. |

Google publishes the [Gemma 4 Apache-2.0 licence](https://ai.google.dev/gemma/apache_2).
Its [model card](https://ai.google.dev/gemma/docs/core/model_card_4) explains that
E4B has about 4.5B effective parameters and 8B including embeddings. Do not promote
it as a 4 GB download or promise it runs on every low-memory machine. The selected
Q4_0 conversion is about 4.59 GB; 12 GB system memory is a recommendation, not a
measurement on all supported computers. This app uses text generation; attaching
a PDF extracts text and does not enable model vision, audio or OCR.

The Apache Software Foundation confirms [Apache-2.0 compatibility with GPLv3](https://www.apache.org/licenses/GPL-compatibility).
Retain all applicable notices; a licence label alone is not a redistribution audit.
The new model does not replace the application's GPL licence or grant rights in
Google, Qwen or Claris branding.

For each binary release provide the matching project source, component sources,
inference-engine sources, PDF-library sources and checksums. Avoid pairing a new
binary with the old 1.0.0 source tag. Model weights are downloaded separately;
their exact source, version, licence, byte length and SHA-256 are recorded in
`Desktop/ai/catalogue.json`. Paid promotion or donations do not remove GPL duties.

## Remaining matters before wider promotion

- **Clipboard interoperability:** the app uses private FileMaker clipboard XML.
  The installed FileMaker licence contains restrictions on reverse engineering,
  subject to applicable law. A qualified adviser must assess the applicable
  agreement, jurisdiction and how the implementation was developed; this code
  review cannot determine whether a restriction or interoperability exception
  applies. A disclaimer does not resolve that question.
- **Documentation:** Claris [restricts redistribution of its documentation](https://www.claris.com/company/legal/claris-documentation).
  Keep the factual step index, help links and bridge-authored guide; do not add
  downloaded help manuals or copied official explanations/examples without rights.
- **Demonstrations:** use fictional scripts and database names. Do not publish
  attached customer PDFs, credentials, email addresses or private business rules.
- **AI accuracy:** local-model output is a draft. The seven-page private PDF check
  exposed omitted changes and syntax errors with Qwen 9B. Gemma 4 E4B passed the same fixture’s threshold-branch and syntax checks; this does not establish live database behaviour. Syntax validation alone
  cannot establish that requested business changes were implemented. Do not claim
  automatic, error-free amendments or database verification.
- **Platform claims:** macOS has local checks. Windows installers are cross-built
  and require native Windows/FileMaker acceptance testing. The packages are unsigned
  or ad-hoc signed and the Mac package is not notarized. State these limits plainly.

Keep support links at the bottom of the project page. Do not describe the app as
official, Claris-approved, Google-approved, certified or guaranteed safe. Any future
cloud AI service, telemetry or external PDF upload needs a fresh privacy review.
