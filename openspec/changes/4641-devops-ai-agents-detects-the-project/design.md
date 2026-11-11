# Design

## Decisions

- **One table of manifests.** `CONST_AGENTS_MD_MANIFESTS` maps each manifest to the language that the toolchain line names, in the order of the line. `ProjectMetadata.manifests` holds the manifests that exist, and `ProjectMetadata.toolchains` gives each language with the `requires-python` range for Python. The template and the model prompt read the same value.
- **Checks only from the hooks.** The pre-push hooks are the checks that the project itself runs. A project with no such hook gets no check line, and its own CI does the checks. No default names a tool that the project may not have.
- **Detection reads the folder.** `devops ai agents --repo` reads a folder that need not be a git checkout, as it does for `pyproject.toml` and the routed documents. So the plan-system slot checks `openspec/config.yaml` on the disk.
- **Rule titles, not bytes.** The invariant test reads the bold title of each numbered rule under `## Rules for every task` with `markdown-it-py`, which the tests use already. A named list holds the rules that only devops-cli has: the ASD-STE100 rule and the decision-model rule.

## Rejected alternatives

- **`uses_openspec(source, ref)` from `devops_cli.openspec.project`.** It reads a commit with `git ls-tree`. The tests of `devops ai agents` run in folders with no git repository, and the command reads the other facts from the disk.
- **A byte-equal test of the template and `AGENTS.md`.** `AGENTS.md` holds 6,498 of the 6,500 allowed characters and has rules that only devops-cli needs, so the two files cannot be equal.
- **Keep the ARCHITECT persona and add the facts.** The persona is a code-review prompt. The task prompt alone gives the model the facts and the shape of the file.
