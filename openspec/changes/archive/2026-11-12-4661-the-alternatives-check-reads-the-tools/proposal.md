# Proposal

## Why

Issue #4661: the alternatives check does not read the tools that the project already uses, and it does not read what an ADR decided. The census of 2026-11-11 read the 330 alternatives blocks of the repository. 58 of its 97 `covers` and `partly` verdicts name a tool that the project already uses. The check gives `in-use` only when the text of the item names the tool (`_verdict_of` in `src/devops_cli/roadmap/alternatives.py`). 1 of its 5 `rejected` verdicts is false: #3258 says that ADR 0010 rejects OpenSpec, but ADR 0010 adopts it. The job tests only that the title or the options of the ADR name the tool. 88 tool strings name 81 tools, so the verdicts of one tool do not join. And a change of an ADR starts no recheck: #3064 still names Hatchet after ADR 0008.

## What Changes

- A new module `src/devops_cli/roadmap/inventory.py` holds the inventory of the tools in use. It has three sources, the cheapest first. The SPDX SBOM that the GitHub dependency graph exports gives the package URL of each package of a manifest, a lock file or a workflow, with one request. The files under `roadmap.alternatives.inventory_paths` of a clone (`k8s`, `tf`, `.devcontainer` and the tools lock by default) name the services, images and CLIs that no manifest holds, as a whole word in any case. deps.dev links a GitHub project to the packages whose source it is, so the repository `modelcontextprotocol/python-sdk` is the PyPI package `mcp` of the SBOM. The job asks deps.dev only when the SBOM holds a package and the other two tests fail. A run with no clone reads the SBOM and deps.dev only.
- A new store method `dependency_purls()` reads the SBOM (`GET /repos/{owner}/{repo}/dependency-graph/sbom`). It is in `RoadmapStore`, `GitHubRoadmapStore` and `InMemoryRoadmapStore`. A dependency graph that is off gives 404, which is an empty SBOM.
- A code rule in `validate_reply`: a `covers` or `partly` tool that the inventory holds gives `in-use` with no proposal of the model, after `rejected`. The comment and the block say "The repository already uses this tool." A failed read of deps.dev skips the item with a named reason and records the failure.
- `rejects(adr, *tool_names)` in `src/devops_cli/roadmap/adr.py` replaces the name test of the confirmed ADR. An ADR rejects a tool when an option that says `rejected` or `not chosen` names the tool, and its title and its other options do not. ADR 0010 names OpenSpec in its chosen option, so it rejects no OpenSpec.
- A check records two more keys in the job record. `alternatives.tool_id` is the canonical id of the tool: the deps.dev project key `github.com/<owner>/<name>` in lower case of its GitHub project, which a PyPI tool takes from the URL of its source, else `pkg:pypi/<name>` with the canonical name of `packaging`. `alternatives.adr_hash` is the hash of the ADR entries that the model saw.
- `plan_alternatives` reads the ADRs once for each run before it selects the items, and `select_items` takes an item of no skip class whose recorded `adr_hash` differs from the hash of the ADRs at HEAD, or that recorded none.
- The CLI option `devops roadmap alternatives --source <clone>` gives the clone. The Service row `alternatives` gets the clone of the model lane (`needs_clone`), which stage and refine already make.
- The dry run lists the read of the SBOM and the read of deps.dev. The ADR reads move from the condition "the run checks an item that is no skip class" to each run.
- A new dependency, `packageurl-python`, parses the package URLs of the SBOM.
- The change has a spec delta, because a verdict, a record key, an option, a setting and a dry-run line are observable (`openspec/config.yaml`).
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: the inventory of the tools in use, the code rule for `in-use`, the test of a rejecting ADR, the canonical id, the ADR hash and the recheck after an ADR change.

## Impact

- Code: `src/devops_cli/roadmap/inventory.py` (new), `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/adr.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Dependencies: `pyproject.toml`, `uv.lock` (`packageurl-python` 0.17.6, MIT)
- Tests: `tests/roadmap/test_roadmap_alternatives_project_facts.py` (new), `tests/fixtures/roadmap/alternatives_census.json` (new), `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_adr.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, `tests/roadmap/stores/test_roadmap_github_store_repository.py`, `tests/support/fakes/roadmap_store.py`, `tests/support/fakes/github_repository.py` (the SBOM route of `GitHubFake`)
- Documents: `docs/roadmap/alternatives.md`, `docs/ROADMAP_WORKFLOW.md` (the record keys), `CONTEXT.md`, `k8s/README.md`, and the generated `docs/CONFIGURATION.md`, `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md`
- Egress: one GET to `api.deps.dev` for each checked tool that the SBOM and the deployed files do not hold, only when the SBOM holds a package. deps.dev is a public, keyless API.
- Left as they are, on purpose: the prompt `src/devops_cli/ai/tasks/roadmap_alternatives.md`, because the new rule is code and the model sees no inventory; the shared cache of the inventory, which the tiered cache item of the plan #4624 adds; the per-item digest and the reference step, the other children of #4624 that change this spec.

## Feasibility

- The SBOM export works and holds package URLs. `uv run devops gh api repos/dan-petty/devops-cli/dependency-graph/sbom --jq '[.sbom.packages[].externalRefs[]? | select(.referenceType=="purl")] | length'` gave 431 on 2026-11-12. The census fixture records the 402 package URLs at the commit it names. Each package of the export has `externalRefs` with `referenceType` `purl`. The GitHub REST documentation of the endpoint says that it answers 404 when the dependency graph is off.
- The SBOM does not hold the deployed services. The census measured that it holds 33 of the 58 tools in use. The other 25 are services, images or CLIs, for example LiteLLM, Grafana, git, notifications-engine and Renovate. A whole-word test over `k8s`, `tf`, `.devcontainer` and the tools lock finds them. The replay test runs the inventory over the 97 census items: 56 of the 58 tools in use give `in-use`. The two misses (#1387 and #2003) are `argoproj/notifications-engine`, a Go library that Argo CD holds inside its image. One tool that the census counted as new (#3612) is in the SBOM at the recorded commit.
- deps.dev links a repository to its packages. `GET https://api.deps.dev/v3/projects/github.com%2Fmodelcontextprotocol%2Fpython-sdk:packageversions` gave 379 package versions on 2026-11-12. The PyPI package `mcp` is one of them with `relationType` `SOURCE_REPO`.
- The false rejection is in the text. `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md` names OpenSpec in its option "Adopt OpenSpec and delete the task files (chosen)" and in two options that say "rejected". The old test saw the name and confirmed `rejected`. The new test sees that the chosen option names OpenSpec too, and drops the proposal. ADR 0008 still rejects Temporal, Hatchet and "DBOS Transact in-process" ("(runner-up): rejected for now").
- The 88 tool strings of the 330 blocks map to 81 canonical ids in the replay test. A PyPI package takes the GitHub project of its `Source`, `Repository` or `Code` URL from the PyPI JSON API (`info.project_urls`), so `pydantic-ai-slim` and `pydantic/pydantic-ai` join.
- Not verified offline: the live share of `in-use` verdicts after the merge (`devops_cli_roadmap_alternatives_total{verdict="in-use"}` above 25 %, 28 of 130 before). A person reads it 7 days after the merge.

## Existing Tool Considered

- The GitHub SBOM REST export gives the packages in use with one request. `packageurl-python` (MIT, the reference parser of the package-url project; release 0.17.6 of 2025-11-24, last push 2026-03-11, not archived) parses its package URLs. `packaging.utils.canonicalize_name` (already locked) gives the canonical PyPI name. deps.dev (public API) gives the packages of a GitHub project. The PyPI JSON API, which the check already reads, gives the source of a package.
- `git grep -i -w -F` is the rule of the census. The job reads the files of the deployed paths and applies the same rule with one regular expression, because a git child process needs a recorded git transcript for each tool name of each test (docs/TESTING.md), and the clone of the Service holds only the files of HEAD.
- Only the code rules and the glue are new code: about 150,000 tokens and 4 hours to build, as the issue says.
- The change deletes the name test of the confirmed ADR (`names` over the title and the options in `_confirmed_adr`) and the read of the ADRs only for a run with an item of no skip class.
