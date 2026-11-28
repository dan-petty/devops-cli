# Proposal

## Why

Row 10 of `devops repos onboard` writes the baseline `main` ruleset over the live ruleset and keeps only the live required check names, so each other live rule and each stricter live threshold is lost with no warning. On 2026-11-26 it removed the `code_coverage` rule of dan-petty/devops-cli and lowered its CodeQL, code quality and review-thread settings (#7326). Rule 5 of the repository rules lets only the owner lower a security or quality threshold, so the row must keep each live rule and each stricter live value, name each one, and leave the choice to the owner.

## What Changes

- Add `src/devops_cli/github/onboard/ruleset_merge.py` with `merge_live_ruleset`, which keeps each live rule, each live check entry and each live parameter that is stricter than the baseline or that its table does not rank, writes the baseline value where the live value is weaker, adds each baseline rule and parameter, and gives one warning line for each kept setting.
- Merge the live ruleset into the baseline body in `ruleset_row` at `src/devops_cli/github/onboard/settings_rows.py:680:def ruleset_row(`, then add the checks of the repository file and of the reported checks with `_with_required_checks`, which still lets the repository file win each parameter of the required checks rule that it sets.
- Add the `warnings` field to the row record of `src/devops_cli/github/onboard/model.py` after `src/devops_cli/github/onboard/model.py:85:changes: tuple[str, ...] = ()` and render each warning in `_row_lines` at `src/devops_cli/github/onboard/run.py:265:def _row_lines(row: Row) -> list[str]:`.
- Add the tests in `tests/github/onboard/test_onboard_ruleset_merge.py` and `tests/github/onboard/test_onboard_rows.py` that fail on the base.
- Add the spec delta of `repos-onboard`: row 10 keeps each live rule, each live check entry, and each live parameter that is stricter or unranked, writes the baseline value where the live value is weaker, lets the repository file win each parameter it sets, names each kept setting, and adds each baseline rule and check.
- State the new row 10 behavior in `docs/repos/onboard.md:56:| 10 | Ruleset |`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-onboard`: Row 10 keeps each live rule and stricter threshold, Row 10 keeps each live required check, Row 10 ranks each live parameter of the required checks rule, Row 10 names each live setting that it keeps, Row 10 adds each baseline rule and check that the live ruleset lacks

## Impact

- Code: `src/devops_cli/github/onboard/ruleset_merge.py`, `src/devops_cli/github/onboard/settings_rows.py`, `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/run.py`
- Documents: `docs/repos/onboard.md`
- Tests: `tests/github/onboard/test_onboard_ruleset_merge.py`, `tests/github/onboard/test_onboard_rows.py`

## Feasibility

- `read_file` of `src/devops_cli/github/onboard/settings_rows.py:700:desired = _with_required_checks(ruleset, own_ruleset, live, ctx.reported_checks)` and `src/devops_cli/github/onboard/settings_rows.py:714:writer.rest("ruleset-update", f"/repos/{ctx.repo}/rulesets/{match['id']}", desired)` showed that row 10 builds its write body from the baseline ruleset and sends it over the live ruleset; that is the defect of #7326.
- Probes line, word for word: "`code_coverage` has no definition at the staging commit." A live `code_coverage` rule therefore has no rule in the baseline body, so the write of row 10 removes it.
- `read_file` of `src/devops_cli/github/onboard/settings_rows.py:654:result = copy.deepcopy(desired)` and `src/devops_cli/github/onboard/settings_rows.py:657:if not rules and own_rules:` showed that `_with_required_checks` starts from the body it is given and adds a required checks rule only from the repository file; the merge runs first, so `_with_required_checks` only adds checks and the parameters of the file.
- `read_file` of `src/devops_cli/github/onboard/settings_rows.py:670:parameters.update(own_parameters)` and `src/devops_cli/github/onboard/settings_rows.py:672:for entry in [*_check_entries(own), *baseline_checks, *_check_entries(live)]:` showed that the required checks rule of the repository file wins each parameter that it sets while each live check entry stays; the added requirement states that win, and the base requirement `The ruleset requires the reported and the declared checks` stays true and unmodified because the new text keeps it.
- The added requirements `Row 10 keeps each live required check` and `Row 10 ranks each live parameter of the required checks rule` compare a live parameter of the required checks rule by the same rank table as the added requirement `Row 10 keeps each live rule and stricter threshold`, so both give the baseline value where the live value is weaker; the table ranks `strict_required_status_checks_policy` true above false, and `tests/support/github_repository.py:103:strict_required_status_checks_policy": False,` holds the baseline value that the new scenario asserts.
- Group 2 names the rendered settings file of the target repository by the constant and the helper: `tests/github/onboard/test_onboard_rows.py:47:_SETTINGS_FILE = ` names the file, and `tests/github/onboard/test_onboard_rows.py:790:def _declare_checks(harness: OnboardHarness, checks: list[str], **parameters: Any) -> None:` writes it into the commit of `main`.
- `read_file` of `src/devops_cli/github/onboard/baseline.py:216:text = session.client.get_file_at(repo, SETTINGS_FILE, branch)` showed that the settings file is read through the client of the session, and `src/devops_cli/github/onboard/baseline.py:39:SETTINGS_FILE: Final[str] = "github/repository.yaml"` holds the one copy of its name.
- Probes line, word for word: "The path `openspec/specs/repos-onboard/spec.md` is a file of the staging commit." The spec delta of this change adds requirements to that capability, and `read_spec` for `repos-onboard` listed no requirement named `Row 10 keeps each live rule and stricter threshold`, `Row 10 keeps each live required check`, `Row 10 ranks each live parameter of the required checks rule`, `Row 10 names each live setting that it keeps` or `Row 10 adds each baseline rule and check that the live ruleset lacks`, so each is new and the base requirements stay unmodified.
- Probes line, word for word: "ac695ca5111ac4772c60e7ff8742cc335c985843:docs/adr/0035-the-onboard-command-owns-the-repository-settings.md:67:- **Decision 7.** The command manages the `main` ruleset of each repository, with the `code_quality` rule, and does not wait for the provider."
- `read_file` of `docs/adr/0035-the-onboard-command-owns-the-repository-settings.md:43:- Each row reads the live value, compares it with the baseline and writes only a difference. On an onboarded repository, `--confirm` sends no write.` showed the contract of the row that the change keeps.
- `AGENTS.md:11:5. **Pass the checks.** Never use `--no-verify`. Never lower a security or quality threshold; only the owner can allow it` is the rule that row 10 breaks today, and the change keeps it.
- The constant that names the rule is `src/devops_cli/github/onboard/settings_rows.py:66:_REQUIRED_CHECKS_RULE: Final[str] = "required_status_checks"`, from `search_code`; `ruleset_row` passes it to the merge, so the new module holds no second copy of the name.
- `read_file` of `src/devops_cli/github/onboard/model.py:85:changes: tuple[str, ...] = ()` showed the frozen row record, which holds no warning field today, and `src/devops_cli/github/onboard/run.py:265:def _row_lines(row: Row) -> list[str]:` showed where one row becomes output lines.
- `read_file` of `tests/support/github_repository.py:89:RULESET: dict[str, Any] = {` showed the baseline ruleset of the fake GitHub, whose `required_status_checks` rule the new tests extend, and `tests/support/github_repository.py:377:self.rulesets = [{"id": 7, **ruleset}]` showed the live rulesets that the new row tests change.
- `read_file` of `tests/github/onboard/test_onboard_rows.py:84:def _onboarded(harness: OnboardHarness, config: Any) -> None:` showed the onboarded state that the new row tests start from, and `tests/github/onboard/test_onboard_rows.py:159:def test_an_onboarded_repository_plans_no_change(` holds the no-change test that the change extends.
- `read_file` of `docs/repos/onboard.md:56:| 10 | Ruleset | The ruleset `main` of the baseline, with each required check of the live ruleset,` showed the row 10 text that the documentation group replaces.
- `search_code` for `merge_live_ruleset` and for `_VALUE_ORDER` answered `No match.`, and `search_code` for `_kept_setting_line` and for `_stricter` answered `No match.`, so the names of the `adds` list are new.
- `merge_live_ruleset(desired, live, check_rule)` takes two ruleset bodies and the name of the check rule; it needs no checkout, no client and no network.
- `ruleset_row(session, writer, ctx, baseline)` needs a client of the GitHub API; the onboard fake answers it, so the tests reach no network.
- `onboard_repository(chosen, session=..., settings=...)` needs a client and a checkout of the workdir; the `onboard_github` harness answers the client and writes the workdir, so no network and no real checkout.
- `read_repository_settings(session, repo, branch, baseline)` needs a client of the GitHub API; the fake answers `GET /repos/<repo>/contents/...`, so the test reaches no network.
- `render_report(report)` needs no client, no checkout and no network.
- The verify `uv run devops ci test tests/github/onboard/test_onboard_ruleset_merge.py` needs the failure class `test` (action `repair`); the programs `uv`, `devops`, `python` and `pytest` come from the runner image, and the pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`.
- The verify `uv run devops ci test tests/github/onboard/test_onboard_rows.py` needs the failure class `test` (action `repair`); `uv`, `devops`, `python` and `pytest` come from the runner image, and the pod settings above apply.
- The verify `uv run devops ci docs` needs the failure class `lint` (action `repair`) and runs the docs check of the CI gate; `uv` and `devops` come from the runner image, and `vale` is `NOT_IN_RUNNER`, so this row does not run it.
- The first checks against the real system are `uv run devops ci test tests/github/onboard/test_onboard_ruleset_merge.py`, then `uv run devops ci test tests/github/onboard/test_onboard_rows.py`, then `uv run devops ci docs`, then `uv run devops openspec check`, then `uv run devops ci --check --only lint,typecheck,openspec`.
- `read_issue` for #6784 showed the item open, with the comment `Do not run row 10 on devops-cli again before #7326 is fixed.`, and `read_issue` for #6876 showed it open; the live run stays with the owner, and this change needs no live write because the onboard tests answer GitHub with a fake.
- `find_issues` for `onboard ruleset` listed #7326, #7445, #7476, #6876 and #6784 as open; this change takes the ruleset merge of row 10 alone, and the context lists no overlap and no metric sender.

## Existing Tool Considered

No open, maintained tool covers the need. The alternatives check of 2026-11-26 in the issue body gives the verdict `none`: safe-settings, repository-settings and terraform-provider-github each enforce a baseline as-is, so each removes live rules and lowers thresholds instead of naming the stricter live settings. The change builds the comparison in row 10: about 50k tokens to write it with its tests, about 10k tokens per later fix, about 5k tokens a year to keep it, and about 4 hours elapsed.

## Dependencies

None.
