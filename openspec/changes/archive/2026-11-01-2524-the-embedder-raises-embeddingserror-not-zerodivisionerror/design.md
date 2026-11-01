# Design

## Decisions

- **The guard sits at the start of `_embed_ollama`, after `_get_ollama_urls` returns.** The function that uses the URL list checks it. `_get_ollama_urls` also reads `ai.api_base_url`, so the guard tests the list that the function resolves, not `ai.ollama_urls` alone. `_dispatch_embed` stays as it is.
- **The guard has its own message, `ERRORS.rag.embedding_no_ollama_urls`.** It names the model, the provider and the setting `ai.ollama_urls`. `embedding_no_provider` stays for the provider that is none of the four it names.
- **The workflow step files the finding with `devops gh issues create`, with `--label source/agent` and no priority label.** The project command needs only `GH_TOKEN`, and the workflow already sets it and holds `issues: write`. An issue with no `priority/*` label is a candidate, so the next intake round of the Service places it with its type, scope, priority and duplicate flag. AGENTS.md says that intake sets the priority, so the step sets none. The label `source/agent` is what `devops roadmap intake --filed-by agent` set before.
- **The contract test pins the new handoff.** It requires `devops gh issues create` and `source/agent` in the step, and it refuses `devops roadmap intake` and a priority label in the step. A mutation that puts `devops roadmap intake` back must fail the test.

## Rejected alternatives

- **A guard in `_dispatch_embed`, before the call to `_embed_ollama`.** `_embed_ollama` resolves the list (it also reads `ai.api_base_url`), and `_dispatch_embed` has three branches that reach it. A check in `_dispatch_embed` repeats that resolution in a second place.
- **Reuse of `embedding_no_provider` for the guard.** Its text says that the provider is not `ollama` and tells the user to set `ai.tasks.embedding.provider`. Both are wrong when the provider is `ollama`. The text would send the user to the wrong setting.
- **A `--no-embed` option on `devops roadmap intake`.** Intake also needs a model for the proposal: `GatewayIntakeModel.propose` calls the `triage` task through `get_llm_client`, and the runner has no model credential for that either. An option for the embedding alone does not help, and an option that skips the proposal removes the type, priority and duplicate flag. It also adds a command option for one workflow.
- **A step that runs only when a model credential is present.** The runner never has one, so the audit would file nothing, and the finding stays lost. The issue asks that the audit files its finding.
- **A raw `gh issue create` in the workflow.** It works, but the project rule is to use `devops gh`, and the `devops` command is already in the contract test that checks that every `devops` command of a workflow resolves.
