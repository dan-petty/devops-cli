# Design

## Decisions

- **The size comes from the files that the tasks name.** The issue names it. The Service can count it before the Job starts, from `tasks.md` that the round can read with git. The count is the distinct paths in code spans: a span that has a `/` and no space, or a root file with a known suffix. The tasks of a plan name the files they read and change, so the count follows the work of the Job.
- **Two rows.** The repository holds two measured peaks, so the table has two rows, split at 10 files. A middle row would have no measurement behind it.
- **CPU request equals CPU limit, and the worker count is the CPU.** `pytest-xdist` counts the CPUs of the node, not of the pod (#2806). The row holds one CPU value, and the Service writes it to the limit, the request and `PYTEST_XDIST_AUTO_NUM_WORKERS`. One source cannot disagree with itself, and a test checks the Job of each row.
- **The memory limit is a setting, not a row value.** The limit is a burst class that protects the node. It is the same for both rows, 8Gi, and `roadmap.implement.max_memory_limit` raises it. The configuration refuses a value below the largest request, because the API refuses a Job whose request is above its limit.
- **The table is a constant next to the sizing code.** The policy mirrors it, and one gate check holds the two equal: it tries each CPU and memory pair in a grid and expects that exactly the rows of the table pass.
- **The Service overrides the spec before it creates the Job.** The policy sees the final spec, and no second write races the policy. `build_job` takes `resources` and replaces only the values it names.
- **The template keeps 2 CPU and 4Gi.** A Job that a person starts by hand is not selected by the policy and needs a valid default.
- **A plan that is archived at its revision counts zero files.** A retry after a stop in the scoped checks finds the change archived on the branch (#3645). The work left is the checks and the push, which fit the small row.
- **A failed read of the plan stops the round.** The round reads the default branch with git in the same way before it chooses an item, and a failure there raises `GitOperationError`. The size uses the same rule, and the round writes nothing before it has the size.

## Rejected alternatives

- **Three rows.** The repository holds no third measured peak, so the middle row would be a guess.
- **A formula from the file count.** It gives values that no measurement backs, and the policy cannot list them.
- **The packed token count.** The pack step runs inside the Job, after the request is fixed.
- **The peak memory of the previous Job.** A new plan has no previous Job.
- **A key in the Service config for the table.** A config change would not change the policy, so the policy would refuse the new class.
- **Patch the Job after it is created.** The policy would admit the template size first, and a patch can be refused after the Job exists.
- **A flag of `devops k8s run-job`.** The Service calls the API. A flag adds a process between the Service and the cluster.
- **LimitRange.** A LimitRange cannot refuse a request above the table and cannot check the environment value.
- **Parse the quantity with the Kubernetes client.** `kubernetes.utils` imports the whole client, which the startup budget refuses for a settings module. The setting is a whole number of Gi, which a pattern checks.
