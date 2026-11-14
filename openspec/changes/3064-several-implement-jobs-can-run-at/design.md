# Design

## Decisions

- **The round counts the running Jobs of its repository against the new setting, as the stage row counts its own.**: `src/devops_cli/roadmap/stage/stage_submit.py:359` already subtracts the running Jobs from a setting and plans with the difference, so the implement row follows a rule that the Service runs.
- **The limit is per repository, not global.**: `src/devops_cli/roadmap/run.py:820` runs the round for one repository and the Service runs one status-lane worker per repository, so a global count would need a store and a clone for every repository in one round.
- **The conflict predicate reads the `Changes:` lines with `group_files`, the reader of the plan check.**: One reader means the round and the plan check see the same paths, and a parent path and its child are known to conflict because a change of one changes the other.
- **The round narrows the targets that the priority walk already took, instead of judging more items.**: `plan_implement` stops at its limit, and judging further items costs a git read of each Staged item's plan; the conflicting item waits for the next round, as the issue asks.
- **The runner Job carries the item label beside the repository label.**: `src/devops_cli/k8s/cluster_job.py:40` gives the label that the stage round reads for one item, and ADR 0021 finds a unit of work by its repository, job and item labels.
- **The change adds no ResourceQuota manifest and no requirement that a quota bounds the Jobs.**: `openspec/changes/archive/2026-11-12-4939-searxng-worker-memory/proposal.md:19` records that namespace `devops` holds no ResourceQuota, and a fixed bound would count the Service's own pods while the runner Job size varies by plan; the API server's answer to the create stays the only cluster check the round makes.
- **A create that the API refuses keeps today's handling: the record and the claim go back and the error raises.**: `src/devops_cli/roadmap/implement/implement_submit.py:488` already releases the claim, so the item is eligible in the next round, and the row's failure ledger shows an API problem instead of hiding it.
- **The merge proof runs real git through `git_for_real` on `process_fake`, and not a recorded transcript.**: The implement tests already answer the `git` program with `git_for_real`, so a real merge needs no new scenario, no new recording and no transcript file, and it proves git's behavior on the very paths that the predicate reads.
- **The generated settings documents get their own group, after the setting exists.**: `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` are written by `uv run devops docs generate` from the field declarations, and `uv run devops ci docs` refuses a row that differs from its source.

## Rejected alternatives

- **Adopt Hatchet for the scheduler.**: It reads no plan, computes no disjoint file set, proves no merge and bounds no namespace, so the custom predicate would still be written beside it.
- **Keep the repository-wide single-Job lock and add the setting alone.**: `src/devops_cli/roadmap/implement/implement_submit.py:546` returns `waiting` while any Job of the repository runs, so a second slot could never fill.
- **Compare the git diff of the two branches after both exist.**: The round decides before it creates the Jobs, and a Planned item has no branch yet.
- **Read free capacity from the node allocatable values before the create.**: The Service's Role grants no `nodes` read (`k8s/devops/roadmap-service/role.yaml`), and a client-side free-capacity read races with the other pods.
- **Add a namespace ResourceQuota manifest to `k8s/devops` as the cluster resource check.**: `openspec/changes/archive/2026-11-13-5483-stage-job-template-entry/design.md:15` records that no ResourceQuota limits Jobs because the runner Job size varies, and a fixed bound in namespace `devops` would count the Service's own pods and refuse one of them.
- **Replay a recorded git transcript for the merge proof, as the `git_fake` fixture does.**: That path needs a new scenario in `tests/support/git_scenarios.py` and a transcript under `tests/fixtures/git/`, and the implement tests already run git for real through `git_for_real` (`tests/support/implement_step.py:142`).

## Security

Crossing: one round of the Service now asks the Kubernetes API for up to `roadmap.implement.max_parallel_jobs` runner Jobs in namespace `devops` instead of one, and each Job still holds a GitHub installation token that names one repository. The Service adds no RBAC rule and reads no `nodes`, and the runner pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]` and `seccompProfile: RuntimeDefault`. A person must confirm that the cluster has room for the extra runner Jobs before the setting goes above 1, and that CronJob `devops-cli-runner` keeps those pod settings. `tests/roadmap/implement/test_roadmap_implement_submit.py` fails if a round creates two Jobs for two items that share a changed path, and `tests/security/test_config_declarations.py` fails if the new variable is not declared.
