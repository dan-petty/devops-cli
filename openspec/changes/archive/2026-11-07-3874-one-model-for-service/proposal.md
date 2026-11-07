# Proposal

## Why

#3874: the in-cluster config of the Service sends model calls to four groups: `analysis` and `implement` use `deepseek-v4.1-flash-1017`, `verification` uses `claude-sonnet-5-5`, and `chat`, `triage` and `ai.model` use the local aliases `devops-background` and `devops-triage`. While the roadmap steps fail most of the time, a mix of models makes a failure hard to read. On 2026-11-07 the owner decided that the Service uses `deepseek-v4.1-flash-1017` for all model configs until most steps work most of the time.

## What Changes

- In `k8s/devops/configmap.example.yaml`, set `ai.model` and the tasks `verification`, `chat` and `triage` to `deepseek-v4.1-flash-1017`. The embedding task stays `qwen3-embedding:0.6b`, because a chat model cannot embed.
- Add a comment to the template that names the owner decision of 2026-11-07 and says when to undo it: when most steps of the roadmap jobs work most of the time.
- Replace the comment on `ai.max_retries`. The old reason (the background tier serves one request at a time) does not hold for a hosted group. The value stays 1 (see Feasibility).
- Update the documents that name the old slots: `k8s/README.md` (LLM Gateway and Roadmap service), `SECURITY.md` rule 13 (the prompts of intake and chat now leave the cluster), `CONTEXT.md`, and the docstring of the triage row in `src/devops_cli/roadmap/run.py`.
- Add a test over the rendered template: every chat slot resolves to `deepseek-v4.1-flash-1017`, and the embedding slot is the embedding model.
- The change has a spec delta in `roadmap-service-deployment`, because a manifest and the model that a service calls are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: MODIFIED "A model call in the cluster is sent at most two times"; ADDED "Every chat model slot of the Service names one model".

## Impact

- Manifests: `k8s/devops/configmap.example.yaml`. The ConfigMap is not under Argo CD: a person or the owner's deploy applies it with `devops k8s deploy-stack --stack devops`. This change applies nothing to the cluster.
- Tests: `tests/k8s/test_k8s_configmap.py`.
- Documents: `k8s/README.md`, `SECURITY.md`, `CONTEXT.md`.
- Data that leaves the cluster: the prompts of the `triage` and `chat` tasks hold the titles and bodies of issues of the repositories of the Service. These repositories are public today (`dan-petty/devops-cli`). The gateway group asks OpenRouter for providers that do not store or train on prompts (`data_collection: deny`).
- The deployed Service already runs stage, refine and alternatives on DeepSeek through the task `analysis`: the task `stage` takes its fields from `analysis` (`_TASK_PARENTS` in `src/devops_cli/config/settings.py`). So this change does not by itself fix the placeholder replies (`x`, `placeholder`) that the stage job returns.

## Existing code

- Reuse `render_active_devops_configmap` (`src/devops_cli/k8s/configmap.py`) in the test, and `AIConfig.for_task` to resolve a slot with its parent.
- Reuse `tests/k8s/test_k8s_configmap.py`, where the test of the retry value already renders the repository template.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| A test: every chat slot of the rendered ConfigMap names `deepseek-v4.1-flash-1017`, the embedding slot is the embedding model | Group 1 |
| A comment in the template names the owner decision and when to undo it | Group 1 |
| `k8s/README.md` and each document that names `devops-triage` or `claude-sonnet-5-5` for the Service match the template | Group 2 |
| The pull request shows the diff of the ConfigMap that `deploy-stack --stack devops` renders, and applies nothing | Pending a person: see Feasibility. The pull request comment shows the rendered diff |

## Feasibility

All commands ran on `origin/main` at `2475fa2c`, in the worktree of this change.

- The premise holds. `git grep -n "model:" -- k8s/devops/configmap.example.yaml` shows `devops-background` (`ai.model` and `chat`), `devops-triage` (`triage`) and `claude-sonnet-5-5` (`verification`). The rendered template validates as `Settings`.
- Nothing newer did it. `git log --oneline origin/main -- k8s/devops/configmap.example.yaml` has no commit that changes these slots, and a search of the open pull requests for #3874 finds none.
- The chat slots are all the tasks of `AITasksConfig` except `embedding`. A task that the template leaves unset (`metadata`, `compose`, `stage`) takes `ai.model` or its parent (`stage` takes `analysis`). So the test resolves each task with `for_task` and does not list the tasks by hand.
- `Settings` accepts the group: `src/devops_cli/config/settings.py` lets a hosted group name pass the check of `ai.model` (`CONST_AI_GATEWAY_HOSTED_MODELS`). `k8s/llm/gateway/config.yaml` serves `deepseek-v4.1-flash-1017` with `max_input_tokens` 1,048,576, which is above any window the template sets.
- The reason of the `max_retries` comment was one request at a time on the background tier. The gateway group `deepseek-v4.1-flash-1017` has no such limit. It uses `router_settings.num_retries: 5`, with no override on the deployment. So a client retry adds a layer on a call that OpenRouter bills, and the value 1 stays. No measure of hosted failures exists, so the change does not move the value: the test no longer pins it with a reason that is false.
- The command `uv run devops k8s deploy-stack --stack devops --dry-run` exits 0. It lists the manifests and the line `devops/devops-cli-config (rendered from the active config)`. It does not print the content of the ConfigMap, and it prints the cluster context and the Secret key names of the active config, so the output is not pasted. It shows no diff of the ConfigMap. The pull request comment shows the diff of the ConfigMap that `render_active_devops_configmap` renders for example repositories, before and after.

## Existing Tool Considered

No new tool. The ConfigMap template and `devops k8s deploy-stack` render and apply the config already. The change edits the template and adds one test. It deletes no internal code.
