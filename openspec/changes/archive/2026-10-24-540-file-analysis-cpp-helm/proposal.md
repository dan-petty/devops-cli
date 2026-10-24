# Proposal

## Why

Issue #540 identifies that `devops_cli.ai.analyze.scanner.detect_language` misclassifies C++ source files as C and reads Helm chart templates as plain text. This incorrect classification feeds review contexts and file outlines, which degrades review quality.

## What Changes

This change corrects language detection across file analysis and sample validation:
- C++ extensions (`.cc`, `.cpp`, `.cxx`, `.c++`, `.hh`, `.hpp`, `.hxx`) map to `cpp`.
- Header files (`.h`) evaluate content for C++ constructs before defaulting to `c`.
- Template files (`.tpl`) inside a Helm chart beside `Chart.yaml` map to `helm`.
- Detection operates reliably even when the host `mimetypes` database is empty.
- Sample validation reports no mislabelled files for C/C++ and Kubernetes/Helm categories.

This change fits in one pull request.

## Capabilities

### New Capabilities
- `file-analysis`: Detect file language and classify source files accurately, including C++ extensions and Helm templates.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/ai/analyze/scanner.py`: Updates language detection and extension fallbacks.
- `src/devops_cli/ai/analyze/outlines.py`: Passes resolved repository paths to language detection.
- `src/devops_cli/ai/review/sample_validation.py`: Supplies repository checkout root during file inspection.
- Tests: Adds comprehensive language detection table tests and updates sample validation expectations.

## Feasibility

I confirmed the premise against the real Python runtime and repository structure:
- In Python 3.14, `mimetypes.guess_type("file.cc")` returns `("text/x-c++src", None)`. Splitting on `+` reduces the subtype to `c`, which matches `_VALID_MIME_SUBTYPES` and causes mislabelling.
- On minimal environments without system MIME tables, `mimetypes.guess_type` returns `(None, None)` and falls back to extension mappings.
- Helm charts consistently contain `Chart.yaml` at their root directory above `templates/`.

## Existing Tool Considered

Pygments 2.21.0 and standard library `mimetypes` were considered. Pygments maps `.tpl` files to Smarty rather than Helm templates, and adds overhead across directory scans. `mimetypes` lacks Helm chart awareness and strips C++ identifiers. Implementing direct extension mapping and Helm chart traversal requires approximately 40 lines of code, 4,000 tokens of agent context, and 15 minutes of implementation time. The internal change deletes no existing external tooling.
