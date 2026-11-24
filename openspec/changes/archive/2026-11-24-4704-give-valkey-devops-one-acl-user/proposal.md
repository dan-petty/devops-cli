# Proposal

## Why

`valkey-devops` has one default user with `requirepass`, so any pod that holds the password reads every key, and the shared caches therefore hold public repositories only (#4704). The change gives the `sweep`, `brain`, `agent` and `metrics` roles their own ACL users with their own key patterns, keeps a private repository's snapshot in the shared tier only under `sweep`, and adds the `valkey.username` setting that the release after this change sends.

## What Changes

- In `dan-petty/homelab`, `valkey-devops` mounts key `users.acl` of Secret `valkey-devops-auth` read-only at `/run/valkey` and starts `valkey-server --aclfile /run/valkey/users.acl`; the `auth.conf` render and the `VALKEY_PASSWORD` env go. `tests/gate/k8s_checks/environment_freeze.py` keeps `k8s/llm/valkey-devops.yaml` unchanged in this repository because `dan-petty/homelab` holds the environment.
- The aclfile keeps the `default` user on with the password of key `password` and defines `sweep`, `brain`, `agent` and `metrics`, each with its own password and its own key patterns.
- In `dan-petty/homelab`, the redis-exporter container sets `REDIS_USER` to `metrics` and reads key `metrics` of `valkey-devops-auth` as `REDIS_PASSWORD`.
- `CLUSTER_SECRETS` generates the four role passwords in `llm/valkey-devops-auth` and builds the derived key `users.acl` from them and from key `password` in the same push, and `k8s/README.md` holds the row of each new key in that step.
- `valkey.username` names the ACL user that a Valkey client sends, with the variable `DEVOPS_CLI_VALKEY_USER`; an empty value sends no user and keeps the default user.
- The tiered snapshot store writes, keeps and reads the shared copy of a private repository only when the process sends the `sweep` user, and removes it under any other user or none.
- `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` name the new setting and its variable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llm-valkey`: The valkey-devops pod loads its ACL users from a Secret, Each valkey-devops role user holds the key patterns of its role, devops-cli's cache Valkey requires its password and admits only namespace devops
- `valkey-endpoint`: A Valkey client sends the user that valkey.username names
- `stack-credential-sync`: The valkey-devops role passwords and aclfile come from one push
- `project-brain/shared-cache`: A private repository's snapshot is shared only under the sweep user

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/valkey/cache.py`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/config/constants.py`
- Documents: `k8s/README.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`
- Tests: `tests/security/test_config_declarations.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/invariants/test_k8s_manifests.py`, `tests/roadmap/stores/test_listing_shared.py`

## Feasibility

- The probe of the request says "The path `valkey.username` is no file of the staging commit. No commit in the history deleted or renamed it.", so `valkey.username` is a setting that this change creates, and `src/devops_cli/k8s/cluster_secrets.py:468:return (*env_rows, *CLUSTER_SECRETS)` shows the Secret table at the staged commit that the push writes.
- `k8s/llm/valkey-devops.yaml:92:key: password` and `k8s/llm/valkey-devops.yaml:137:key: password` show the valkey container and the exporter read one key, and the `command:` block writes `requirepass "%s"` from `$VALKEY_PASSWORD`, so the cache has one password and no ACL user.
- `k8s/llm/valkey-devops.yaml:6:It holds no data of a private repository until it has role ACL users (#4704).` states the premise in the manifest itself.
- `k8s/llm/valkey-devops.yaml:133:- name: REDIS_PASSWORD` shows the exporter sends only a password, so it authenticates as the default user today.
- `src/devops_cli/k8s/cluster_secrets.py:499:restarts=(Workload("deployment", "valkey-devops"),),` holds the row `llm/valkey-devops-auth`, and `src/devops_cli/k8s/cluster_secrets.py:496:generator=_DEVOPS_CACHE_VALKEY_GENERATOR,` shows its one `password` entry is generated, so a push writes one key and restarts the pod.
- `src/devops_cli/k8s/cluster_secrets.py:46:DEVOPS_CACHE_VALKEY_AUTH_KEY = "valkey_devops_password"` is the keyring entry of that value, and the `devops/devops-cli` row adopts the same value as `DEVOPS_CLI_VALKEY_PASSWORD` from key `password` of `llm/valkey-devops-auth`, as `src/devops_cli/k8s/cluster_secrets.py:629:adopt_from=SecretKeyRef("llm", "valkey-devops-auth", "password"),` shows.
- `src/devops_cli/config/settings.py:541:class ValkeyConfig(BaseModel):` holds `url`, `password`, `timeout` and `threat_intel_ttl` and no user, as `src/devops_cli/config/settings.py:559:password: str | None = None` shows, so a client cannot name an ACL user today.
- `src/devops_cli/valkey/cache.py:237:class _SettingsValkeyCredentialProvider(valkey.credentials.CredentialProvider):` resolves the password on connect, and `src/devops_cli/valkey/cache.py:245:return (pw,) if pw else None` shows that the cache tier sends no user.
- `src/devops_cli/valkey/cache.py:243:def get_credentials(self) -> tuple[str] | tuple[str, str]:` returns the password alone today, and `tests/valkey/test_valkey_cache_tier.py` lists no case for it, so the test of the user wiring goes in that module, which group 2 changes.
- `k8s/devops/configmap.example.yaml:157:url: valkey://valkey-devops.llm.svc.cluster.local:6379/0` shows the ConfigMap names the address and no user, and `k8s/devops/roadmap-service/deployment.yaml:113:- name: DEVOPS_CLI_VALKEY_PASSWORD` shows the Service sends the default user's password and no user variable.
- `src/devops_cli/k8s/secret_push.py:332:Count a value the push will store as the keyring's, for later entries of the key.` shows a generated value reaches a later entry of the same push, so the derived `users.acl` reads the four role values that the same push generates.
- `tests/k8s/test_cluster_secret_plan.py:65:DEVOPS_CACHE_PASSWORD = "devops-cache-keyring-value-0001"` and `tests/k8s/test_cluster_secret_plan.py:74:DEVOPS_CACHE_VALKEY_AUTH_KEY: DEVOPS_CACHE_PASSWORD,` show the fake keyring and the row that the new test extends.
- `tests/security/test_config_declarations.py:139:_VARIABLES_OF_LATER_SETTINGS = frozenset(` is the census that the new variable name joins in group 1.
- `src/devops_cli/roadmap/stores/listing_shared.py:183:def snapshot_key(repo: str) -> str:` gives every snapshot one key, `src/devops_cli/roadmap/stores/listing_shared.py:754:class TieredSnapshotStore:` is the tiered store, and `src/devops_cli/roadmap/stores/listing_shared.py:812:if visibility is Visibility.PRIVATE:` keeps a private repository's copy out of the shared tier with no user to tell one role from another.
- `src/devops_cli/config/constants.py:2874:CONST_VALKEY_BRAIN_PREFIX: Final[str] = "valkey:brain:v1"` and `src/devops_cli/config/constants.py:2875:CONST_VALKEY_ROADMAP_PREFIX: Final[str] = "valkey:roadmap:v1"` are the prefixes that the role patterns cover.
- `src/devops_cli/config/constants.py:2902:class BrainWrite(StrEnum):` holds `src/devops_cli/config/constants.py:2916:PRIVATE = "private"` and `src/devops_cli/config/constants.py:2917:REMOVED = "removed"`, the results of a refused private save and of a removed shared copy.
- `tests/roadmap/stores/test_listing_shared.py:78:visibility: Callable[[str], Visibility] = _public,` is the helper that the new case extends with the ACL user of the process.
- The finding about the pinning test is a defect, and group 3 fixes it at its place: `tests/k8s/test_cluster_secret_plan.py:168:def test_table_holds_each_secret_entry_with_its_source_and_restarts() -> None:` builds one row for each entry of `load_cluster_secrets_table()` and compares the whole list at `tests/k8s/test_cluster_secret_plan.py:183:assert rows == [`, where the row of the cache Secret sits at `tests/k8s/test_cluster_secret_plan.py:376:"llm/valkey-devops-auth",` with its one `password` entry, so the four role entries and the derived aclfile entry join that expected list in the same step.
- The finding about the keyring-write list is a defect too, and group 3 fixes it at its place: `tests/k8s/test_cluster_secret_push.py:370:sorted(backend.writes),` compares the exact list of keyring writes of the `--stack llm` push inside `tests/k8s/test_cluster_secret_push.py:def test_a_generated_value_is_stored_in_the_keyring_before_the_apply`, whose expected value holds `tests/k8s/test_cluster_secret_push.py:381:DEVOPS_CACHE_VALKEY_AUTH_KEY,` and `tests/k8s/test_cluster_secret_push.py:380:"runs_index_password",`, so the four generated role keys join that expected list in the same step; the derived `users.acl` entry adds no keyring write, because `src/devops_cli/k8s/cluster_secrets.py:class SecretEntry` states that a derived value is never adopted or generated.
- `tests/invariants/test_k8s_manifests.py:127:def test_readme_lists_the_table() -> None:` reads `k8s/README.md`, `tests/invariants/test_k8s_manifests.py:129:rows = [_readme_row(s, e) for s in CLUSTER_SECRETS for e in s.entries]` builds one row for each entry of the table, and `tests/invariants/test_k8s_manifests.py:130:assert [row for row in rows if row not in readme] == []` fails on a missing row, so group 3 writes the five rows of its new entries into `k8s/README.md` in the same step, and its verify runs that test.
- Group 3 changes `tests/k8s/test_cluster_secret_push.py`, whose applied-key map at `tests/k8s/test_cluster_secret_push.py:251:"llm/valkey-devops-auth": ["password"],` takes the four role keys and `users.acl`, and whose keyring-write list at `tests/k8s/test_cluster_secret_push.py:370:sorted(backend.writes),` takes the four role keys.
- Group 3 changes `tests/invariants/test_k8s_manifests.py`, whose expected set at `tests/invariants/test_k8s_manifests.py:53:DEVOPS_CACHE_VALKEY_AUTH_KEY,` takes the four role keys, because `src/devops_cli/k8s/cluster_secrets.py:def keyring_only_keys` counts every keyring-only key of the table, derived inputs included.
- Group 5 changes the tiered snapshot store, where `src/devops_cli/roadmap/stores/listing_shared.py:806:def _share(self, snapshot: ListingSnapshot) -> BrainWrite:` refuses the shared copy of a private repository today, and adds the case `test_a_private_repository_is_shared_only_under_the_sweep_user` to `tests/roadmap/stores/test_listing_shared.py`, so the code and the test deliver the criterion together.
- The table loader reads the checkout's fixture, as `src/devops_cli/k8s/cluster_secrets.py:420:_FIXTURE_SECRETS_FILE = (` shows and `tests/fixtures/cluster-secrets.toml` holds, so a test of the table needs a checkout of the repository.
- The push planner reads a live Secret, as `src/devops_cli/k8s/secret_push.py:472:def plan_push(selected: Sequence[ClusterSecret], options: PushOptions) -> PushPlan:` shows, so it needs a client of the cluster; the test of `tests/k8s/test_cluster_secret_plan.py` gives it `FakeCluster`.
- The visibility read needs a client of GitHub, and the test of `tests/roadmap/stores/test_listing_shared.py` gives it a visibility double, so no network is reached.
- Loading the settings needs the keyring for `valkey.password` and `valkey.username`; the tests give it the fake keyring of `tests/support/fakes/keyring.py`.
- No new command or verify program enters the plan: each verify runs a row of `devops ci` with `uv`, `pytest`, `kubectl` and `kube-linter` from the runner image, no pod setting changes, and the `kubectl exec` and `curl` checks are person steps, so no failure class is new and no NOT_IN_RUNNER tool is named.
- The first checks that the implementation runs are `uv run devops ci test tests/security/test_config_declarations.py`, `uv run devops ci test tests/valkey/test_valkey_cache_tier.py`, `uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py tests/invariants/test_k8s_manifests.py`, `uv run devops ci test tests/roadmap/stores/test_listing_shared.py`, `uv run devops ci --check --only k8s` and `uv run devops ci docs`.
- The set of users is the four that the issue names; no tool of this run counts it, so the count is unverified and the census is the derived aclfile of the case `test_valkey_role_passwords_and_derived_aclfile`, whose group 3 verify `uv run devops ci test tests/k8s/test_cluster_secret_plan.py` stops when the file lists a user line other than `default`, `sweep`, `brain`, `agent` and `metrics`.
- The owner's comment of 2026-11-21 keeps the `default` user on and defers turning it off to #6600, and the owner's comment of 2026-11-21 asks for the aclfile form of the infra base `acl` component; the plan follows both, so the `user default off` of the body is not built.
- The owner's comment of 2026-11-21 runs the push from the branch before the merge and merges only when `--plan` shows every key `unchanged`, so the Secret holds `users.acl` before Argo CD applies the manifest.

## Existing Tool Considered

`valkey-io/valkey` (BSD-3-Clause, maintained, last activity 2026-11-17) is in use, as the alternatives check records: its ACL with an aclfile gives the named users, the per-key patterns, the command categories and `NOPERM`. The change adds only the wiring that the check lists as lacking: the derived aclfile entry of the Secret table, the Secret mount, the `valkey.username` setting and `REDIS_USER` on the exporter. The issue writes that cost as about 60,000 tokens and 2 hours, plus the person step.

## Dependencies

- #4668: it shares the listing snapshot and the tool facts in Valkey under `valkey:roadmap:*` and `valkey:brain:*`, and it is closed as completed, so its keys are the ones that the role patterns cover.
