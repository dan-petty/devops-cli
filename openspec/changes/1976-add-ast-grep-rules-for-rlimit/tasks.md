# Tasks

## 1. Add the three process-safety rules, their cases and their gate entries

Kind: manifest. Reads: `.ast-grep/rules/review-cwd-read.yml`, `.ast-grep/rule-tests/review-cwd-read-test.yml`, `src/devops_cli/core/process.py`, `tests/gate/construct_gate.py`. Changes: `.ast-grep/rules/process-setrlimit-nproc.yml` (new), `.ast-grep/rules/process-nonblocking-std-fd.yml` (new), `.ast-grep/rules/process-killpg-guarded.yml` (new), `.ast-grep/rule-tests/process-setrlimit-nproc-test.yml` (new), `.ast-grep/rule-tests/process-nonblocking-std-fd-test.yml` (new), `.ast-grep/rule-tests/process-killpg-guarded-test.yml` (new), `tests/gate/construct_gate.py`.

- [ ] 1.1 The case in `.ast-grep/rule-tests/process-setrlimit-nproc-test.yml` fails first on `resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))`, the cases in `.ast-grep/rule-tests/process-nonblocking-std-fd-test.yml` fail first on `os.set_blocking(0, False)` and `fcntl.fcntl(1, fcntl.F_SETFL, fcntl.O_NONBLOCK)`, and the case in `.ast-grep/rule-tests/process-killpg-guarded-test.yml` fails first on a module-level `os.killpg` call and passes on the call inside `_signal_process_group` of `src/devops_cli/core/process.py`
  - Verification: `$ uv run devops ci test tests/gate/construct_gate.py` fails on the base
- [ ] 1.2 Write each rule with `language: python`, `severity: error` and `files: ["src/**"]`, beside the existing rules. Match `resource.setrlimit(resource.RLIMIT_NPROC, $$$REST)` and the bare `setrlimit(RLIMIT_NPROC, $$$REST)`. Match `os.set_blocking` with the literal 0, 1 or 2 and `False`, and `fcntl.fcntl` with the literal 0, 1 or 2 and an `fcntl.O_NONBLOCK` attribute or an `O_NONBLOCK` name among its arguments. Match `os.killpg($$$ARGS)` with a `not` over an `inside` relation whose `function_definition` name matches the four guard-holding functions of `src/devops_cli/core/process.py`, with `stopBy: end`. Run `uv run ast-grep test --skip-snapshot-tests` to see each invalid case fail before its rule and pass after it. Then add each id to `CONST_AST_GREP_RULE_FILES` with `("src/**",)` and one `Violation` in `VIOLATIONS` of `tests/gate/construct_gate.py` in the `src` tree, and run `uv run devops ci --only constructs` to see the row green
  - Verification: `$ uv run devops ci test tests/gate/construct_gate.py` passes

## 2. Name the three rules in the architecture document

Kind: other. Reads: `.ast-grep/rules/process-setrlimit-nproc.yml`, `.ast-grep/rules/process-nonblocking-std-fd.yml`, `.ast-grep/rules/process-killpg-guarded.yml`. Changes: `ARCHITECTURE.md`.

- [ ] 2.1 Name the three rule ids beside the process-safety bullets of ARCHITECTURE.md section 7.3, so a reader learns which check holds each rule. Leave `.pre-commit-config.yaml` as it is, because the construct gate compares the hook `entry` and `args` with `CONST_AST_GREP_SCAN_ARGS`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `ARCHITECTURE.md`
  - Verification: `$ uv run devops ci docs` passes
