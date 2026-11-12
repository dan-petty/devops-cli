# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests with recorded runner events and a fake kubectl: the refusal for each level and caller kind; the refusal for a changed record, an old plan, another limit, a commit that origin does not hold, another branch and a closed pull request for an agent, and host key checks off for an agent; one disruptive host at a time in plan order; a node that was cordoned before stays cordoned; a blocked drain check; a fresh check that differs; an unplanned changed task; a health failure after a host; a gap of the API server; the audit record; the question; the dry run with no process
  - Verification: `$ uv run devops ci test tests/infra/test_apply.py tests/infra/test_nodes.py tests/commands/test_infra_apply.py`
- [x] 1.2 Add `infra/apply.py`, `infra/nodes.py`, `apply_level`, `origin_holds`, `export_tree`, `Playbook.run`, the apply models, the counter, the dry-run plan and the command `devops infra apply`
  - Verification: `$ uv run devops ci test tests/infra tests/commands/test_infra_apply.py tests/commands/test_infra_plan.py tests/commands/test_infra_status.py tests/commands/test_infra_onboard.py tests/telemetry/test_telemetry_instruments.py tests/dry_run tests/lang`
- [x] 1.3 Run the apply live on dan-petty/homelab as an agent at the level `full`: homelab #19 (`ansible/playbooks/03_k3s.yaml`) on each host alone, then homelab #20 (`ansible/playbooks/13_crash_capture.yaml`) on hawk, and record the audit records and the nodes before and after in a comment of the pull request
  - Verification: `$ uv run devops infra status dan-petty/homelab --ping`

## 2. Documents

- [x] 2.1 Write the section `## Infra Repos` of SECURITY.md and `ansible-runner` in its item 3, change "hosts" to "hardware" in the "Only a person" paragraph of AGENTS.md, add the glossary terms to CONTEXT.md, and regenerate the command reference
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
- Pending a person: decide whether other text of AGENTS.md gets shorter, so that the "Only a person" paragraph can hold the full text of design section 11 within the cap of 6,500 characters.
