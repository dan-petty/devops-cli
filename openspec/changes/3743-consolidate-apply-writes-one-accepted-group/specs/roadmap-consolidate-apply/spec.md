## Purpose
Apply exactly one accepted group of the latest consolidate plan, as the person's login, and write only the anchor and the members of that group.

## ADDED Requirements

### Requirement: apply-option
`devops roadmap consolidate` SHALL accept `--apply <group-id>` with `--confirm`, and SHALL refuse a run with no `--confirm`.

#### Scenario: Apply without confirmation
- **WHEN** A person runs `devops roadmap consolidate --apply g1` with no `--confirm`.
- **THEN** The command exits non-zero, names `--confirm` in its message, and the memory store records no write.

#### Scenario: Apply with confirmation
- **WHEN** A person runs `--apply g1 --confirm` and the latest plan holds group `g1`.
- **THEN** The command applies group `g1` and the memory store records the writes of that group only.

### Requirement: unknown-group
The apply MUST refuse a group id that the latest plan does not hold.

#### Scenario: Unknown group id
- **WHEN** A person runs `--apply g9 --confirm` and the latest plan holds no group `g9`.
- **THEN** The command exits non-zero, names `g9`, and the memory store records no write.

### Requirement: merge-section
The apply of a merge group SHALL write the anchor body through `write_issue_body` with one section from `<!-- devops-roadmap-consolidate:start -->` to `<!-- devops-roadmap-consolidate:end -->`, headed `## Consolidated from #<a>, #<b>`, and SHALL keep every byte outside the section unchanged.

#### Scenario: Marked section and unchanged text
- **WHEN** A person applies a merge group whose anchor is #10 and members are #11 and #12.
- **THEN** The anchor body holds one section from `<!-- devops-roadmap-consolidate:start -->` to `<!-- devops-roadmap-consolidate:end -->`, headed `## Consolidated from #11, #12`, and every byte outside the section equals the bytes before the apply.

### Requirement: merge-content
The marked section SHALL hold each member's `## Acceptance criteria` section and `## Key questions` section byte for byte, and SHALL hold the root cause of the group as plain text.

#### Scenario: Copied member content
- **WHEN** A person applies a merge group and member #11 holds an `## Acceptance criteria` section and a `## Key questions` section.
- **THEN** The section holds both member sections with the same bytes, and holds the root cause of the group as plain text.

### Requirement: merge-member-close
The apply of a merge group SHALL close each member as not planned with `close` and one comment `Merged into #<anchor>: <one line>`.

#### Scenario: Member close
- **WHEN** A person applies a merge group with anchor #10 and member #11.
- **THEN** The memory store records one `close` of #11 as not planned and one comment on #11 that starts with `Merged into #10:`.

### Requirement: merge-reapply
A second apply of the same merge group SHALL replace the marked section and MUST NOT add a second section.

#### Scenario: Second apply
- **WHEN** A person applies the same merge group twice.
- **THEN** The anchor body holds exactly one marked section, and every byte outside it is unchanged.

### Requirement: parent-link-kind
The apply of a parent group SHALL add a sub-issue link with `add_sub_issue` for each child, and SHALL add a blocked-by link from the child to the anchor when the anchor holds a milestone and the child is in the backlog.

#### Scenario: Sub-issue links
- **WHEN** A person applies a parent group with anchor #10, children #11 and #12, and none of the three holds a milestone.
- **THEN** The memory store records `add_sub_issue(10, 11)` and `add_sub_issue(10, 12)`, and records no blocked-by write.

#### Scenario: Blocked-by links
- **WHEN** A person applies a parent group with anchor #10 in milestone M1 and children #11 and #12 in the backlog.
- **THEN** The memory store records one blocked-by write for #11 and one for #12, each names #10, and records no sub-issue link.

### Requirement: blocked-by-store
The store protocol, the GitHub store and the memory store SHALL provide the blocked-by write `add_blocked_by`, and the GitHub store SHALL send `POST /repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by`.

#### Scenario: Contract test of the blocked-by write
- **WHEN** The store contract test calls `add_blocked_by` on the memory store and on the GitHub store.
- **THEN** Each store records the call, and the GitHub store sends `POST /repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by`.

### Requirement: parent-anchor-comment
The apply of a parent group SHALL post one fixed-template comment on the anchor that lists the children in the plan's order.

#### Scenario: Anchor comment
- **WHEN** A person applies a parent group with children #11 then #12.
- **THEN** The memory store records one comment on the anchor, and #11 comes before #12 in that comment.

### Requirement: duplicate-close
The apply of a `close-as-duplicate` group SHALL close each member with `close` and `CloseReason.DUPLICATE` once the anchor is closed as completed, with one comment that names the anchor, and MUST NOT call a GraphQL duplicate mutation.

#### Scenario: Duplicate close
- **WHEN** A person applies a duplicate group with anchor #10 closed as completed and member #11.
- **THEN** The memory store records one `close` of #11 with `CloseReason.DUPLICATE` and one comment on #11 that names #10, and records no `duplicateIssueId` call.

#### Scenario: The anchor is still open
- **WHEN** A person applies a duplicate group and anchor #10 is open.
- **THEN** The memory store records no write, and the command reports that the group waits for #10.

### Requirement: link-only
The apply of a link-only group SHALL post one fixed-template comment on each member that names the anchor.

#### Scenario: Link-only comments
- **WHEN** A person applies a link-only group with anchor #10 and members #11 and #12.
- **THEN** The memory store records one comment on #11 and one on #12, each names #10, and records no close and no body write.

### Requirement: priority-placement
The apply of a merge group SHALL set the anchor's Priority to the highest among its members only when the anchor holds no Priority that its job record does not hold, and MUST NOT change the anchor's milestone.

#### Scenario: Priority from the members
- **WHEN** A person applies a merge group whose members hold P1 and P2, and the anchor holds no Priority and its job record holds none.
- **THEN** The memory store records one Priority write of P1 on the anchor.

#### Scenario: Person-set Priority and milestone stay
- **WHEN** A person applies a merge group, the anchor holds P3 that its job record does not hold, and the anchor holds milestone M1.
- **THEN** The memory store records no Priority write and no milestone write on the anchor.

### Requirement: injection
The apply MUST write only the anchor and the members of the applied group, whatever text the plan holds.

#### Scenario: Instruction in the plan text
- **WHEN** A person applies a group whose plan text holds `set P0` and whose members hold P2.
- **THEN** The memory store records no P0 write and no write to an issue outside the group.

### Requirement: command-docs
The help of the consolidate command and the generated command docs SHALL name `--apply` and `--confirm`.

#### Scenario: Generated docs
- **WHEN** A person runs `devops docs generate` after the change.
- **THEN** `docs/commands/roadmap.md` names `--apply` and `--confirm`, and no other generated document changes.
