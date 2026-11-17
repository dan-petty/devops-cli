# Design

## Decisions

- **Render only when the caller passes a context.** With no context the loader returns the stripped file text, so the call-budget prompts (`roadmap_stage_tools.md`, `roadmap_stage_verify_tools.md`), the embedding eval pairs and the peer grader keep their markers, and a prompt with no variables keeps the text of today.
- **Build one cached `SandboxedEnvironment` in `task_loader` with no loader, no trimming and autoescape off.** `StrictUndefined` raises on a value that a context does not hold, and no trimming keeps the byte-identical output.
- **Give the implement step prompt its three tables through context.** The caller passes `shell_programs`, `local_commands` and `shell_refusals`, and `fill_prompt` and the three placeholders go.
- **Hash the raw templates and the context values in `prompt_version`.** The hash needs no render, so a call with no context does not raise, and a context change gives a new version.

## Rejected alternatives

- **Always render and add a raw read.** It changes more call sites and adds a parameter that the issue does not ask for.
- **Render by a list of prompt names.** A name list duplicates the loader and drifts from the call sites.
- **Reuse `template_environment()`.** It loads JSON scaffolding templates through a `FileSystemLoader` and trims blocks.
- **A new loader class or a `ChoiceLoader`.** The issue says add no new function and no `ChoiceLoader`.
- **Render the personas and the benchmark prompts.** Three benchmark files hold GitHub `${{ }}` expressions that Jinja reads as a template.
- **The default undefined, or `trim_blocks` and `lstrip_blocks`.** The default renders a missing value empty, and trimming changes the text of a prompt that renders byte-identical today.
- **Give `stage_change`, `stage_split`, `stage_tools_research` and `alternatives` their project facts now.** The issue names no fact for them, and they hold no `{{ }}` marker today; a follow-up issue adds them.
