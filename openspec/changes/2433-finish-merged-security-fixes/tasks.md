# Tasks

## 1. The merged changes are archived

- [x] 1.1 Archive `1469-audit-keys-leak-exit-code` in its own commit
  - Verification: `uv run devops openspec archive 1469-audit-keys-leak-exit-code`
- [x] 1.2 Archive `1492-drop-gh-go-trivy-ignores` in its own commit
  - Verification: `uv run devops openspec archive 1492-drop-gh-go-trivy-ignores`
- [x] 1.3 Tick the archive task of `2205-refuse-code-loading-env-keys`, and archive it in its own commit
  - Verification: `uv run devops openspec archive 2205-refuse-code-loading-env-keys`

## 2. The guard refuses GCONV_PATH and the bash keys that run code

- [x] 2.1 Add failing tests: a caller override of `GCONV_PATH`, `SHELLOPTS`, `BASHOPTS` or `PS4`, in upper and lower case, raises `SecurityError`; `DYLD_VERSIONED_LIBRARY_PATH`, `DYLD_IMAGE_SUFFIX`, `DYLD_EXAMPLE_KEY` and `BASH_FUNC_x()` pin the prefix rule
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [ ] 2.2 Add `GCONV_PATH`, `SHELLOPTS`, `BASHOPTS` and `PS4` to `CONST_CODE_LOADING_ENV_PATTERNS`, and write its comment as one short sentence for each source
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_review_rules_pack.py`
- [ ] 2.3 Write the child environment bullet of `ARCHITECTURE.md` for `isolate_env` on and off, with the constant as the full list and the null byte in its own sentence
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. The audit-keys tests assert each clause of the spec

- [ ] 3.1 Assert the success line in `test_config_audit_keys_table_rendering`, and the name of the leak in the security alert of `test_config_audit_keys_fails_on_a_plaintext_secret_in_the_table`
  - Verification: `uv run devops ci test tests/test_config_audit_keys.py`

## 4. The Service image invariants are in one subject file

- [ ] 4.1 Move the two tests of `tests/test_service_image_gh.py` and `test_service_dockerfile_base_images_pinned_by_digest` with its helpers into `tests/invariants/test_service_image.py`, and delete the flat file
  - Verification: `uv run devops ci test tests/invariants/test_service_image.py tests/test_architectural_invariants.py`
- [ ] 4.2 Add a failing test of the gh release finder with a quoted URL and a URL after another character
  - Verification: `uv run devops ci test tests/invariants/test_service_image.py`
- [ ] 4.3 Make the finder search the Dockerfile text for each gh release URL
  - Verification: `uv run devops ci test tests/invariants/test_service_image.py`
- [ ] 4.4 Add `test_service_image.py` to the subject files of `tests/invariants/` in `docs/TESTING.md`
  - Verification: `uv run devops docs check`

## Workflow follow-up

- `ZDOTDIR` and the interpreter keys that make a child run code, for example `PYTHONPATH` and `NODE_OPTIONS`: #2429.
- `devops config audit-keys` does not scan the global config file: #2426.
- `devops config audit-keys --dry-run` claims a compliance that it did not check: #2255 removes the echo-only preview.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
