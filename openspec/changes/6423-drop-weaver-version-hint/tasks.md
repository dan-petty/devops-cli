# Tasks

## 1. The install hint names the devtools image and no version

Kind: behavior. Changes: `src/devops_cli/telemetry/semconv.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`, `tests/telemetry/test_telemetry_semconv.py`.

- [x] 1.1 Test that with no weaver on PATH, the refusal names `ghcr.io/dan-petty/devtools` and the weaver releases page, and holds no version number
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_semconv.py`
- [x] 1.2 Move the hint to `MESSAGES.telemetry.weaver_missing_hint` with the image `CONST_DEVTOOLS_IMAGE` and no version, and delete `CONST_SEMCONV_WEAVER_VERSION`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_semconv.py`

## 2. No copied weaver version is left

Kind: deletion.

- [x] 2.1 Confirm that no code under `src/` or `tests/` names the deleted constant
  - Verification: `$ ! git grep -n SEMCONV_WEAVER_VERSION -- src/ tests/`

## 3. Documents

Kind: documents.

- [ ] 3.1 Regenerate the reference documents for the changed message
  - Verification: `$ uv run devops docs generate --check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
