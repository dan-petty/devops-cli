# Tasks

## 1. Policy and template

- [x] 1.1 Add the refusal cases of the three containers and the case of the old shape to the gate check
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Rewrite the template as three containers and the policy over one variable of the containers
  - Verification: `$ uv run devops ci --check --only k8s`

## 2. Documents

- [x] 2.1 State the layout in docs/CLUSTER.md, SECURITY.md and docs/roadmap/implement.md
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 2.2 Modify the requirements of `roadmap-implement-runner`
  - Verification: `$ uv run devops openspec check`
