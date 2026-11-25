## ADDED Requirements

### Requirement: Ordered lens rule table

`select_lens(evidence)` SHALL evaluate rules from `src/devops_cli/ai/personas/lens.toml` in file order (unique `id` per row) using explicit flag, step role, finding producer/CWE, `pathspec` path globs, and `type/*`/`scope/*` labels, returning the first match or `lens=None` when nothing matches.

#### Scenario: First matching row wins and unknown evidence returns none

- **WHEN** `select_lens` evaluates explicit flag vs path, `refute` step vs finding, each producer row (`gitleaks`, `trivy`, `kube-linter`, `bandit`+CWE, `semgrep`+CWE, `mypy`, `c901`, `pytest`, `coverage`), path globs (`k8s/**`, `tf/**`, `.github/workflows/**`, `Dockerfile*`, `tests/**`, `docs/**`, `docs/adr/**`, `openspec/**`, `src/**`), `type/docs` behind `src/devops_cli/cli.py`, and empty evidence
- **THEN** the first matching row id and lens return, and empty evidence returns `lens=None`

### Requirement: Chat persona auto selection and bounded telemetry

`devops ai chat` SHALL accept `--persona auto` to choose a lens from working-tree changes (`source="rule"`), default omitted `--persona` to `architect` (`source="default"`), emit `source="flag"`, `ai.lens`, and `ai.lens.rule`, and declare `devops_cli_ai_lens_total{caller,lens,source}` bounded at 84 or fewer series.

#### Scenario: Auto and default resolution record accurate source labels and telemetry bounds

- **WHEN** `devops ai chat` resolves `--persona auto` on a `k8s/` change vs omitted `--persona` vs explicit `--persona architect`, and tests check `AI_LENS_TOTAL` series bounds and `devops docs check`
- **THEN** `--persona auto` selects `devsecops` with `source="rule"`, omitted resolves to `architect` with `source="default"`, explicit resolves with `source="flag"`, `caller × lens × source <= 84`, and `docs/TELEMETRY.md` lists `devops_cli_ai_lens_total`
