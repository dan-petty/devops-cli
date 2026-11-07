# A sandboxed read-only run tool for the planner

The planner reads files and runs no command, so a plan can rest on a premise that only a run shows. In the first five plan fixes, 8 of 48 findings rest on such a premise. One of them is a command that looked read-only and removed a key from the config file (#3218). So the planner gets a run tool. A run tool is a risk: a command that writes, a credential that it prints, a path that it reaches, a connection that it opens and a process that it leaves behind are the five ways that a run does harm. This record decides the tool, the commands that it runs, the controls that hold a run, the place of a run, the output of a run and the input of #2695.

## Status

The merge of the pull request that adds this record is the approval of this record. The record holds no approving person, no comment URL and no SHA: a file cannot hold the SHA of the merge that adds it. `git log --follow -- docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` names that merge commit on the default branch, and the merge commit is the record of the approval. A person asks for a change in the review of that pull request, and a merge follows a review that approves. The follow-up issues of this record are filed only after that merge, so no agent builds the tool before the approval.

## Decision

The planner gets one run tool. It runs one command in a separate Kubernetes Job and gives the text of the run, cut and masked, to the planner.

### The allow-list

The run tool runs two kinds of command, and no other command:

- **The help of every command**: `devops <command> --help`. The help of a command prints its options and exits, so it reads the command tree and writes nothing. A command that an issue or a model quotes is not an entry, because an issue is untrusted input and the text of a plan can mislead a model.
- **Each read-only command of the exposure table**: the command that `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py` marks read-only, with the options that its MCP tool publishes. The table is the tested record of a command that only reads: `tools_for_role` in `src/devops_cli/ai/mcp/roles.py` keeps a tool of a job role only when the table marks it read-only, and `tests/ai/mcp/test_mcp_read_only_write_options.py` fails on a read-only tool that publishes an option that writes.

A command that publishes an option for a path is not an entry, even when the table marks it read-only. `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` sets the options that a tool publishes, and a path that a model gives is untrusted input (rule 11 of `SECURITY.md`). So the run tool takes no path from the planner: it reads the copy of the staged commit that the Job mounts, and nothing else.

The allow-list is a table of command paths, and the run tool compares the whole command path. A command that the table does not name is refused with the cause, and the planner then plans without a run.

### The isolation controls

The pod of the run Job holds seven controls, and each one closes a way that a run does harm:

1. **A temporary HOME on an `emptyDir`.** The Service pod mounts a persistent volume at `/home/devops`; the run Job mounts an `emptyDir` with a size limit, so a command that writes to its home or to its cache writes to a volume that ends with the pod. `/tmp` is a second `emptyDir` with a size limit.
2. **A copy of the config with no credential.** The `config` volume is a ConfigMap that a person makes from `devops-cli-config`, with each key that holds a credential removed, and the container has no `envFrom` of Secret `devops-cli`. So a command that prints its configuration prints no credential, and a command that reads the configuration reads no token.
3. **A read-only copy of the staged commit.** The Job mounts the clone of the staged commit read-only, so a write fails with `EROFS` at the path of the repository. The writable paths are the two `emptyDir` volumes only.
4. **No network.** A NetworkPolicy selects the pod of the run Job and admits no egress, DNS included. The egress policy of the Service (`k8s/devops/roadmap-service/networkpolicy-egress.yaml`) admits TCP 6443 to the API server and the perimeter of the namespace admits the gateway, the cache and public HTTPS; the run Job gets none of them.
5. **A CPU, a memory and a wall-clock cap.** The container requests and limits 1 CPU and 2Gi of memory, and the Job sets `activeDeadlineSeconds: 120`. The kernel ends a run that reaches any of the three, so a command that loops, that allocates or that waits ends.
6. **UID 1000.** The pod sets `runAsNonRoot: true`, `runAsUser: 1000` and `runAsGroup: 1000`, and the container sets `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` and drops every capability, as rule 5 of `SECURITY.md` requires.
7. **No service account token.** The pod sets `automountServiceAccountToken: false` and uses the ServiceAccount `devops-cli`, which mounts no token. So a command that reads `/var/run/secrets/kubernetes.io/serviceaccount` reads no file, and a command that calls the Kubernetes API has no credential.

The container sets `seccompProfile: RuntimeDefault`, as the Service pod does at `k8s/devops/roadmap-service/deployment.yaml:47`. The Job sets `backoffLimit: 0` and `restartPolicy: Never`, so a run happens once, and `ttlSecondsAfterFinished` deletes the Job one day after it ends.

### The run location

A run happens in a separate Kubernetes Job. The planner asks for the run, and the Service creates the Job for that one run. A run happens in no other place:

- **Not in the Service pod.** The stage row runs `plan_stage` in the Service process (`_run_stage_adapter` in `src/devops_cli/roadmap/run.py`), and no stage Job exists. A command in that process holds the token of the Service, the persistent home of the Service, the network of the Service to the API server and every credential of Secret `devops-cli`. The seven controls cannot hold a process of that pod, so the run tool refuses a run there.
- **Not in the planner process.** The planner is a model loop with read-only tools, and it keeps no process of its own. A command in that loop would run in the pod of the planner, so the run tool refuses a run that no Job holds. A run that the Job cannot hold fails closed, with the cause, and the plan then says that it ran no command.

The Service creates the Job from a suspended CronJob that holds the template, as the implement row creates its Job from `devops-cli-runner` (`src/devops_cli/k8s/cluster_job.py` and `src/devops_cli/k8s/cluster_job_api.py`). It waits while the Job runs, with the wall-clock cap, and reads the log of the pod. It deletes nothing, because `ttlSecondsAfterFinished` deletes the Job. The Role `roadmap-service-jobs` already allows `create` on `jobs`, `list` on `pods` and `get` on `pods/log`. The ValidatingAdmissionPolicy `roadmap-service-jobs` pins the Job that the Service makes (`k8s/devops/roadmap-service/admissionpolicy.yaml`), so the follow-up adds the rows of the run Job to that policy and to the gate check that runs its expressions.

### The output of a run

The run tool gives the planner text and no more:

- **A byte cap and a line cap.** The text holds at most 8 KiB and at most 120 lines. The cut keeps the first lines and the first bytes, cuts at a line boundary, and ends with one line that says how many bytes and lines it left out. So the first lines of a failure stay, and a command that prints more than the cap states so.
- **`mask_secrets`.** The text passes through `mask_secrets` of `src/devops_cli/security/sanitizer.py` before the planner reads it, so a value that looks like a token, a key or a password is masked. The mask is the second guard after control 2, because a command can print a value that no configuration holds.
- **A quote under `## Feasibility`.** The plan quotes the text in a fenced block under `## Feasibility`, with the command line and the exit code. A run that a signal ends names the signal in place of the exit code. The quote is the evidence of the plan, so a person reads what ran and what it returned, and the plan cannot claim a run that it did not make.

The run tool returns the command line, the exit code and the text. It returns no file and no artifact, because the planner writes a plan and no code.

### The input of #2695

The owner decided on 2026-10-30 that the container separates privilege on this path, and rejected bubblewrap and `unshare` (#2695). This record takes that decision as an input and adopts the container of the run Job as its boundary, with no sandbox library:

- **`unshare` is not available.** The Service pod sets `seccompProfile: RuntimeDefault` (`k8s/devops/roadmap-service/deployment.yaml:47`), and #2695 reports that `unshare --user` fails under that profile. The run Job keeps the profile, so a user namespace is no boundary that it can use.
- **`bwrap` is not in the image.** `NOT_IN_RUNNER` in `src/devops_cli/roadmap/runner_tools.py` names `bwrap` with the reason that the tests of that mark run only with `-m bwrap`, so the runner image holds no bubblewrap. Nobody ran bubblewrap in the pod of the Service, so its failure there is unverified. The record rejects `HostSandbox` (`src/devops_cli/sandbox/host.py`) for this path on that ground, and on the owner decision.
- **The question of the agent-sandbox controller stays open.** The owner comment of 2026-11-01 adds `kubernetes-sigs/agent-sandbox` as a candidate to measure, and #2695 owns that question. This record does not change #2695. A measurement that succeeds replaces the pod spec of the run Job, and the seven controls stay.
- **`SECURITY.md` rule 6 stays true.** Rule 6 confines a model-generated shell command with bubblewrap today, and it holds while no run tool exists. #2695 owns the edit of that rule, and this record changes no behavior, so the rule stays true until the follow-up ships.
