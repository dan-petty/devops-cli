# Proposal: #6334

## Why
The `devops infra plan` parser counts a `meta: end_host` skip by a false `when` condition as unchecked. The skip result holds `skip_reason` and no `false_condition`. An unchecked task raises the agent access level that `devops infra apply` needs. A plan with no changes can then require full access.

## What Changes
- `_check_mode_caused` in `src/devops_cli/infra/plan.py` treats `skip_reason` values indicating a false condition (`Conditional result was False` or `end_host conditional evaluated to False`) that do not name `ansible_check_mode` as checked.
- Tasks skipped by a false condition with these `skip_reason` values are not added to `unchecked`.
- Update `infra-plan` specification with the modified requirement.
- The change fits one pull request.

## Capabilities
- `infra-plan`: MODIFIED requirement "Hidden diffs and unchecked tasks".

## Impact
- A plan whose only skipped task is a `meta: end_host` with a false condition shows 0 unchecked tasks and requires no elevated agent access level.

## Feasibility
- Observed in `dan-petty/homelab#60`: `devops infra plan` produced `unchecked: Skip node that is NotReady or cordoned (ansible.builtin.meta)` because Ansible emitted `{"skip_reason": "end_host conditional evaluated to False, continuing execution for condor.lan"}` and no `false_condition`.

## Existing Tool Considered
- The project owns the Ansible event parsing in `src/devops_cli/infra/plan.py`. No external tool parses these Ansible callback JSON strings for plan generation.
- Build cost: about 15 lines of code and tests; about 20k tokens and 20 minutes.
