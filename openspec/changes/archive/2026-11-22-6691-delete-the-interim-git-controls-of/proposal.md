# Proposal: #6691

## Why
#6691: until #3700, the agent phase of a roadmap Job ran in the same container as the App key, so the Jobs kept interim git controls of #2695. Since #3700, the runner Job runs three containers: the init containers `prepare` and `agent`, then the container `publish`. Only `prepare` and `publish` hold the App key, only `agent` holds the model key, `agent` mounts no state folder, and `publish` mounts the run folder and the state folder read only. The controls protect nothing more, and the owner decided to delete them in one pull request (#3700 comment 7066447618). The review of #6732 found two more parts that exist only while the cluster can hold the runner Job of one container (#6691 comment 7079530820).

## What Changes
- Delete `OriginGit`, its new git folder, its copy of the `shallow` file and of the remote-tracking ref, and the pin of the origin URL (`origin_url`): the module `roadmap/implement/git_isolation.py`, its tests, `GitSettingsError`, `link_shallow`, `CONST_GIT_TOKEN_CALL_CONFIG`, `CONST_GIT_SHALLOW_FILE` and the message `implement_git_settings_refused`. The withdraw of the review step deletes the branch from the clone of the plan with a plain `git push --force-with-lease`, after a `git ls-remote` that finds the branch.
- Delete the parser of the git arguments of `_github_pin` (`git_reaches_remote`, `CONST_GIT_NETWORK_SUBCOMMANDS`, `CONST_GIT_REMOTE_NETWORK_ACTIONS`, `CONST_GIT_VALUE_OPTIONS`). Each git child gets the session's token as `GH_TOKEN`. The in-process mint and renewal of the token stay, because the Service needs them.
- Delete the private `GH_CONFIG_DIR` of a gh child: the folder, its candidates in the runtime, temp and data folders, `CONST_GH_CONFIG_DIR_ENV`, `CONST_GH_HOST_ENV`, `CONST_GH_HOSTS_FILE`, `CONST_GH_CONFIG_FILE`, `CONST_GH_PRIVATE_CONFIG_DIRNAME`, `CONST_GH_TEMP_FOLDER_PREFIX` and the four `gh_config_*` messages. A gh child gets the session's token as `GH_TOKEN`.
- Delete the process sweeps and `adopt_orphans`: `end_leftover_processes`, the sweeps of the process runner, of `OriginGit`, of the end of a turn of the agent, of the agent phases of implement, fix-checks and fix-conflict and of `publish_patch`, the autouse fixture that stubbed them, the message `implement_leftover_processes`, and the dependencies `psutil` and `types-psutil`, which only the sweep read. `deny_environment_reads` stays.
- Delete the symlink stop of `implement_step.py` (`_link_failure`, `implement_stop_link`). The refusal of `publish` of a new or changed mode 120000 replaces it, and new tests prove it for a changed link, a file that becomes a link and a link that becomes a file.
- Delete the branch of the first rule of `k8s/devops/roadmap-service/admissionpolicy.yaml` that admits the one container of the old runner template on an `UPDATE`, and the `envFrom` of Secret `devops-cli` on an `UPDATE`. Only a runner Job of one container from before #6518 had that `envFrom`, so the second branch admits nothing without the first.
- Delete the create of the one container `runner` and its reads from the dry run of `devops k8s run-job --template runner`: the template in git makes only the three containers.
- The change is observable: a message, a manifest and the output of a dry run change, so specs get deltas.

## Capabilities
- `subprocess-environment`: remove the requirements of the git parser, of the private gh folder, of its candidates, of the async folder and of the sweeps; add the requirement that each gh and git child gets the session's token as `GH_TOKEN`; change the requirements of the process group, of the `-c` value and of the failed mint.
- `roadmap-implement-runner`: change the requirements of the policy (one container and `envFrom`), of the network git call, of run-job and of the dry run; remove the requirements of the sweeps of `OriginGit` and of the `shallow` file.
- `roadmap-implement-job/runner-job`: remove the requirement of the end of the processes of a step.
- `roadmap-fix-checks` and `roadmap-fix-conflict`: change the order of the hardening of the process.
- `roadmap-implement-step/exit-checks`: remove the stop on a symbolic link.
- `roadmap-phases`: add the scenario of a changed link to the publish.
- `github-app-identity` and `gitops-host-overrides`: each git child gets the token.

## Impact
- A local git child, such as `git status` or `git commit`, now gets the session's token. In a process that acts as the App, a failed mint stops each git child. For a person with no login, the first git child looks up the token, and the process keeps that failed lookup for its git children; a gh call looks again. A Ctrl+C sends SIGINT to the group of a git child before any SIGKILL, so git removes its lock files.
- A gh child reads the gh configuration of the user of the process again. A runner container has an empty home.
- `devops roadmap implement --group` on a workstation runs the agent in the checkout of the person, with the token of the person. The controls that this change deletes never ran on that path: the sweeps ran only in a runner, and `adopt_orphans` only in a runner Job. The shell of a person's agent can read the gh login of the person.
- The change fits one pull request.

## Feasibility
- The live cluster on 2026-11-22: CronJob `devops-cli-runner` holds the init containers `prepare` and `agent` and the container `publish`. The active Jobs of namespace `devops` are one fix-checks Job of the three containers and one stage Job. The runner Jobs of one container `runner` that are left all ended, and their TTL of 86400 s deletes them. The Service patches only a running implement Job (`manage_deadlines`) and a fix-checks Job (`_report`, `resume`), and each fix-checks Job is of the three containers. No live Job uses `envFrom`.
- `--phase all` (`apply_implement`, `fix_checks_phases.repair_round`, `fix_conflict_phases.repair_round`) runs the agent next to the App key. It runs only where `require_runner` passes: `roadmap.implement.in_runner` is true, the process acts as the App, and `service.github_app.token_repository` names the repository. Only `prepare` and `publish` of a runner Job have all three. `build_job` gives each of them the args with its own `--phase` and `--work` last, for the Service and for `devops k8s run-job`, and the admission policy pins that form for a Job of the Service. The default CronJob and the stage CronJob set no `in_runner`, and run-job sets the token repository only for the runner and the stage templates. A workstation has `in_runner` false: `--confirm` starts a runner Job or refuses.
- A live implement Job (#4244) and a live fix-checks Job (#6338) passed on the three containers.

## Existing Tool Considered
- No tool is needed: the change deletes code. Kubernetes keeps the containers apart: each init container and the container `publish` has its own process tree and environment, and the processes of `agent` end when its container ends. git's own `--force-with-lease` keeps a push of another writer.
- Deleted internal code: `git_isolation.py` (`OriginGit`, `origin_url`, `_Folder`, `_read_shallow`, `_sweep`), `git_reaches_remote`, `_private_gh_config`, `_private_gh_folder` and its candidates, `_pinned`, `_end_leftover_processes_in_runner`, `adopt_orphans`, `end_leftover_processes`, `_end_agent_processes`, `_turn`, `_link_failure`, `GitSettingsError`, 13 constants, 7 messages, the one-container branch of the dry run, two branches of the admission policy, and their tests.
