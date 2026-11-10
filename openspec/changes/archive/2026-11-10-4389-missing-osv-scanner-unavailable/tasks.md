## 1. Scanner preflight check for osv-scanner
kind: behavior

- [x] 1.1 Add unit test for missing osv-scanner binary returning unavailable status
  Verification: `$ uv run devops ci test tests/security/test_osv_scanner.py`
- [x] 1.2 Check binary presence in OsvScanner.scan before dispatching command
  Verification: `$ uv run devops ci test tests/security/test_osv_scanner.py tests/security/test_sarif_emission.py`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
