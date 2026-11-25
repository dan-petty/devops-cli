## Problem
Lines cited at 05e9388 (`release/v0.2.29`).

- **The state file is parsed directly.** `load_state` (`tf/analysis.py:280-313`) reads the state file as JSON and projects it (`_project_state_resource`, `:258-277`). The state file is not a public interface of OpenTofu or Terraform; `tofu show -json` is.
- **Encrypted state reads as empty.** OpenTofu's client-side state encryption writes a state without a `resources` key. `load_state` then returns an empty state, and `detect_drift` (`:362-391`) reports every declared resource as missing from state.
- **Module resources are reported as orphaned.** `parse_hcl_directory` reads only the root module's files (`_hcl_files`, `:172-178`). State addresses resources inside modules as `module.<name>.<type>.<name>` (`:270`), so none of them match a declaration.
- **The provider is guessed** from the resource type's prefix (`:148`), so aliased providers (`provider = aws.west`) are misreported.
- **"Drift" here is structural only.** It compares declared addresses with recorded ones. Drift against live infrastructure needs a refresh.

## Proposed remedy
- **When the directory is initialised:**
  - state comes from `tofu show -json` (resource addresses, modules and providers);
  - drift comes from `tofu plan -refresh-only -json`.
  - Terraform is used only when OpenTofu is absent, as `_resolve_tf_binary` (`commands/tf.py:51-61`) already orders them.
- **When it is not initialised,** the commands report the state as unavailable and name `tofu init`, instead of guessing.
- **Delete** `load_state`, `_project_state_resource`, `resolve_state_file` and the prefix-based provider guess.
- **Keep** the python-hcl2 parse of the configuration for the dependency graph and blast radius.

## Key questions
- **Key question for the owner:** #310 chose to read HCL and the state file in process, so that read-only IaC queries pay no binary start-up and need no initialised directory. This item reverses that choice for state and drift. Do we accept the reversal?
  - *Proposed answer:* yes.
  - A wrong answer costs more than a `tofu show` start-up. Encrypted state and module resources are both misreported today.
  - An uninitialised directory gets an explicit "unavailable" instead of a misleading report.
  - The configuration graph and blast radius keep the in-process HCL parse, so #310's choice stands where it gives correct answers.

## Acceptance criteria
- [ ] Recorded `tofu show -json` output for a configuration with a module reports the module's resources as in sync, not orphaned.
- [ ] Recorded output for an encrypted-state backend reports the resources, not an empty state.
- [ ] Recorded `tofu plan -refresh-only -json` output with a changed attribute reports drift on that resource.
- [ ] An uninitialised directory reports the state as unavailable and names `tofu init`.
- [ ] Tests use the process fake replaying the recorded output.
- [ ] Tests run offline with fakes only at process and HTTP edges; each new test runs under 1 s.
- [ ] `uv run devops ci` passes.

Related: #310, #775 (process runner), #1031.

Found by the 2026-10-08 client-library audit.

Opened as a borrow (#1153, `budget/borrowed`): the agent filing quota is spent for this cycle, and this is a defect or security finding of the owner-requested 2026-10-08 client-library audit.

## Update 2026-10-08: owner decision

The key question is answered as proposed: reverse #310's no-binary design **for state and drift only**.
- When the directory is initialised, state comes from `tofu show -json` and drift from `tofu plan -refresh-only -json`.
- An uninitialised directory reports "state unavailable (run tofu init)" instead of a guess.
- The in-process HCL parse stays for the dependency graph and blast radius.
