# Proposal

## Why

Issue #589 identifies that untrusted content can smuggle prompt injections via invisible Unicode tags, zero-width steganography, chat template delimiter mimicry, and exfiltration links. The system currently lacks a dedicated prompt injection detector and canary audit tool, which exposes review pipelines and AI agent workflows to indirect injection attacks.

## What Changes

This change introduces prompt injection smuggling detection and canary auditing:
- Adds pure-function detection module `src/devops_cli/security/prompt_injection.py` with:
  - INJ001: Unicode Tag ASCII smuggling detection and decoding (`U+E0020` to `U+E007E`), exempting emoji tag sequences.
  - INJ002: Format-character and zero-width smuggling detection (`category == 'Cf'`).
  - INJ003: Chat template delimiter mimicry detection with escaping utilities (`<|im_start|>`, `[INST]`, `<<SYS>>`, etc.).
  - INJ005: Markdown exfiltration link embedding detection.
  - EGR005: High-entropy cryptographic canary generation, prompt sentinel wrapping, and response auditing (`CanaryTokenManager`).
- Adds CLI command `devops scan injection <target>` supporting `--sarif`, `--suppress`, `--show-suppressed`, `--fail-on`, `--min-severity`, `--format`, `--json`, and `--dry-run`.
- Exposes `scan_injection` FastMCP tool through `CONST_MCP_EXPOSURE_TABLE`.
- Enforces Ruff rules `PLE2502`, `PLE2510`, `PLE2512`, `PLE2513`, `PLE2514`, and `PLE2515` in `pyproject.toml`.

This change fits in one pull request.

## Capabilities

### New Capabilities
- `prompt-injection-detection`: Detect prompt-injection smuggling vectors (Unicode tags, format-characters, chat delimiters, markdown exfiltration) and audit canary leaks.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/security/prompt_injection.py`: New pure-function security scanner module.
- `src/devops_cli/commands/scan.py`: New `devops scan injection` subcommand.
- `src/devops_cli/config/constants.py`: Exposes `scan_injection` in `CONST_MCP_EXPOSURE_TABLE`.
- `pyproject.toml`: Activates Ruff rules `PLE2502`, `PLE2510`, `PLE2512`–`PLE2515`.
- `src/devops_cli/lang/en/help.py` & `src/devops_cli/lang/en/messages.py`: ASD-STE100 help and status messages.
- New unit and integration tests under `tests/test_prompt_injection.py` and `tests/test_scan_injection.py`.

## Feasibility

I confirmed the premise against the real Python runtime, library source, and repository files:
- In Python 3.14, `unicodedata.category` marks Tag-block code points (`0xE0020`–`0xE007F`) and zero-width code points (`0x200B`, `0x200C`, `0x200D`, `0x2060`, `0xFEFF`) as category `Cf`. `U+E0000` is category `Cn`.
- `ruff rule` with Ruff 0.16.8 confirmed that `PLE2502`, `PLE2510`, `PLE2512`, `PLE2513`, `PLE2514`, and `PLE2515` exist, while `PLE2511` does not exist.
- Standard suppression policy handling via `load_policy` and `build_report` integrates cleanly with `write_sarif`.
- Vibes reference implementation `tools/prompt_injection_scanner.py` verifies the INJ001-INJ005 rule taxonomy and canary generation pattern.

## Existing Tool Considered

External libraries `llm-guard` (0.3.16) and `rebuff` (0.1.1) were considered:
- `llm-guard` requires heavy dependencies including PyTorch, Hugging Face transformers, and Presidio Analyzer, which violates the CLI footprint and speed constraints.
- `rebuff` is unmaintained, with its last release on 2024-01-20.
Building the lightweight pure-function detector using standard library `unicodedata`, `re`, and `secrets` requires approximately 250 lines of code, 12,000 tokens of agent context, and 45 minutes of implementation time. The change deletes no existing external tooling.
