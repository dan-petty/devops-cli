Perform a specialized documentation review on '{target}' using the '{persona}' persona.

### Documentation Review Mandates:
- **Technical Accuracy & Consistency**: Verify that CLI subcommands, options, configuration keys, API parameters, and environment variables cited in the documentation accurately match actual code implementations without drift or missing options.
- **Clarity & Structural Completeness**: Evaluate organizational hierarchy, readability, setup instructions, and relative markdown link integrity. Identify missing usage examples, undocumented prerequisites, or confusing explanations.
- **Zero Information Leakage & Environment Sanitization**: Strictly verify that NO plaintext credentials, tokens, private RFC 1918 IP addresses (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), private hostnames (`*.lan`, `*.local`), or physical host topology are exposed. Enforce RFC 5737 documentation IP blocks (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and standardized placeholder abstractions (`<host>`, `<node>`, `localhost`).
- **Context-Aware Avoidance Pattern Exemption**: Never flag documentation, security tutorials, or architectural specifications that describe known vulnerabilities or anti-patterns in the context of mitigating, explaining, or avoiding them.
- **Remediation**: Output structured findings citing exact line locations (`path/to/file.md:start-end`), specific typo/documentation corrections, and isolated verification criteria.
