# Tasks

## 1. Documents

- [x] 1.1 Write `docs/SRE.md`: purpose and scope, principles, the service catalog, the target, the current state with its queries, the method, the rules and the gap table
  - Verification: `$ uv run devops docs check`
- [x] 1.2 Add the spec to `.nav.yml` and `docs/index.md`, and link it from `docs/DESIGN.md`, `docs/CLUSTER.md` and `k8s/README.md`
  - Verification: `$ uv run devops ci --check --only lint,format,docs,openspec,domain`

- [x] 1.3 Move the order of a new Secret into `k8s/README.md`, and add chart rule C15 and the page lines of both windows to `docs/DESIGN.md`
  - Verification: `$ uv run devops ci test tests/docs tests/design`
- [x] 1.4 File the gaps with no open issue as sub-issues of #5445, and comment on the open issues of the other gaps
  - Verification: `$ uv run devops gh api repos/dan-petty/devops-cli/issues/5445/sub_issues --jq '.[].number'`
