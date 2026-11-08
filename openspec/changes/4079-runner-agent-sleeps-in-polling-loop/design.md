# Design

## Decisions

- **Keep the worker choice of `devops ci test` and change no file under `src/devops_cli/commands/`.**: `src/devops_cli/config/defaults.py:469:DEFAULT_CI_TEST_SERIAL_MAX_FILES: Final[int] = 12` and `src/devops_cli/config/defaults.py:470:DEFAULT_CI_TEST_NARROWED_WORKERS: Final[int] = 4` record the measured choice of #1669, and the full suite keeps addopts' workers (`pyproject.toml:205:addopts = "-n logical --dist worksteal`). The long run comes from six whole-set replays, so the plan does not reverse that decision.
- **Share one report through a module-scoped fixture and add one parametrized item per case.**: Six tests each called `replay_all` over the whole list, so the module replayed the set six times. The fixture shares one report, and the item per case lets xdist distribute the cases and names the failing case.
- **Put the no-poll rule in the implement prompt, not in the shell policy.**: `src/devops_cli/roadmap/implement/implement_step.py:def _tune` sets no command timeout and no polling loop, so the sleep calls are the model's choice. The prompt states the rule and a test holds it.
- **Add no completion-event service and no harness change.**: The shell tool call already returns one result per command, so a service would add a dependency for no need.
- **State the eval score of the prompt change in the implement pull request.**: `docs/ROADMAP_WORKFLOW.md:400:A change to the implement prompt` requires the score on the base and on the branch with one model, and the live command needs the gateway, so a person runs it.

## Rejected alternatives

- **Pass -n auto to every `devops ci test` run.**: The measured choice of #1669 runs a selection of up to `src/devops_cli/config/defaults.py:469:DEFAULT_CI_TEST_SERIAL_MAX_FILES: Final[int] = 12` test modules serially, because worker start-up costs more than it saves for a few modules, and `pyproject.toml:205:addopts = "-n logical --dist worksteal` already gives the full suite its workers.
- **Add a completion-event service or a polling loop to the runner harness.**: `src/devops_cli/roadmap/implement/implement_step.py:def _tune` gives the shell its allowed commands and its environment and sets no command timeout, so a shell call already returns one result when its command exits.
- **Refuse sleep code inside a program that the shell runs.**: The shell policy admits the documented programs and their arguments (`src/devops_cli/roadmap/implement/implement_step.py:467:allowed_commands=list(IMPLEMENT_SHELL_PROGRAMS),`), so matching sleep text inside a program would refuse other probes; the prompt rule removes the choice with no shell change.
- **Keep the six whole-set replays and rely on xdist to spread them.**: A narrowed run of one test module runs serially, as `docs/TESTING.md:158:runs serially for up to` records, so xdist spreads nothing and the module still replays the set six times.
