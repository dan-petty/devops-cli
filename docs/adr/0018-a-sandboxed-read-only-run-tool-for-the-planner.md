---
status: accepted
date: 2026-11-07
decision-makers: [owner]
issue: 3242
body-hash: 7cf478ed6e7473a8ab956143f8d2bd167632bf0d19c8e2a4dce3647b82dee910
---

# A sandboxed read-only run tool for the planner

The planner reads files and runs no command, so a plan can rest on a premise that only a run shows. In the first five plan fixes, 8 of 48 findings rest on such a premise. One of them is a command that looked read-only and removed a key from the config file (#3218). So the planner gets a run tool. A run tool is a risk: a command that writes, a credential that it prints, a path that it reaches, a connection that it opens and a process that it leaves behind are the five ways that a run does harm. This record decides the tool, the commands that it runs, the controls that hold a run, the place of a run, the output of a run and the input of #2695.

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

## Considered Options

A run needs a boundary around one command. This record measures four open options against the seven controls of the Decision and against the place of a run.

- **bubblewrap.** `HostSandbox` (`src/devops_cli/sandbox/host.py`) wraps bubblewrap: it binds the repository read-only, mounts a private `/tmp`, clears the environment and kills the process group at the output cap. It lacks a user namespace here. #2695 reports that `unshare --user` fails under `seccompProfile: RuntimeDefault`, and the run Job keeps that profile. It also lacks a binary in the image: `NOT_IN_RUNNER` in `src/devops_cli/roadmap/runner_tools.py` names `bwrap`, and nobody ran bubblewrap in the Service pod, so its failure there is unverified. The owner rejected it on 2026-10-30.
- **nsjail.** nsjail is an open Linux sandbox that uses namespaces, seccomp-bpf and cgroups, and it sets the CPU, the memory and the process limits that control 5 needs. It lacks the same user namespace: it starts a user namespace and a network namespace, and the profile of the pod refuses both. It also adds a second binary and a policy file to the runner image, to keep and to test, and it closes no way that the pod does not close.
- **gVisor.** gVisor (`runsc`) is an open user-space kernel. It gives the strongest boundary of the four: a command sees a kernel of its own, so a defect of the kernel of the pod reaches no host. It lacks a runtime in the cluster: the cluster declares no RuntimeClass for `runsc`, so a Job needs a node that installs gVisor, a RuntimeClass and a second measurement of the image of the run Job. A person changes the cluster for it, and the container boundary needs no such change.
- **The agent-sandbox controller of `kubernetes-sigs`.** The owner comment of 2026-11-01 names it as a candidate to measure, and #2695 owns that question. It gives a Sandbox custom resource and a controller that makes the pod, so it replaces the Job that the Service makes. It lacks a controller in the cluster and a measurement that the owner has accepted. This record does not measure it. A measurement that succeeds replaces the pod spec of the run Job, and the seven controls stay.

**The cost of the container boundary** is about 3,000 tokens to write, about 500 tokens a month to keep and one day of work. The work is a Job template, a NetworkPolicy, a ConfigMap without a credential, a Role row and the rows of the admission policy. **The cost of a sandbox built from scratch**, a namespace tool of the repository with its own policy, its own tests and its own profile, is about 40,000 tokens and two weeks. It also keeps a second path to review and to patch. The container is the cheaper boundary, and the cluster already gives it.

## Rejected options

- **A deny list of the commands that write.** Rule 7 of `SECURITY.md` records that the path filter of the kube-api denies a known write, and a new subresource passes it until the list names it. A command that writes and that the list does not name runs, and #3218 shows that a command that looked read-only deleted a key. The allow-list of the Decision fails closed: a command that the table does not name does not run.
- **A command that an issue or a model quotes.** An issue is untrusted input, and the text of a plan can mislead a model. The run tool takes no command from the text of an issue, and a model quotes no command into the allow-list.
- **`--help` only.** The help of a command prints its options and reads no state, so it proves no premise of a plan. A plan that rests on a value of the configuration needs a read of that value.
- **`HostSandbox` with bubblewrap inside the Service pod.** The owner decision of 2026-10-30 rejects bubblewrap and `unshare` on this path. `NOT_IN_RUNNER` in `src/devops_cli/roadmap/runner_tools.py` leaves `bwrap` out of the runner image, and #2695 reports that a user namespace fails under the profile of the pod. The Service pod also holds the token, the home directory, the network and the credentials that the seven controls close.
- **A NetworkPolicy alone.** A policy closes the network and no other way that a run does harm: a write, a credential that a command prints, a process that it leaves behind. The seven controls close the five ways, and the policy is one of the seven.
- **The Service pod.** The stage row runs `plan_stage` in the Service process (`_run_stage_adapter` in `src/devops_cli/roadmap/run.py`). A command in that process holds the token of the Service, the persistent home of the Service, the network of the Service to the API server and every credential of Secret `devops-cli`. The seven controls cannot hold a process of that pod.
- **A stage Job.** No stage Job exists: the plan runs in the Service pod, so a stage Job would be a second mechanism beside the plan. The plan would then run in the pod that the run tool refuses, and the boundary would depend on a row that does not exist.
- **The full output of a run.** A command can print a megabyte, and a plan holds a token budget. The byte cap and the line cap cut the text to 8 KiB and 120 lines, and the cut names what it leaves out.
- **A model summary of the output.** A summary can drop the line that shows the failure, and it can add a fact that the command did not print. The planner reads the cut text, and the plan quotes that text under `## Feasibility`.
- **A fake executor that returns the expected text.** A fake proves what a test wrote and no boundary. #3218 shows that a command can do harm that its name does not show, so the proof tests run a real command in the real Job.

## Proof

One new test module, `tests/roadmap/test_roadmap_run_job.py`, proves the three ways that the controls must close. A follow-up adds it, and this record names it so the follow-up builds no other proof.

The three tests read the Job that the follow-up renders from its template with `build_job` of `src/devops_cli/k8s/cluster_job.py`. They open no connection and start no pod:

- `test_a_write_outside_the_read_only_copy_fails` asserts that the pod spec mounts the clone of the staged commit with `readOnly: true`, and that it mounts no writable volume at the path of the repository. The two `emptyDir` volumes are the only writable paths.
- `test_a_read_of_a_credential_and_of_the_service_account_token_finds_no_file` asserts that the container holds no `envFrom` of Secret `devops-cli`, that the `config` volume comes from the ConfigMap without a credential, and that the pod sets `automountServiceAccountToken: false`.
- `test_an_outbound_connection_fails` asserts that a NetworkPolicy selects the labels of the pod of the Job, that its `policyTypes` holds `Egress`, and that it admits no egress and no DNS.

One live test, `test_the_run_job_holds_the_three_controls`, runs the same three cases in the cluster: it writes a file beside the clone, it reads `/var/run/secrets/kubernetes.io/serviceaccount/token` and the `config` volume, and it opens a connection to a public address. Each case must fail. The test carries the marker `k8s`, which the follow-up adds to `pyproject.toml`, and a run selects it only with `-m k8s`, as `NOT_IN_RUNNER` selects the tests marked `bwrap`.

## Follow-ups

Four issues build the tool. Each one names this record and lists #3242 as a dependency, and the Service files it only after the merge of this record:

1. **The run Job manifest.** A suspended CronJob holds the pod spec of the seven controls, a NetworkPolicy selects its pod, a ConfigMap holds the configuration without a credential, and the Role `roadmap-service-jobs` gets `get` on the CronJob. The rows of the run Job go into the ValidatingAdmissionPolicy `roadmap-service-jobs` (`k8s/devops/roadmap-service/admissionpolicy.yaml`) and into the gate check that runs its expressions.
2. **The allow-list builder.** A table of command paths, built from `CONST_MCP_EXPOSURE_TABLE` of `src/devops_cli/config/constants.py` and from `_PATH_PARAM_RESTRICTIONS` of `src/devops_cli/ai/mcp/generator.py`, refuses a command that the table does not name, with the cause.
3. **The output cut and mask.** The cut to 8 KiB and 120 lines, the line that names what it leaves out, and the call to `mask_secrets` of `src/devops_cli/security/sanitizer.py`.
4. **The proof tests.** The offline tests of `tests/roadmap/test_roadmap_run_job.py`, the live test marked `k8s`, and the marker in `pyproject.toml`.

## Consequences

- A plan can run a command and quote its text and its exit code under `## Feasibility`, so a person reads what ran. A plan that rests on a false premise that a run shows becomes rare.
- The Service makes one Job for each run and waits for it, with the wall-clock cap of 120 s. `ttlSecondsAfterFinished` deletes the Job one day after it ends, so a run leaves no pod behind.
- A run that the Job cannot hold fails closed, with the cause, and the plan says that it ran no command. A refused command changes no plan.
- The allow-list follows the exposure table and the generator, so a command that becomes read-only enters the table once and needs no second edit. A command that publishes a path option stays out, even when the table marks it read-only.
- The admission policy of the Service grows by the rows of the run Job, and its gate check grows with them. A run Job that a person does not pin is refused.
- `SECURITY.md` rule 6 stays true until the follow-up ships, because this record changes no behavior. #2695 owns the edit of that rule and the measurement of `kubernetes-sigs/agent-sandbox`.
- The boundary is the container of the pod, so a defect of the kernel of the host stays a risk that the seven controls do not close. The owner took that risk on 2026-10-30, and a gVisor RuntimeClass or the agent-sandbox controller can close it later without a change of the tool.

## Status History

The merge of the pull request that adds this record is the approval of this record. The record holds no approving person, no comment URL and no SHA: a file cannot hold the SHA of the merge that adds it. `git log --follow -- docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` names that merge commit on the default branch, and the merge commit is the record of the approval. A person asks for a change in the review of that pull request, and a merge follows a review that approves. The follow-up issues of this record are filed only after that merge, so no agent builds the tool before the approval.
