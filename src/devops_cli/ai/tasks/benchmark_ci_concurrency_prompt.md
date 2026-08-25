Analyze the following GitHub Actions workflow snippet that exhibits intermittent deployment race conditions and duplicate concurrent deployments to staging using a step-by-step chain-of-thought remediation process:

### Vulnerable Workflow:
```yaml
name: Deploy Staging
on:
  push:
    branches: [ 'feat/*', 'release/*' ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - run: ./deploy.sh staging
```

### Remediation Steps:
1. **Analyze Race Conditions**: Identify root causes of concurrent execution across push events, overlapping branches, and matrix builds.
2. **Formulate Concurrency Key**: Define deterministic `concurrency.group` keys (e.g. `${{ github.workflow }}-${{ github.ref }}`) with `cancel-in-progress: true` to prevent concurrent colliding runs.
3. **Enforce Least Privilege**: Add top-level `permissions: contents: read` or specific minimum required token scopes.
4. **Output Complete YAML**: Provide the corrected, production-ready GitHub Actions workflow manifest.
