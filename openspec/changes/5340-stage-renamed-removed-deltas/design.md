# Design

## Decisions

- **Write the OpenSpec form that the repository already uses.**: A rename is `- FROM: \`### Requirement: <old>\`` and `- TO: \`### Requirement: <new>\`` on two lines. A removal is a `### Requirement: <name>` header with a `**Reason**:` line and an optional `**Migration**:` line. The code spans keep a name that ends with a code span whole, because the FROM and TO pattern of OpenSpec strips one closing backtick.
- **Write REMOVED and RENAMED after ADDED and MODIFIED.**: The order of the OpenSpec template keeps the files of a plan with no rename and no removal the same as before. The archive applies the sections in its own order, so the order in the file changes nothing.
- **Name the fields `from_name` and `to_name`.**: `from` is a keyword of Python, and an alias makes the reply, the dump and the read differ.
- **Keep `migration` as an optional field.**: The hand-written plans of the repository give a `**Migration**:` line for each removal. Without the field, fix-plan would drop that line when it writes such a plan again.
- **Check in the gate only what `openspec validate` does not check.**: The validator refuses a MODIFIED block under the old name, a rename and a removal of one requirement, and a TO that collides with an ADDED requirement. It does not compare a FROM, a TO or a removed name with the base spec, and `openspec archive` fails on them later. So the gate checks the base names, and only when the caller gives the requirement names of the capability.
- **Let the review judge whether a name fits its text.**: No rule can see that a name says the opposite of its text. The review already sends a plan back for an open `spec_delta_wrong` finding, so the review prompt adds this case to that type, and the stage prompt tells the planner the fix (ADR 0020: a rule before a model, a model where no rule can decide).
- **Read the base scenarios and the base text under the old name.**: OpenSpec applies RENAMED before MODIFIED, so a MODIFIED block under the new name replaces the renamed base block. The scenario copy and the moved-spec check of plan-check follow the same map from the new name to the old name.
- **Deliver the reader part of #5256 here.**: Write, then read, must keep each fact of the files (#5205), and the property test of the reader generates every field of `StageSpec`. A writer change with no reader change breaks that contract.

## Rejected alternatives

- **Keep the old name and fix the name in the delivery pull request.**: The evidence is #5182 and #5336: the delivery merged the false name, and the living spec still holds it.
- **Detect a name that no longer fits with a word rule, such as a `not` in the name and none in the text.**: Such a rule refuses good plans and misses most bad ones. Only a reader of the meaning can judge it, and the review already reads the plan.
- **Write REMOVED with the bullet form `- \`### Requirement: <name>\``.**: The bullet form has no place for the reason, and the issue asks for a reason with each removal.
