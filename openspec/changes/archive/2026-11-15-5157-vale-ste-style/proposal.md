# Proposal

## Why

AGENTS.md rule 9 asks for prose in ASD-STE100, and `src/devops_cli/ai/tasks/style_ste100.md` gives the rules. No tool checks them, so a person checks each document by eye (#5157).

## What Changes

- Add `.vale.ini` and four suggestion rules under `.vale/styles/STE/`: a sentence over 25 words, a paragraph over 6 sentences, the passive voice and a contraction.
- Add Vale 3.26.0 to `src/devops_cli/tools_lock/tools.lock` with the sha256 of the Linux amd64 and arm64 builds, so `devops install-tools --tool vale` installs the pin.
- Add `tests/docs/test_vale_ste.py` and the `vale` helper of `tests/support/`: 26 words give one `STE.SentenceLength` alert and 25 give none, a contraction gives one alert, and a code block and a code span give none. `docs/TESTING.md` returns 0 errors.
- Name the tool in `CONTRIBUTING.md`.

## Capabilities

### New Capabilities

- `docs-ste-style`: the Vale style that checks the ASD-STE100 rules.

### Modified Capabilities

None.

## Impact

- Configuration: `.vale.ini`, `.vale/styles/STE/`
- Tool lock: `src/devops_cli/tools_lock/tools.lock`
- Tests: `tests/docs/test_vale_ste.py`, `tests/support/vale.py`
- Document: `CONTRIBUTING.md`

## Feasibility

- Read on `origin/main`, 2026-11-15. The rule text is `src/devops_cli/ai/tasks/style_ste100.md`, and `src/devops_cli/tools_lock/tools.lock:54:[binary.kubectl]` shows the lock form of a binary tool.
- Vale 3.26.0 is MIT, released 2026-10-31. Its asset digest is `sha256:22aa69a5...` for linux-amd64 and `sha256:3154179f...` for linux-arm64, checked with `sha256sum` after a download.
- `vale docs/TESTING.md` exits 0 with 302 suggestions at the suggestion level.
- `uv run pytest tests/tools_lock tests/commands/test_install_tools.py tests/docs/test_vale_ste.py` passes after the change.

## Existing Tool Considered

Vale 3.26.0 is the standard prose linter, and no open Vale style for ASD-STE100 exists: the ASD dictionary is copyrighted, so community styles paraphrase the rules. The change adds four YAML rules and one pin: about 3,000 tokens to build and 300 a quarter to keep.

## Dependencies

None.
