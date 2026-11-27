# Design

## Decisions

- **Change the default value, not the code.** `src/devops_cli/github/onboard/baseline.py` reads `github.template_repository` and the latest release of that repository. So a new default moves the source.
- **No value test.** docs/TESTING.md ("Which change gets a test") says that no test asserts a value of the configuration. `uv run devops repos onboard dan-petty/github-workflows --plan --only 9` is the proof: it names the template ref that it renders. `uv run devops ci docs` keeps `docs/CONFIGURATION.md` equal to the settings.
- **Dated lines in the Status History of ADR 0032 and ADR 0035.** The decisions of the two records stay. The onboard command applies one baseline from a template, and a shared template is in a public repository at a release tag. Only the name of the repository changed. docs/adr/README.md gives the line `Fact out of date` for a fact that changed.

## Rejected alternatives

- **A value test of `DEFAULT_GITHUB_TEMPLATE_REPOSITORY`.** It holds a value of the configuration, and docs/TESTING.md forbids that (#6060). The next move of the template would fail it with no change of code.
- **A new record that supersedes ADR 0035.** docs/adr/README.md asks for a new record after the third amendment, or when the body contradicts the code. ADR 0035 has no amendment. Its decision (one baseline, applied by the onboard command) still matches `src/devops_cli/github/onboard/`. The name of the repository is a value, and docs/adr/README.md says that a value is not a record.
- **Take the template source from `_src_path` of `.copier-answers.yml`.** Each repository that infra onboarded would then stay on the template of infra, and infra removes that template. The owner order of dan-petty/infra#217 moves each repository one time with `copier recopy` instead.
