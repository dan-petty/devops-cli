# Tasks

## 1. JSON stdout of scan commands

- [x] Add failing tests that parse the stdout of `--json` and `--format json` for `scan trivy`, `scan secrets`, `scan sast`, `scan iac`, `scan complexity`, `scan workflows` and `scan aibom`
  - Verification: `uv run pytest tests/test_scan.py -k json_stdout -q`
- [x] Gate the muted progress line on the resolved table format in `scan trivy`, `scan secrets`, `scan sast`, `scan iac`, `scan complexity` and `scan workflows`
  - Verification: `uv run pytest tests/test_scan.py -q`
- [x] Keep `scan aibom` progress gated on `--output` and verify its `--format json` stdout parses
  - Verification: `uv run pytest tests/test_scan.py -k aibom_json -q`
- [x] Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`
- [x] Archive the change
  - Verification: `uv run devops openspec archive 2216-scan-json-stdout`
