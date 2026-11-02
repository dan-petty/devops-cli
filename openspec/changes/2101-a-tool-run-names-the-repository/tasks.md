# Tasks

## 1. Add repository_uri to ToolRun and read it from git

Kind: behavior. Reads: `src/devops_cli/core/repo.py` (`nearest_checkout`). Changes: `src/devops_cli/security/tool_executor.py`, `tests/ai/test_tool_executor_contract.py`.

- [ ] 1.1 In `tests/ai/test_tool_executor_contract.py`, add a branch for `config` to `_handle_tool_executor_git`. For `config --local --get remote.origin.url` it answers the `url` of the section `remote "origin"` in `<root>/.git/config` (read with `configparser`). It answers exit 1 with no output when the file or the section is missing, and exit 128 when the path holds `broken`, as `_handle_git_rev_parse` does. Add tests that run the `executor` fixture over a scenario whose `.git/config` holds a remote. One test uses `https://user:token@example.com/a/b.git` and asserts `https://example.com/a/b.git`. One test uses `ssh://git@example.com/a/b.git` and asserts `ssh://example.com/a/b.git`. One parametrized test uses `git@example.com:a/b.git`, `/srv/a.git` and `file:///srv/a.git`, and asserts None. One test with no remote asserts None. Verify that `uv run devops ci test tests/ai/test_tool_executor_contract.py` fails on the base
- [ ] 1.2 In `src/devops_cli/security/tool_executor.py`, add `repository_uri: str | None = None` to the `ToolRun` model, and describe it in the docstring of `ToolRun`. Add `_read_repository_uri(root: Path) -> str | None`. It returns None when `nearest_checkout(root)` is None. Else it calls `_git(root, "config", "--local", "--get", "remote.origin.url", accepted=(0, 1))`, and returns None for an empty output. Else it splits the URL with `urlsplit`, returns None when the scheme or the host is empty, and returns `urlunsplit` of the URL with the netloc set to the text after the last `@`. Add `_tree_repository_uri(root: Path, *, required: bool) -> str | None`, which calls `_read_repository_uri` and turns a `SandboxError` into None unless `required` is true, as `_tree_commit` does. In `record_tool_run`, pass `repository_uri=_tree_repository_uri(root, required=require_commit)` to the `ToolRun` constructor. Verify that `uv run devops ci test tests/ai/test_tool_executor_contract.py` passes
- [ ] 1.3 Check the tests that must keep passing. They are `test_a_tree_outside_any_repository_records_no_commit`, `test_a_checkout_without_a_commit_records_no_commit`, `test_a_checkout_that_git_cannot_read_is_refused_and_not_recorded_as_no_commit` and `test_the_direct_executor_records_no_commit_for_a_checkout_that_git_cannot_read`. Verify that `uv run devops ci test tests/ai/test_tool_executor_contract.py tests/security/test_scanner_tool_executor.py` passes

## 2. Write versionControlProvenance in the SARIF export

Kind: behavior. Reads: `tests/fixtures/sarif-schema-2.1.0.json`. Changes: `src/devops_cli/security/sarif.py`, `src/devops_cli/security/tool_executor.py` (module docstring), `tests/security/test_sarif_emission.py`.

- [ ] 2.1 In `tests/security/test_sarif_emission.py`, add tests that build a document with `to_sarif` and the helper `_record`, and check it with `_assert_valid_sarif`. One test uses a record with `repository_uri` set and a clean commit, and asserts one `versionControlProvenance` entry with `repositoryUri` and `revisionId`. One test uses a commit that ends with `-dirty`, one uses `repository_uri` None, and one uses commit None. Each asserts that the run has no `versionControlProvenance`. One test uses three records with the same `repository_uri` at the clean commits A, B and A, and asserts two entries in the order A, B. One test uses a clean record and a `-dirty` record, and asserts one entry for the clean commit. Verify that `uv run devops ci test tests/security/test_sarif_emission.py` fails on the base
- [ ] 2.2 In `_run_for` of `src/devops_cli/security/sarif.py`, build the list of entries `{"repositoryUri": record.repository_uri, "revisionId": record.commit}` from the records whose `repository_uri` is set and whose commit is set and does not end with `-dirty`. Drop a repeated pair, and keep the order of the first record of each pair. Set `run["versionControlProvenance"]` when the list is not empty. Verify that `uv run devops ci test tests/security/test_sarif_emission.py` passes
- [ ] 2.3 In `test_the_run_of_a_tool_holds_each_record_of_that_tool_in_its_property_bag` of `tests/security/test_sarif_emission.py`, change the docstring: the sentence "no record holds what an artifact or `versionControlProvenance` requires" no longer holds. The test must keep passing, because `_record` sets no `repository_uri`. The snapshot `tests/security/__snapshots__/test_sarif_emission.ambr` holds no `tool_runs`, so it does not change. In the module docstring of `src/devops_cli/security/tool_executor.py`, move `commit` out of the list of names that the export does not write: `commit` is the `revisionId` and `repository_uri` is the `repositoryUri` of `versionControlProvenance`, for a record with a repository URI and a commit that does not end with `-dirty`. Remove the sentence that says the record holds no repository. Verify that `uv run devops ci test tests/security/test_sarif_emission.py tests/ai/test_tool_executor_contract.py` passes

## 3. Document the field

Kind: documentation. Reads: none. Changes: `docs/SELF_IMPROVEMENT.md`.

- [ ] 3.1 In the section "Tool Run Records" of `docs/SELF_IMPROVEMENT.md`, add that a record holds `repository_uri`, the `origin` remote of the checkout with no userinfo, and that it is empty for a remote that is not an absolute URI with a host. Add that the run of the tool in `findings.sarif` holds a `versionControlProvenance` entry for each distinct pair of repository URI and clean commit. Verify that `uv run devops ci docs` passes

## 4. Archive

Kind: documentation. Reads: none. Changes: `openspec/changes/`, `openspec/specs/`.

- [ ] 4.1 In the last commit, archive the change with `uv run devops openspec archive 2101-a-tool-run-names-the-repository`, and verify that `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
