# Tasks

## 1. The render refuses an unknown key

Kind: behavior.

- [x] 1.1 Write a failing test: the render refuses a template key that no setting declares and names it
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py`
- [x] 1.2 Call `unknown_setting_keys` in the render of the ConfigMap
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py tests/k8s/test_k8s_configmap_keys.py`

## 2. The guard counts the readers of the tree

Kind: other.

- [x] 2.1 Count a call of a reader of `tests.support.k8s_tree`, judge a path whole, and add both cases to the self-test of the guard
  - Verification: `$ uv run devops ci --check --only test-tree`

## 3. Tests of the area

Kind: other.

- [x] 3.1 Delete the tests that assert a value of a manifest, a chart values file or a config file, with their helpers and test data
  - Verification: `$ uv run devops ci --check --only test-tree`
- [x] 3.2 Replace the tests of source code that read a committed manifest with tests on a fixture
  - Verification: `$ uv run devops ci test tests/k8s/ tests/commands/k8s/ tests/invariants/`
- [x] 3.3 Lower the counts of `tests/gate/tree_checks/config_reads.toml`
  - Verification: `$ uv run devops ci --check --only test-tree`

## 4. Specs and documents

Kind: other.

- [x] 4.1 Change each scenario whose test goes so that it names a validator command or a live check
  - Verification: `$ uv run devops openspec check`
- [x] 4.2 Correct the documents that named a deleted test
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The other areas of #6082: workflows, monitoring, commands, images and tools.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
