### What happened

#1307 splits the test migration into one child per package, and each child names the test files it owns. Files added after the census of 2026-10-07 have no owner. The test-suite audit of 2026-10-24 at df8e2ee5 found 49 test files that no child of #1307 names and that patch a `devops_cli` name or import a private one: 146 internal patch sites in 33 files and 50 private-name imports in 28 files.

| File | Internal patch sites | Private-name imports |
| :--- | ---: | ---: |
| `tests/test_k8s_ipv6_and_proxy_boundaries.py` | 15 | 9 |
| `tests/test_k8s_volume_reclaim.py` | 12 | 0 |
| `tests/test_k8s_gpu_placement.py` | 11 | 0 |
| `tests/ai/review/test_runner.py` | 6 | 4 |
| `tests/test_telemetry_llm_content.py` | 9 | 0 |
| `tests/test_ai_research_socratic.py` | 6 | 2 |
| `tests/test_rag_kb_sync.py` | 8 | 0 |
| `tests/test_review_group_analysis.py` | 7 | 1 |
| `tests/test_review_pipeline_go.py` | 3 | 5 |
| `tests/test_pr_hardening_report.py` | 7 | 0 |
| `tests/test_review_canary.py` | 6 | 0 |
| `tests/test_security_zizmor.py` | 6 | 0 |
| `tests/ai/review/test_pipeline.py` | 3 | 2 |
| `tests/commands/test_review_removed_options.py` | 5 | 0 |
| `tests/test_k8s_tempo.py` | 4 | 1 |
| `tests/llm_stream_fakes.py` | 4 | 0 |
| `tests/test_ai_research_mental_model.py` | 4 | 0 |
| `tests/test_fail_to_pass.py` | 4 | 0 |
| `tests/test_osv_scanner.py` | 2 | 2 |
| `tests/ci/test_cache_fuzzing.py` | 2 | 1 |
| `tests/core/test_cleanup_fuzzing.py` | 2 | 1 |
| `tests/test_ci_repeat.py` | 3 | 0 |
| `tests/test_config_field_validation.py` | 1 | 2 |
| `tests/test_golangci_lint_scanner.py` | 3 | 0 |
| `tests/test_review_rules_pack.py` | 2 | 1 |
| `tests/commands/test_pr.py` | 0 | 2 |
| `tests/test_ai_research_analogies.py` | 2 | 0 |
| `tests/test_architectural_invariants.py` | 0 | 2 |
| `tests/test_review_syntax_masking.py` | 0 | 2 |
| `tests/test_roadmap_return.py` | 2 | 0 |
| `tests/test_url_credential_masking.py` | 2 | 0 |
| `tests/ai/review/test_cited_code.py` | 1 | 0 |
| `tests/argo/test_gitops_fuzzing.py` | 0 | 1 |
| `tests/core/test_clock_contract.py` | 1 | 0 |
| `tests/test_ai_research_forage.py` | 0 | 1 |
| `tests/test_all_commands_help_dryrun.py` | 0 | 1 |
| `tests/test_ci_mutate.py` | 1 | 0 |
| `tests/test_cli_format_adoption.py` | 0 | 1 |
| `tests/test_cli_startup_imports.py` | 0 | 1 |
| `tests/test_codebase_hygiene_and_shims.py` | 0 | 1 |
| `tests/test_core_repo.py` | 1 | 0 |
| `tests/test_k8s_agents_manifests.py` | 0 | 1 |
| `tests/test_k8s_monitoring_alerting.py` | 0 | 1 |
| `tests/test_kb_manuals_metadata.py` | 0 | 1 |
| `tests/test_review_ruff_mypy_evidence.py` | 0 | 1 |
| `tests/test_review_tool_runs.py` | 0 | 1 |
| `tests/test_review_tool_sandbox.py` | 0 | 1 |
| `tests/test_stack_dashboards.py` | 0 | 1 |
| `tests/test_survey_cmd.py` | 1 | 0 |

Most of these files are new since 2026-10-07: for example `tests/test_k8s_gpu_placement.py` (2026-10-21), `tests/test_telemetry_llm_content.py` and `tests/test_review_pipeline_go.py` (2026-10-24). So the coupling that #1307 retires keeps growing in files that no item will migrate.

### What should happen

Each file in the table tests through the public interface over the shared fakes, as docs/TESTING.md and ADR 0007 require. It patches no `devops_cli` name and imports no private name.

### Evidence

- `.data/agent/scratch/audit/full_list.txt` of the 2026-10-24 audit, sections 3.internal-patch, 3.private-import (rows marked `no-child-issue`), 3.new-coupling and 5 ("test files that no child issue of #1307 names").
- Every file in the table exists at b170358e.

### Acceptance criteria

- [ ] No test in the files above patches a `devops_cli` module, class, function or attribute, or imports a name that starts with `_` from `devops_cli`.
- [ ] Each double is a shared fake from `tests/support/fakes/`, installed through its seam or fixture.
- [ ] Product code that a test needed only for a patch goes, as #1307's Q27 says.
- [ ] If #1309 has landed, its ceilings go down by the sites that this item removes.
- [ ] Each test still checks the behaviour that it checked before. The pull request names each test it deletes and why.
- [ ] `uv run devops ci` passes.

This item is a child of #1307 for the files that no other child names. A file that #1313 moves keeps its owner here. Follows ADR 0007 as #2143 amends it.


Source: https://github.com/dan-petty/devops-cli/issues/1307

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
49 test files added after the 2026-10-07 census patch devops_cli internal names or import private names. No child of #1307 owns them. They must test through public interfaces over shared fakes, as ADR 0007 and docs/TESTING.md require.

### Acceptance criteria
- Criterion 1: No test in the 49 files patches a devops_cli module, class, function, or attribute, or imports a name that starts with an underscore from devops_cli.
  Verification: Run a grep or static analysis over the 49 files for patch( calls targeting devops_cli names and for imports of names starting with _. The result is zero matches.
- Criterion 2: Each test double is a shared fake from tests/support/fakes/, installed through its seam or fixture.
  Verification: Inspect the 49 files. Every mock or fake object comes from tests/support/fakes/ or a conftest fixture that installs one. No inline MagicMock replaces a devops_cli dependency.
- Criterion 3: Product code that a test needed only for a patch is removed or made public, as #1307 Q27 specifies.
  Verification: For each removed patch site, confirm the product code it targeted is either deleted or exposed through a public seam. The pull request description names each such site.
- Criterion 4: If #1309 has landed, its ceilings are reduced by the number of sites this item removes.
  Verification: Check the #1309 ceiling values in the repository. They are lower by the count of sites removed in this pull request.
- Criterion 5: Each test still checks the behaviour it checked before. The pull request names each test it deletes and why.
  Verification: Diff the test function names before and after. Every deleted test is named in the pull request description with a reason.
- Criterion 6: uv run devops ci passes.
  Verification: Run uv run devops ci in the pull request branch. All checks complete with a passing status.

### Key questions
- **What is the public interface that these 49 test files must use instead of internal patches and private imports?**: The public interface is the CLI (typer app) and public module-level functions. Tests install shared fakes from tests/support/fakes/ through seams or fixtures. They do not patch devops_cli names or import names that start with an underscore. [sources: tests/test_k8s_volume_reclaim.py, tests/test_k8s_gpu_placement.py]
- **What shared fakes exist in tests/support/fakes/ that cover the domains in the 49 files?**: The repository has tests/k8s_fakes.py (FakeCoreV1, client, pod) and tests/support/fakes/ for LLM clients and other services. The 49 files span k8s, AI review, telemetry, RAG, and CLI domains. Each domain needs its shared fake installed through a seam. [sources: tests/test_k8s_volume_reclaim.py, tests/ai/review/test_runner.py, tests/test_telemetry_llm_content.py]
- **What does #1307 Q27 specify for product code that a test needed only for a patch?**: The acceptance criteria state that such product code goes, as #1307 Q27 says. The exact wording of Q27 is not in the context provided. The implementer must read #1307 to confirm the rule. [sources: tests/test_k8s_ipv6_and_proxy_boundaries.py]
- **Does #2143 change ADR 0007 in a way that affects the requirements of this item?**: The body states this item follows ADR 0007 as #2143 amends it. The content of #2143 is not in the context. The implementer must confirm the amended requirements before starting. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
#2143
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "High", "Priority": "P2-Medium", "Status": "Planned", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "f16ef71961157e12a236561860427d70fa97565199a7c99de223f62cd6c4b3f0", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "1c6e448b81fc413e8b4e3af5aec98c0d2af090ea1a5b98d8c32f174d8bc50ea6", "stage.branch": "test/2167-the-49-test-files-that-no", "stage.file_cap": null, "stage.groups": "[[\"AI review runner: remove private imports and patch sites\", 9751], [\"AI review pipeline: remove private imports and patch sites\", 9750], [\"AI review cited code and removed options\", 9754], [\"AI review pipeline go, group analysis, canary\", 9723], [\"AI review rules pack, syntax masking, ruff/mypy evidence\", 9733], [\"AI review tool runs and tool sandbox\", 9693], [\"K8s IPv6/proxy boundaries and volume reclaim\", 9758], [\"K8s GPU placement and tempo\", 9736], [\"K8s agents manifests and monitoring alerting\", 9722], [\"Telemetry LLM content and RAG KB sync\", 9727], [\"Security zizmor, OSV scanner, golangci-lint scanner\", 9776], [\"CI repeat, CI mutate, cache fuzzing\", 9784], [\"Core cleanup fuzzing, clock contract, core repo\", 9761], [\"Commands test_pr: remove set_delivered_status patch\", 9711], [\"AI research: socratic, mental model, analogies, forage\", 9823], [\"LLM stream fakes: remove private method patches\", 9729], [\"Argo gitops fuzzing: remove private import\", 9691], [\"Fail to pass, config field validation, PR hardening report\", 9755], [\"Architectural invariants, roadmap return, URL credential masking\", 9755], [\"All commands help dryrun, CLI format adoption, CLI startup imports\", 9726], [\"Codebase hygiene, KB manuals metadata, stack dashboards, survey cmd\", 9798]]", "stage.needs_split": null, "stage.pr": "2982", "stage.ready": "2982", "stage.sha": "4d71a3875563f43f6812856c109172993a20d30b"} -->
