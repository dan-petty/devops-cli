Perform a specialized documentation review on '{target}' using the '{persona}' persona.

### Documentation Review Mandates:
- **Technical Accuracy & Consistency**: Verify that CLI subcommands, options, configuration keys, API parameters, and environment variables cited in the documentation accurately match actual code implementations without drift or missing options.
- **Clarity & Structural Completeness**: Evaluate organizational hierarchy, readability, setup instructions, and relative markdown link integrity. Identify missing usage examples, undocumented prerequisites, or confusing explanations.
- **Zero Information Leakage**: Verify that no plaintext credentials, tokens or keys are exposed. Whether private addresses or host names may appear in the documentation is the project's convention to state.
- **Context-Aware Avoidance Pattern Exemption**: Never flag documentation, security tutorials, or architectural specifications that describe known vulnerabilities or anti-patterns in the context of mitigating, explaining, or avoiding them.
- **Remediation**: Output structured findings citing exact line locations (`path/to/file.md:start-end`), specific typo/documentation corrections, and isolated verification criteria.
- **Line Numbers**: Each line of the file starts with its line number and a tab, counted from the top of the whole file on every page. Cite those numbers in `location`, and never copy them into quoted code or a fix. In a diff, a removed line has no number.
