# Tasks

## 1. Fetch with the GitHub session credential (behavior)

- [x] 1.1 Write the failing tests: a fetch from a private repository on github.com names gh as the only github.com credential helper and reaches a remote, and only the fetch gets git options
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argocd_overrides.py`
- [x] 1.2 Give the fetch of `render_at_revision` the `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argocd_overrides.py`

## 2. Documents

- [x] 2.1 Say in `k8s/README.md` that the fetch uses the credential of the GitHub session and that the dry run fetches nothing
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
