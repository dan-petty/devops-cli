# Design

## Decisions

- **The gate decides the catalog, not the devcontainer.** The owner asks for parity with the checks that run in the devcontainer. The devcontainer holds more tools than the gate (kubectl, minikube, docker, scanners). A runner that holds a scanner fails a test that the gate passes (popeye, #2165). So the image holds each tool that a `devops ci` row, a hook, a required job of `ci.yml` or a live-marked test needs, and nothing else. `NOT_IN_RUNNER` records each decision with its reason.
- **One table in code, read by the build and by the tests.** `RUNNER_TOOLS` gives the program, the source, the reasons and the version command. The Dockerfile smoke step, the smoke test of the workflows and the unit tests all call or read the same table, so no second list exists.
- **The pin of each tool comes from its source.** A dev dependency uses the installed distribution, which `uv sync --locked` made equal to `uv.lock` (a test compares them). A tool of the lock uses `tools.lock`, and the check also runs `devops install-tools --check --tool <name>`. A tool that the Dockerfile pins (uv, gh, Node, Python, actionlint) has its pin in the table, and a test compares it with the Dockerfile. A package of apt and a program of the base image have no pin: their version follows the distribution.
- **Trivy and promtool install in the `runner` stage, not in `builder`.** The `service` stage copies `/opt/devops-tools` from `builder`, so an install there would grow the Service image by about 280 MB. The `runner` stage rebuilds on each CI run (`no-cache-filters: runner`), which adds the download (20 s) to that job only.
- **The smoke step runs last and as user 1000.** It then checks the image as the Job runs it, and the workflows run the same module again on the loaded image with the data root set.
- **A size bound in the smoke test.** The image grows by 115 MB compressed (522 to 638 MB) and 337 MB in the new layers. The bound 3000000000 bytes for the size that `docker image inspect` prints (2.78 GB measured) keeps a later change from a silent jump.
- **One shell policy table.** `SHELL_PROGRAMS` holds the programs that the agent shell runs, with an access class and the refused arguments. `SHELL_REFUSALS` holds each refused program and what to do instead. The old constants derive from them. The prompt takes two placeholders that the table fills, so the prompt cannot differ from the table. `docs/ROADMAP_WORKFLOW.md` holds the same rendered table, and a test compares them.
- **A refused argument is a refusal by policy.** The hook checks the words of the command with `shlex`, as the harness does, and raises a retry whose cause is a `PermissionError`. The log counts it as a refused command of that program, like any refusal.
- **The access class names what the program does by itself.** `cat`, `grep`, `ls`, `head`, `tail` and `find` are `read`. A redirect with `>` writes a file in the checkout; the shell does not refuse `>` today, and the agent can write the same file with `write_file`. The shell is no security boundary (the runner is).

## Rejected alternatives

- **Install the whole devcontainer tool set.** Rejected: the popeye test fails with popeye on PATH (`tests/ai/test_tool_executor_contract.py`, "host path reached without a fake"), and the gate does not run these scanners. kubectl, helm and minikube have no use in a Job that mounts no cluster token.
- **Install the tools in the `builder` stage.** Rejected: the Service image would hold Trivy and promtool (about 280 MB) and no Service code uses them.
- **Keep a `--version` line per tool in the workflows.** Rejected: it is a second list of the tools. The check module in the image replaces it.
- **Block `-exec` and `-delete` with `denied_operators`.** Rejected: that list matches substrings in the whole command, so `-delete` would also refuse `git branch --delete`, and `-ok` would refuse any word that holds it. The hook reads the words of one program.
- **Refuse `cat`, `grep` and the others, as today.** Rejected by the evidence: the model repeats the call, and 3 of 13 stops ended on it. The programs only read.
- **A new `devops` command for the check.** Rejected: a command needs help text, README rows and docs sync, and nothing else calls it. `python -m` on the module gives the same result for the build.
