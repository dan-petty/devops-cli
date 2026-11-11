# Proposal: #4628

## Why

The stage facts context (`src/devops_cli/roadmap/stage/stage_context_facts.py`) read four devops-cli paths from the staged commit of the target repository: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/runner_tools.py`, `Dockerfile` and `k8s/devops/cronjob-runner.yaml`. When a path was absent, it raised `RoadmapStageError` ("Staged source moved or missing"). The trigger patterns match most issue texts (retry, review, failure, and about 40 tool names such as `uv` and `python`), and the commits of the 6 other repositories hold no devops-cli module. So the stage gave no verdict for most items in those repositories. On 2026-11-11 the Service log shows this error for dan-petty/dotfiles#1 and for dan-petty/homelab#1 and #2 (#4628).

The failure classes and the runner tools describe the runner image, and the runner image is the devops-cli image for every repository. The installed modules hold these facts, so the commit of the target does not need to hold them.

## What Changes

- The failure taxonomy section reads `FailureClass` and `ACTION_BY_CLASS` from the installed `devops_cli.roadmap.failure` module.
- The runner capabilities section reads `tool_names()` and `NOT_IN_RUNNER` from the installed `devops_cli.roadmap.runner_tools` module. Each `NOT_IN_RUNNER` line now holds the reason text. The ast extractor wrote the Python name of a constant (for example `_NO_CLUSTER`) or `exclusion rule` for 22 of 28 entries.
- The Dockerfile packages line and the pod security subsection come from the staged commit only when that commit holds `src/devops_cli/roadmap/runner_tools.py`. Each one is left out when the commit lacks that path or the file of the fact. The builder raises no error.
- The ast parse of the staged `failure.py` and `runner_tools.py` and the constant `FAILURE_TAXONOMY_PATH` are deleted.
- A test asserts that `runner_tools.py`, the `Dockerfile` and the pod manifest exist in the repository, so a move fails in CI and not in a Job.
- The stage eval keeps its fallback to the checkout for the image fact files. A case whose commit and checkout lack the module files now reaches the model.

The stage context text and the outcome of the stage job are observable, so the change has spec deltas for `roadmap-stage` and `roadmap-stage-eval`.

## Capabilities

- `roadmap-stage`: modifies `Failure taxonomy in staging context`, `Runner capability facts in staging context` and `Repository-derived facts`.
- `roadmap-stage-eval`: removes `The live run reads the runner facts in the checkout` and adds `The live run reads the image facts in the checkout`, because two of its scenarios state the raise that this change deletes.

## Impact

- The stage job gives a verdict for an item of another repository whose text names a tool or a failure word.
- For a devops-cli commit, the facts text is the same except for the 22 `NOT_IN_RUNNER` lines that now hold their reason text. The text grows from 2,655 to 5,985 characters for an item that triggers both sections.
- No setting, command, message or manifest changes. The change fits one pull request.

## Feasibility

- Source at `origin/main` (`a87442a0`): `build_failure_taxonomy_context` and `build_runner_capabilities_context` raised `RoadmapStageError` when `read_file` returned None for one of the 4 paths.
- Service log, Loki query `{service_name="roadmap-service"} |= "Staged source moved or missing"` over 24 h on 2026-11-11: 2 lines. The line of 14:37Z names dan-petty/dotfiles#1, and the line of 15:19Z names dan-petty/homelab#1 and #2. Each names `src/devops_cli/roadmap/runner_tools.py`.
- Command output: the base builder and the new builder ran on the text of dan-petty/dotfiles#1 and on the files of its `main` commit `7d80c9105f8a`. The base builder raised `RoadmapStageError: Staged source moved or missing: src/devops_cli/roadmap/runner_tools.py`. The new builder gave the runner capabilities section.
- Command output: the base text and the new text for the devops-cli files differ in 22 of 86 lines. Each of the 22 lines is a `NOT_IN_RUNNER` entry whose base value was `_NO_CLUSTER`, `_SCANNER`, `_NO_GATE_STEP` or `exclusion rule`. The issue expected a byte-equal text. That holds for every other line, and the 22 base lines held the name of a constant, not a fact. The new lines hold the reason text of the installed dict.
- `tool_names()` gives the same list as the ast extractor, and the values of `FailureClass` and `ACTION_BY_CLASS` give the same lowercased names (command output, both comparisons `True`).

## Existing Tool Considered

No open tool covers the need: the values are the runtime constants of this project. The standard library import of `devops_cli.roadmap.runner_tools` and `devops_cli.roadmap.failure` covers it, and the stage already imports both modules. `mkdocstrings/griffe` (checked in #3406) reads a docstring or a signature, not a runtime constant. The change deletes about 100 lines of internal code: `_extract_failure_classes`, `_extract_action_by_class`, `_extract_failure_taxonomy`, `_extract_runner_tools_list`, `_extract_dict_exclusions`, `_extract_runner_tools` and `FAILURE_TAXONOMY_PATH`. Cost: about 80,000 tokens and 1 hour to build, and about 2,000 tokens a month to keep.
