# Design

## Decisions

- **The repository file wins for the fields that it sets, in the required checks rule only.** The issue asks for the required checks. The file is the render of the template, kept current by `copier update`, plus the edits of the repository. Its other rules are the same as the baseline in the common case, and a merge of them is the subject of #7326, which ranks the strictness of each parameter. So the change merges only the required checks rule: the parameters that the file sets replace those of the baseline, and the entry of a check that the file names replaces the entry of the same check from another source.
- **A union of the required checks.** The checks of the file, of the baseline, of the live ruleset and of the template pull request all stay. A union never removes a check, so the change does not lower a live ruleset (#7326). It does not change which checks of the template pull request become required, which #7318 owns; a check that the file names is the choice of the repository.
- **The live read stays.** D3 adds each check that reported on the template pull request. Those checks exist only in the live ruleset after the merge of the pull request. Without the live read, `test_a_second_confirmed_run_on_a_new_repository_writes_nothing` and `test_an_onboarded_repository_plans_no_change` fail, because the next run removes those checks.
- **The file of the default branch.** Row 8 reads `.github/labels.yml` of the default branch in the same way. A branch with no file gives the old result.
- **The schema of the template checks the file.** A person can change the file, so row 10 checks it against `templates/github-repository.schema.json` at the ref of the baseline. `config/yaml_errors.py::load_yaml` reads it, so a file that does not load gives an error with no text of the file. The error goes to row 10 only, which is `not readable`; the other rows still run.

## Rejected alternatives

- **The repository file replaces the whole ruleset of the baseline.** It also changes the other rules, which #7326 owns, and it can lower a rule of the baseline with no warning.
- **The repository file replaces the list of checks.** It removes the checks of the live ruleset and of the template pull request, so a second run removes the checks of D3.
- **A Copier answer for the required checks in the template of dan-petty/infra.** It needs a change of the template and of each repository, and the repository file already holds the checks.
- **Read the file in the baseline step.** A file that the schema refuses would then make each row of the baseline `not readable`, not only row 10.
