# Proposal

## Why

Issue #2806. The implement Job `devops-cli-runner-20261030-202214-d182` for #2656 ended `Failed`. Its pod was `OOMKilled` at the 4 Gi limit, four minutes after it started. The work of the step was lost. The Job log ended after a `write_file` call and did not name the command that used the memory.

Two faults show here. The pod has a memory limit that a runaway command reaches. And the tool log writes the line of a shell call only after the call ends, with no command in it, so a kill leaves no cause.

## What Changes

- Memory limit of the runner container: from 4 Gi to 12 Gi. The request stays at 4 Gi, so the scheduler places the pod as before and the pod can burst. The CPU limit (2) and the storage limits stay as they are. The numbers that justify this are in Feasibility.
- The pod sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to `2`, the CPU limit. The shell of a step takes this variable from the process when it is set, as it takes `UV_PYTHON`. The project runs `pytest -n logical`, and `pytest-xdist` reads the CPU count of the node, not the CPU limit of the pod, so on the node `hog` a test run starts 48 workers in a pod that has 2 CPU. This is the likely cause of the kill.
- The tool log writes one more line for a call that has a `command`, before the call runs: `Tool call: shell, started: <command>`. The command is the program and its first arguments, masked, on one line, and bounded. The line after the call stays.
- A consumer observes the manifest and the Job log, so the change carries a spec delta: it modifies one requirement of `roadmap-implement-runner` and one of `roadmap-implement-step`, and adds one requirement to each.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-runner`: the memory limit of the template and the worker bound of the test runner.
- `roadmap-implement-step`: the tool log line before a command and the variable that the shell takes.

## Impact

- `k8s/devops/cronjob-runner.yaml`, `k8s/README.md`, `docs/ROUTINE_TASKS.md`.
- `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`.
- `tests/test_k8s_runner.py`, `tests/test_roadmap_implement_tool_log.py`, `tests/test_roadmap_implement_step.py`.
- The admission policy `roadmap-service-jobs` needs no change (see Feasibility).

## Feasibility

- **The kill is real.** `kubectl -n devops get pods` shows pod `devops-cli-runner-20261030-202214-d182-d8rk7` as `OOMKilled` on node `hog`. Prometheus, `max_over_time(container_memory_working_set_bytes{namespace="devops",container="runner"}[30h])`, gives 4,133,457,920 bytes for it, at the 4 Gi limit (4,294,967,296 bytes). The log of that pod ends with eight tool lines, the last one `write_file, ok`. The next call was a shell call, and its line is written only after the call ends, so the command that used the memory is not in the log. The command is therefore not proven. The proposal states the most likely one below.
- **The other Jobs are small.** The 10 other runner pods peaked between 270,610,432 and 1,240,924,160 bytes (6 to 29 percent of 4 Gi). The OOM pod throttled 77 percent of its CPU periods (`container_cpu_cfs_throttled_periods_total` over `container_cpu_cfs_periods_total`). The other pods throttled between 9 and 40 percent.
- **The likely command and its cost, measured.** `pyproject.toml` sets `addopts = "-n logical ..."`. In the xdist source (`xdist/plugin.py`, `pytest_xdist_auto_num_workers`), the worker count is the variable `PYTEST_XDIST_AUTO_NUM_WORKERS` when it is set, else `psutil.cpu_count(logical=True)`. `psutil` reads the CPUs of the node, and a CPU limit of a pod does not change that number. Node `hog` has 48 CPUs (`kubectl describe node hog`). Measured on this host (16 CPUs), the sum of the PSS of the process tree for `pytest tests/test_roadmap_implement_step.py tests/test_k8s.py tests/test_roadmap_implement_tool_log.py` (263 tests): 766 MB with 2 workers in 23 s, 4,488 MB with 16 workers in 24 s. That is about 280 MB for each worker, and the run is not faster. 48 workers cost about 13 GB. So the limit alone does not fix the cause: 12 Gi is below that figure. The worker bound does.
- **The limit.** Hog has 64 GB. It has 43 percent of its memory requested and 24 percent as limits (`kubectl describe node hog`). The Service makes no second Job for a repository while one runs. A limit of 12 Gi with the request of 4 Gi is a burst class: a kill needs a real runaway. If the node comes under pressure, the kubelet evicts the pods that exceed their request first, and a runner is one of them.
- **CPU and storage do not bind.** A CPU limit only slows a process. The 10 completed Jobs ran between 2.5 and 11 minutes against a deadline of 7200 s, so the limit of 2 stays. No `container_fs_usage_bytes` series exists for the runner, there is no eviction event in the namespace, and the 10 other Jobs completed, so the storage limits stay.
- **The roadmap-service pod.** Its peak over 7 days is 611,205,120 bytes, 57 percent of its 1 Gi limit. That is a margin of 43 percent, so its limits stay.
- **The admission policy.** `k8s/devops/roadmap-service/admissionpolicy.yaml` does not pin the resources of a Job (its header says so), and no expression reads `resources`. `tests/test_k8s_job_admission_policy.py` runs every expression against the Job that the template makes, so it covers the new limit. This session cannot run `kubectl create --dry-run=server` as the Service account, so the live admission is reasoned from the CEL text and the test.
- **Not measured.** A Job on #2656 in a pod with the new settings. The cluster is read-only for this session. After the manifest syncs, a person or the next Job confirms the peak in Prometheus.

## Existing Tool Considered

`pytest-xdist` already has the setting: the environment variable `PYTEST_XDIST_AUTO_NUM_WORKERS`. The change builds no CPU detection. Kubernetes `resources` gives the limit. `mask_secrets` of `devops_cli.security.sanitizer` masks the command in the log, `shlex` splits it, and `str.encode("unicode_escape")` escapes control characters. The change builds only the choice of what the line shows. Cost, estimated: about 80 lines of code and tests, about 60k tokens of agent work and one hour of elapsed time. The upkeep is small.

The change deletes no code.
