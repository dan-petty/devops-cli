# Design

## Decisions

- **Raise the limit to 12 Gi and keep the request at 4 Gi.** The owner said to raise or remove the limits where needed. The measured peak of normal Jobs is 1.24 GB at most, so 4 Gi is right for the request: the scheduler needs only that. A limit of 12 Gi lets a step burst. A kill then needs a real runaway, and the node has room (64 GB, 43 percent requested). 12 Gi is below the cost of 48 test workers (about 13 GB, from 280 MB each), so the limit is not the fix of the cause.
- **Bound the test workers with the variable that xdist reads.** The cause is a worker count from the CPUs of the node. `PYTEST_XDIST_AUTO_NUM_WORKERS` is the documented setting of `pytest-xdist` for this, and `-n logical` honors it. Setting it to the CPU limit (2) cost no time in the measured run (23 s with 2 workers, 24 s with 16). The manifest holds the value, and a test checks that it equals the CPU limit, so the two cannot drift.
- **The shell takes the variable from the process, like `UV_PYTHON`.** The shell of a step gets only `PATH`, `HOME` and the locale of the process, plus `shell_environment`. So a variable on the pod does not reach `pytest` unless `shell_environment` passes it. The function passes it only when the process has it, so a developer machine keeps its own count.
- **A separate line before the call, not a change of the line after it.** The line after the call has the outcome, which a killed call never reaches. The new line needs only the command, so it can come first. The line after the call stays as it is, so the count of refused programs and the other readers of the line do not change.
- **The command line shows a bounded form.** The first word must be a known program (the rule of the line after the call). Any other first word shows as `other`, because a first word can be a password or a token that the model read from a file. For a known program the line shows at most `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS` words. The text is read to a fixed length, masked with `mask_secrets`, escaped with `unicode_escape` so that it is one line, and cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS`. The mask runs before the cut, so a cut cannot split a secret.
- **Residual risk, accepted.** The mask finds a secret by its form. A password that the model read from a file and passes as the argument of an allowed program, such as `git commit -m <password>`, has no form and stays in the log. The Job log is the only evidence of what the agent did, and a command with no argument cannot show a cause like `-n 48`. The issue asks for the arguments. The bound on words and characters and the allowlist of programs limit the harm.
- **CPU and storage limits stay.** See Feasibility in the proposal for the numbers.
- **The roadmap-service limits stay.** Its peak is 57 percent of its limit.

## Rejected alternatives

- **Raise the limit only.** The evidence shows 48 workers cost about 13 GB. A limit of 12 Gi would still kill the same run, and a limit of 16 Gi would leave a small node with no margin. It fixes the symptom of one run and not the cause.
- **Bound the workers only, keep 4 Gi.** The cause of this kill is not proven, as the log has no command. Another command, such as `mypy --strict` on a large file set, can also pass 4 Gi. The owner asked for a burst class, and the cost is a limit that the node can pay.
- **Remove the memory limit.** A pod with no limit has no cgroup cap, so a runaway command would make the kernel kill other pods on the node. The 12 Gi limit keeps a runaway inside its pod.
- **Detect the cgroup quota in the code and pick the worker count.** It is hand-rolled code for what a variable of the installed tool does.
- **Change `addopts` to `-n 2`.** It slows the full suite on a developer machine and in CI, where the CPUs are real.
- **Write the command in the line after the call.** A killed call never writes it, which is the case the issue is about.
- **Log the whole command.** A command can be long and can hold a secret. The words and characters are bounded.
