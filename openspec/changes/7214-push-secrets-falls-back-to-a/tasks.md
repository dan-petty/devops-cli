# Tasks

## 1. Name the tree's own Secret file in the environment tree

Kind: behavior. Reads: `src/devops_cli/k8s/environment.py`, `tests/k8s/test_environment.py`, `tests/ci/test_ci_mutate.py`, `tests/commands/k8s/test_k8s.py`, `tests/k8s/test_app_render.py`, `tests/k8s/test_image_pins.py`, `tests/k8s/test_k8s_argocd_gate.py`. Changes: `src/devops_cli/k8s/environment.py`, `tests/k8s/test_environment.py`.
Adds: `test_environment_tree_cluster_secrets_names_the_file_of_the_tree`

- [ ] 1.1 The new test `test_environment_tree_cluster_secrets_names_the_file_of_the_tree` in `tests/k8s/test_environment.py` fails before the change, because `src/devops_cli/k8s/environment.py:104:fixture = self.repo / "tests" / "fixtures" / _CLUSTER_SECRETS` returns the fixture for a tree that holds no file
  - Verification: `$ uv run devops ci test tests/k8s/test_environment.py` fails on the base
- [ ] 1.2 Delete the fixture branch of the `cluster_secrets` property in `src/devops_cli/k8s/environment.py`, so `src/devops_cli/k8s/environment.py:96:def cluster_secrets(self) -> Path:` returns the tree's own cluster secrets path, direct or nested, and never a path under the test fixtures. Replace `test_environment_tree_cluster_secrets_resolves_fixture_in_repository` in `tests/k8s/test_environment.py` with `test_environment_tree_cluster_secrets_names_the_file_of_the_tree`, which builds a checkout with the helper `tests/k8s/test_environment.py:20:def _checkout(folder: Path, *, project_file: str | None = None) -> Path:`, writes no cluster secrets file, and asserts that `tests/k8s/test_environment.py:134:tree = EnvironmentTree(root=repo / "k8s", repo=repo)` gives the direct path of the tree
  - Verification: `$ uv run devops ci test tests/k8s/test_environment.py` passes

## 2. Raise a configuration error when the tree has no Secret file

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/k8s/environment.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/exceptions/config.py`, `tests/k8s/test_cluster_secrets_file.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_gitea.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/commands/test_config_commands.py`, `tests/invariants/test_k8s_manifests.py`, `tests/invariants/test_k8s_searxng.py`, `tests/k8s/test_cluster_secret_key_refs.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_cluster_secrets.py`, `tests/k8s/test_grafana_renderer_optional.py`, `tests/k8s/test_roadmap_service_key.py`, `tests/lang/test_language_catalogs.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/lang/en/errors.py`, `tests/k8s/test_cluster_secrets_file.py`.
Adds: `cluster_secrets_file_not_found`, `test_load_cluster_secrets_table_raises_when_the_tree_has_no_file`

- [ ] 2.1 The new test `test_load_cluster_secrets_table_raises_when_the_tree_has_no_file` in `tests/k8s/test_cluster_secrets_file.py` calls `load_cluster_secrets_table` on an empty folder and fails before the change, because `src/devops_cli/k8s/cluster_secrets.py:498:env_file = _resolve_fixture_secrets_file()` returns the rows of the fixture instead of raising
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secrets_file.py` fails on the base
- [ ] 2.2 Delete `src/devops_cli/k8s/cluster_secrets.py:453:_FIXTURE_SECRETS_FILE = (`, `src/devops_cli/k8s/cluster_secrets.py:456:_FALLBACK_FIXTURE_SECRETS_FILE = Path("tests/fixtures/cluster-secrets.toml")` and `src/devops_cli/k8s/cluster_secrets.py:459:def _resolve_fixture_secrets_file() -> Path | None:`. In `src/devops_cli/k8s/cluster_secrets.py:467:def load_cluster_secrets_table(`, resolve the tree with `src/devops_cli/k8s/environment.py:118:def resolve_environment(`, read the cluster secrets path of that tree, and raise `src/devops_cli/exceptions/config.py:10:class ConfigurationError(DevOpsCLIError, ValueError):` with the new message `cluster_secrets_file_not_found` of `src/devops_cli/lang/en/errors.py` when that path is no file; catch nothing. In `tests/k8s/test_cluster_secrets_file.py`, delete the four tests of the fixture fallback and add `test_load_cluster_secrets_table_raises_when_the_tree_has_no_file`, which asserts the error and the path in its message
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secrets_file.py` passes

## 3. Give the fixture folder as the tree to the push and plan tests

Kind: other. Reads: `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_key_refs.py`, `tests/k8s/test_grafana_renderer_optional.py`, `tests/support/paths.py`, `tests/fixtures/cluster-secrets.toml`. Changes: `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_key_refs.py`, `tests/k8s/test_grafana_renderer_optional.py`.

- [ ] 3.1 Import `FIXTURES` from `tests/support/paths.py` in the four modules and give it as the tree to each read of the table: the module-level `tests/k8s/test_cluster_secret_plan.py:80:TABLE_REFS = {secret.ref for secret in load_cluster_secrets_table()}`, `tests/k8s/test_cluster_secret_key_refs.py:89:table_list = tuple(load_cluster_secrets_table())` and each other call of the loader in those modules. Give the loaded table as the `table` argument of each `secrets_by_ref`, `keyring_only_keys`, `generator_option_names` and `generator_for_option` call of the modules. Give `tests/k8s/test_cluster_secret_push.py:132:return runner.invoke(PUSH_COMMAND, ["--context", "test-ctx", *args])` the default `--k8s-dir` of `FIXTURES` when its arguments name none, so each push test passes the tree and `tests/k8s/test_cluster_secret_push.py:954:def test_push_secrets_with_fixture_environment_tree(` keeps its own. Add `test_push_secrets_names_the_missing_cluster_secrets_file`, which runs `--plan` with `--k8s-dir` on an empty folder and asserts a non-zero exit, `ConfigurationError` in `result.exception`, and the name of the file in its message, because `tests/k8s/test_cluster_secret_push.py:56:_push_app = typer.Typer()` reports no error line
  - Verification: `$ uv run devops ci test tests/k8s` passes

## 4. Give the fixture folder as the tree to the object store gate check

Kind: other. Reads: `tests/gate/k8s_checks/object_store.py`, `tests/support/paths.py`, `tests/fixtures/cluster-secrets.toml`. Changes: `tests/gate/k8s_checks/object_store.py`.

- [ ] 4.1 Import `FIXTURES` from `tests/support/paths.py` in `tests/gate/k8s_checks/object_store.py` and pass it as the tree to both table reads of the module, `tests/gate/k8s_checks/object_store.py:1045:refs = [secret.ref for secret in load_cluster_secrets_table()]` and `tests/gate/k8s_checks/object_store.py:1053:refs = [secret.ref for secret in load_cluster_secrets_table()]`, so the k8s row reads the environment rows of the fixture
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 5. Give the deploy-stack and invariant tests a tree that holds the Secret rows

Kind: other. Reads: `tests/support/k8s_tree.py`, `tests/support/paths.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/invariants/test_k8s_manifests.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/fixtures/cluster-secrets.toml`. Changes: `tests/support/k8s_tree.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/invariants/test_k8s_manifests.py`.

- [ ] 5.1 Add `copy_with_cluster_secrets(target: Path) -> Path` to `tests/support/k8s_tree.py`: it copies the tree at `tests/support/k8s_tree.py:14:K8S = REPO_ROOT / "k8s"` to `target`, copies the fixture at `tests/fixtures/cluster-secrets.toml` into the copy as its cluster secrets file, and returns `target`. In `tests/commands/k8s/test_k8s_qdrant_security.py`, build that copy once in a module fixture with `tmp_path_factory` and give it as `--k8s-dir` to `tests/commands/k8s/test_k8s_qdrant_security.py:117:return CliRunner().invoke(DEPLOY_COMMAND, ["--context", "test-ctx", "--no-wait", *args])`, so every deploy-stack run of the module reads a tree that holds the file, because `src/devops_cli/commands/k8s/stack_lifecycle.py:984:table = load_cluster_secrets_table(env=env)` loads the table of the tree of the run. Pass `FIXTURES` to the read at `tests/commands/k8s/test_k8s_qdrant_security.py:237:for secret in load_cluster_secrets_table()` and to `tests/invariants/test_k8s_manifests.py:38:table = load_cluster_secrets_table()`. The runs that prove it are `test_deploy_stack_pushes_secrets_after_namespaces_and_before_manifests_and_helm` and `test_keyring_sources_are_managed_keys_or_declared_keyring_only`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_manifests.py tests/commands/k8s/test_k8s_qdrant_security.py` passes

## 6. Give the deploy-stack command tests a tree that holds the Secret rows

Kind: other. Reads: `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_deploy_stack_urls.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/support/k8s_tree.py`, `tests/support/paths.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`. Changes: `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_deploy_stack_urls.py`, `tests/commands/k8s/test_k8s_devops_stack.py`.

- [ ] 6.1 Give `--k8s-dir` with a copy from `copy_with_cluster_secrets` to every `deploy-stack` run of these modules that pushes Secrets: the dry runs that list the Secrets, such as `test_deploy_stack_dry_run_lists_the_secrets_and_key_names_and_runs_nothing` at `tests/commands/k8s/test_k8s.py:265:result = runner.invoke(app, ["deploy-stack", "--stack", "infra"])`, the runs that name a relative tree, and the runs of a tree that `tests/commands/k8s/test_k8s.py:460:def _pinned_tree(root: Path, unpinned: str | None = None) -> Path:` builds. Give the same copy to the bootstrap run at `tests/commands/k8s/test_k8s.py:1400:result = runner.invoke(app, ["bootstrap", "--no-auto-start", "--stack", "infra"])`, because it keeps the push on. Put the copy under the temporary folder in a folder named k8s and change into the temporary folder for a run that names the relative tree, so the expected relative paths of the output stay the same, and put `tests/fixtures/cluster-secrets.toml` at the root of each pinned tree. Leave every run with `--no-push-secrets` unchanged. A run of `tests/commands/k8s/test_k8s_deploy_stack_urls.py` and of `tests/commands/k8s/test_k8s_devops_stack.py` takes the same copy
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py tests/commands/k8s/test_k8s_deploy_stack_urls.py tests/commands/k8s/test_k8s_devops_stack.py` passes

## 7. Give the remaining deploy-stack tests a tree that holds the Secret rows

Kind: other. Reads: `tests/commands/k8s/test_k8s_logging_stack.py`, `tests/commands/k8s/test_k8s_gpu_placement.py`, `tests/commands/test_environment_root_commands.py`, `tests/support/k8s_tree.py`, `tests/support/paths.py`. Changes: `tests/commands/k8s/test_k8s_logging_stack.py`, `tests/commands/k8s/test_k8s_gpu_placement.py`, `tests/commands/test_environment_root_commands.py`.

- [ ] 7.1 Give `--k8s-dir` with a copy from `copy_with_cluster_secrets` to every `deploy-stack` run of `tests/commands/k8s/test_k8s_logging_stack.py` and `tests/commands/k8s/test_k8s_gpu_placement.py` that pushes Secrets, such as `tests/commands/k8s/test_k8s_logging_stack.py:30:res = cli("k8s", "deploy-stack", "--stack", "logging", "--k8s-dir", "k8s", "--dry-run")` and `tests/commands/k8s/test_k8s_gpu_placement.py:238:result = cli(["k8s", "deploy-stack", "--stack", "llm", "--dry-run", "--k8s-dir", "k8s"])`: put the copy under the temporary folder in a folder named k8s and change into the temporary folder, so the expected relative paths of the output stay the same. In `tests/commands/test_environment_root_commands.py`, copy `tests/fixtures/cluster-secrets.toml` into the tree that `tests/commands/test_environment_root_commands.py:30:def copy_of_k8s(tmp_path: Path) -> Path:` builds, and give `--no-push-secrets` to both runs of `test_deploy_stack_reads_a_copy_of_the_tree_as_it_reads_the_tree`, whose subject is the manifests and the charts
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_logging_stack.py tests/commands/k8s/test_k8s_gpu_placement.py tests/commands/test_environment_root_commands.py` passes

## 8. Give the bootstrap command tests a tree that holds the Secret rows

Kind: other. Reads: `tests/commands/k8s/test_k8s_bootstrap.py`, `tests/commands/k8s/test_k8s_context.py`, `tests/support/k8s_tree.py`, `tests/support/paths.py`. Changes: `tests/commands/k8s/test_k8s_bootstrap.py`, `tests/commands/k8s/test_k8s_context.py`.

- [ ] 8.1 Give `--dir` with a copy from `copy_with_cluster_secrets` to the two bootstrap runs of `tests/commands/k8s/test_k8s_bootstrap.py` that reach the deploy, `tests/commands/k8s/test_k8s_bootstrap.py:231:res = runner.invoke(app, ["bootstrap", "--auto-start", "--stack", "infra"])` and `test_k8s_bootstrap_when_already_running`, because `src/devops_cli/commands/k8s/bootstrap.py:69:stack_life.deploy_stack(k8s_dir=env.root, stack=stack)` pushes the Secrets of the tree that the run resolved. In `tests/commands/k8s/test_k8s_context.py`, copy `tests/fixtures/cluster-secrets.toml` into the tree that `tests/commands/k8s/test_k8s_context.py:73:manifest_dir = tmp_path / "k8s"` builds, which `tests/commands/k8s/test_k8s_context.py:80:result = runner.invoke(app, ["bootstrap", "--dir", str(manifest_dir), "--stack", "infra"])` deploys. Leave `test_k8s_bootstrap_fails_when_start_fails` and `test_k8s_bootstrap_auto_start_failure` unchanged, because they stop before the deploy
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_bootstrap.py tests/commands/k8s/test_k8s_context.py` passes

## 9. Run the Mattermost bootstrap test in a repository whose tree holds the rows

Kind: other. Reads: `tests/commands/test_k8s_bootstrap_mattermost.py`, `src/devops_cli/commands/k8s/mattermost_bootstrap.py`, `tests/support/paths.py`, `tests/fixtures/cluster-secrets.toml`. Changes: `tests/commands/test_k8s_bootstrap_mattermost.py`.

- [ ] 9.1 Add a fixture to `tests/commands/test_k8s_bootstrap_mattermost.py` that changes into a temporary repository with a `.git` folder, a `.devops/project.toml` whose `[kubernetes] dir` names `k8s`, and a copy of `tests/fixtures/cluster-secrets.toml` as the cluster secrets file of that tree. Give it to `test_bootstrap_mattermost_full_flow`, which runs `tests/commands/test_k8s_bootstrap_mattermost.py:117:res = runner.invoke(app, ["k8s", "bootstrap-mattermost"])` and reaches `src/devops_cli/commands/k8s/mattermost_bootstrap.py:433:_push_cluster_secrets(effective_context)`, and that function calls `src/devops_cli/commands/k8s/mattermost_bootstrap.py:341:k8s_push_secrets(` with no `k8s_dir`, so the push reads the tree of the current folder. Keep the `--no-push-secrets` runs and `test_bootstrap_mattermost_no_pod` unchanged
  - Verification: `$ uv run devops ci test tests/commands/test_k8s_bootstrap_mattermost.py` passes

## 10. Run the generate tests in a repository whose tree holds the rows

Kind: other. Reads: `tests/commands/test_config_commands.py`, `src/devops_cli/commands/config.py`, `tests/support/paths.py`, `tests/fixtures/cluster-secrets.toml`, `tests/k8s/test_environment.py`. Changes: `tests/commands/test_config_commands.py`.

- [ ] 10.1 Add a fixture to `tests/commands/test_config_commands.py` that changes into a temporary repository with a `.git` folder, a `.devops/project.toml` that names the `k8s` folder, and a copy of `tests/fixtures/cluster-secrets.toml` as the cluster secrets file of that tree. Give it to every test of the module that runs `devops config set ... --generate` and reaches the generator: `test_generate_the_crawl4ai_token`, `test_a_typed_credential_has_no_generator`, `test_a_token_is_already_stored`, `test_rotate_the_token`, `test_dry_run_of_a_generate` and `test_the_plan_reads_a_stored_token`, because `src/devops_cli/commands/config.py:273:table = load_cluster_secrets_table()` resolves the tree from the project profile of the current folder. `test_a_typed_value_and_generate_together` and `test_rotate_without_generate` stop before that read and need no tree
  - Verification: `$ uv run devops ci test tests/commands/test_config_commands.py` passes

## 11. Drop the devops/renovate row from the product table

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_gitea.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/commands/test_config_commands.py`, `tests/invariants/test_k8s_manifests.py`, `tests/invariants/test_k8s_searxng.py`, `tests/k8s/test_cluster_secret_key_refs.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_cluster_secrets_file.py`, `tests/k8s/test_grafana_renderer_optional.py`, `tests/k8s/test_roadmap_service_key.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/commands/k8s/test_k8s.py`.
Adds: `test_the_product_table_holds_no_renovate_row`

- [ ] 11.1 The new test `test_the_product_table_holds_no_renovate_row` in `tests/k8s/test_cluster_secrets.py` fails before the change, because `tests/k8s/test_cluster_secrets.py:20:def test_the_secret_row_holds_the_two_ids_and_the_key_under_their_variables() -> None:` asserts the product row and `src/devops_cli/k8s/cluster_secrets.py:764:"devops/renovate",` keeps it
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secrets.py tests/k8s/test_cluster_secret_plan.py tests/commands/k8s/test_k8s.py` fails on the base
- [ ] 11.2 Delete the `devops/renovate` row from `src/devops_cli/k8s/cluster_secrets.py:504:CLUSTER_SECRETS: tuple[ClusterSecret, ...] = (` and its name from `src/devops_cli/k8s/cluster_secrets.py:762:OPTIONAL_FEATURE_SECRETS: Final[tuple[str, ...]] = (`. Replace `test_the_secret_row_holds_the_two_ids_and_the_key_under_their_variables` with `test_the_product_table_holds_no_renovate_row`. Delete the expected Renovate rows of `tests/k8s/test_cluster_secret_plan.py` and the expected Renovate line of the secrets list of `tests/commands/k8s/test_k8s.py`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secrets.py tests/k8s/test_cluster_secret_plan.py tests/commands/k8s/test_k8s.py` passes

## 12. Move the Renovate Secret row to homelab in the documents

Kind: other. Reads: `docs/CLUSTER.md`, `k8s/README.md`. Changes: `docs/CLUSTER.md`, `k8s/README.md`.

- [ ] 12.1 In `docs/CLUSTER.md`, rewrite `docs/CLUSTER.md:273:the product cluster secret row` and `docs/CLUSTER.md:276:The product keeps Secret row`, so both say that the cluster secrets file of dan-petty/homelab holds row `devops/renovate` and the product table holds none. In `k8s/README.md`, delete the three `devops/renovate` rows of the Cluster Secrets table at `k8s/README.md:844:setting renovate.github_app_id` and rewrite the bullet at `k8s/README.md:893:holds the GitHub App`, so a person pushes the row from a homelab checkout
  - Verification: `$ uv run devops ci docs` passes
- [ ] 12.2 Edit `docs/CLUSTER.md` and `k8s/README.md` to say that dan-petty/homelab holds the `devops/renovate` Secret row
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: `git grep -n "tests/fixtures" -- src` finds no read of the Secret table.
- Group 3: With an environment tree that has no `cluster-secrets.toml`, `devops k8s push-secrets --plan` exits with an error that names the file.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
