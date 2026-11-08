# Design

## Decisions

- **Refuse the plan in `path_problems` of `src/devops_cli/roadmap/stage/stage_paths.py`.**: `path_problems` already refuses a plan that leaves out a caller file, and `check_gates` calls it. A hard refusal makes the plan name the test before staging finishes.
- **Record the tests that each changed manifest reaches in the job, and read that record in the gate.**: The replay runs the gates and reads no git. A record lets the job use its checkout and lets the replay judge the same rule from its case, as `search_evidence` does.
- **Pass the record in `src/devops_cli/roadmap/plan_recheck.py` too, from a search at the ref of the pass.**: The recheck calls `check_gates` and judges the plans that the implement job takes. A skipped record would let the same deadlock return on a merged plan.
- **Match the manifest file name and the name of its folder, not the whole path.**: The logging test builds the path from `REPO_ROOT`, `k8s`, `logging` and `networkpolicy.yaml`, so it holds no full-path string. Both names must match, so a test that holds only the folder name is no reference.
- **Apply the rule to every changed YAML manifest under `k8s/`.**: Tests assert on other manifests too, so a rule for `networkpolicy.yaml` alone would leave the same deadlock for the next manifest.
- **Read the references of each changed manifest once per reply, with the search of the job.**: The record costs one search for each changed manifest of a reply, and the first reply and a split reply read the same record.
- **Defer the early-stop guard of the implement runner to a separate issue.**: The stage gate removes the reported deadlock. The guard is a second runtime path with its own tests, and it changes no plan.
- **Add the record to `CaseFacts` with an empty default.**: The recorded cases keep their shape, and the replay of a case with no record judges no reference.

## Rejected alternatives

- **Refuse a changed manifest whose referencing tests the plan omits inside `stage_probe`.**: `src/devops_cli/roadmap/stage/stage_probe.py` reads the staging commit for the premise and holds no rule on the plan paths.
- **Search the checkout inside `path_problems` and leave the replay out.**: `src/devops_cli/roadmap/stage/stage_eval_gates.py:class PlanUnderTest` builds its tree from the case and runs no git, so the rule would never be replayed.
- **Search the raw text of each test file for the full manifest path.**: `tests/commands/k8s/test_k8s_logging_stack.py` builds the path from `REPO_ROOT`, `k8s`, `logging` and `networkpolicy.yaml`, so it holds no full-path string.
- **Match a test on the folder name alone.**: Many test files hold `logging`, so a plan would list unrelated tests and the plan would grow past its group budget.
- **Pass no record in `src/devops_cli/roadmap/plan_recheck.py`.**: `src/devops_cli/roadmap/plan_recheck.py:def _record` calls `check_gates`, and a merged plan is the one that the implement job runs, so a skipped record would let the deadlock return.
- **Add a `ProposalGate.PERIMETER` member and its line in `check_gates`.**: The problem is a path rule of the plan, as the missing-path and caller problems are, and both report under the `paths` gate.
- **Include the implement runner early-stop guard in this change.**: The reported deadlock ends when the plan names the test, and the guard adds a second runtime path with its own tests.

## Security

A perimeter network policy is the trust boundary of a namespace, and the new rule touches no cluster: it reads the manifest paths and the test paths of a plan, and the text of the tests of a checkout. The job runs one read-only search for each changed manifest, and the record it builds reaches the gates and the case facts only. A person must confirm that the rule refuses no plan that lists its tests, and that a case records real test paths. The test `test_a_manifest_plan_that_omits_its_test_is_refused` fails if the rule stops refusing the omitted test, and `test_the_record_names_the_test_that_builds_the_path_from_its_parts` fails if the record names a test that holds only the folder name.
