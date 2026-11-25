# Design

## Decisions

- **Ordered TOML rule table (`src/devops_cli/ai/personas/lens.toml`)**: Store all rules (`flag`, `step_role`, `finding`, `path`, `label`) in file order so first match wins deterministically and tests verify every row by id without executing selector logic to discover rows.
- **`pathspec` for path patterns**: Use `pathspec` (`PathSpec.from_lines("gitignore", ...)`, already pinned) so `**` recursive globs (`k8s/**`, `tf/**`, `src/**`) and bare prefixes (`Dockerfile*`) follow project path semantics.
- **`None` default for `--persona` in `devops ai chat`**: Use `persona: str | None = None` so callers distinguish omitted (`architect`, `source="default"`) from explicit `--persona architect` (`architect`, `source="flag"`) and `--persona auto` (`select_lens` over git changes, `source="rule"`).
- **Closed label sets on `devops_cli_ai_lens_total`**: Restrict `caller` to `("chat",)`, `lens` to all `Persona` values plus `"none"`, and `source` to `("flag", "rule", "default")`, yielding 21 current series (`<= 84` even up to 4 callers).

## Rejected alternatives

- **Weighted scoring across signals**: Requires an empirical tuning corpus and tie-breaking logic, whereas ADR 0020 specifies deterministic ordered rules.
- **Model-chosen persona lens**: Keeps model latency out of deterministic routing and violates ADR 0005 / offline testability.
- **Python dict/list constant instead of TOML**: Mixes rule data into code instead of following the project's TOML rule convention.
- **Hardcoded `type/ci` label**: Uses `type/infra` and `scope/ci` declared in `workflow_labels.py` and `.github/labels.yml`.
