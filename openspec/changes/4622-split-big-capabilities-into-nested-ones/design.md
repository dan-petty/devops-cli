# Design

## Decisions

- **One nested capability for each gate or module.** The split groups the requirements by the gate or the module that they describe, so that two pull requests about different gates archive into different files. For example, `roadmap-stage/paths-gate`, `roadmap-stage/trace-gate`, `roadmap-stage/criteria` and `roadmap-stage/selection`. The largest nested capability holds 36 requirements, which leaves room under the limit of 80.
- **The area holds no spec of its own.** `openspec/specs/<area>/spec.md` and `openspec/specs/<area>/<name>/spec.md` can both exist, but then a delta that names the area archives into a file next to its nested capabilities. A delta of an old plan would then add requirements to the wrong place with no error. The invariant test refuses an area with a `spec.md`, so such a delta fails in the pull request that archives it.
- **The split is word for word.** A script moved each requirement block as it was, placed by its name, and wrote the blocks of each nested capability in the order of the old file. `openspec show --json` compares the name, the text and the scenarios of each requirement on `origin/main` and after the split. A requirement on `main` that the map does not place stops the script, so a rebase over a new requirement is safe.
- **OpenSpec lists the capabilities, and the job reads their files.** `read_base_specs` calls `openspec list --specs --json` once and reads the `spec.md` of each id. `openspec show` for each of 290 capabilities costs one process each, and the stage job needs only the purpose, the names and the statements, which `read_spec` already reads from the file. `StageTools.read_spec` uses the same listing function.
- **No OpenSpec, no base spec.** With no `openspec` on the path, the stage job validates nothing, and the tool `read_spec` already answers that it reads no spec. `read_base_specs` gives no base spec in the same case. The Service image installs OpenSpec, so the job there always reads the specs.
- **The readers of a commit take a folder path.** `specs_at`, `read_change` and the refine context read the files of a commit through git, with no checkout, so OpenSpec cannot list them. They take the folder path under `specs/` at any depth as the capability, which is the rule of `spec-discovery.js`.
- **A nested capability covers a module by its area.** Refine names the specs that cover a cited module: a capability covers a module when its name is the key of the module or a start of it. For a nested capability, the area is that name, because the area keeps the name of the old capability.
- **The archive stays in the closing pull request.** The owner chose the split and no change of rule 1 of `AGENTS.md`.

## Rejected alternatives

- **A recursive folder walk in `read_base_specs`.** It would keep the job independent of the tool, but it copies the discovery rules of OpenSpec (dot folders, links, the root file), and the issue asks to delete the walk.
- **A nested capability for each requirement name prefix.** The names of the requirements do not follow a prefix scheme, so the groups would not follow the gates.
- **A pytest that compares the requirements before and after the split.** The comparison holds only for the commit of the split: the next archive adds a requirement and the test fails. The comparison runs once with `openspec show --json` and its result is in the pull request.
