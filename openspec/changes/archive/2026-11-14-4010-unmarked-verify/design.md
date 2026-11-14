# Design

## Context

`_group` reads the first task and the verification problems before it infers the kind. `TaskGroup.verification_commands` holds only the spans that start with `$ `, so an unmarked span is absent.

## Goals

- Name the missing marker.
- Keep the valid forms unchanged.

## Decisions

- **Check the spans of `Verification:` lines only.** The loop reads the lines that start with `- Verification:` and matches each code span. A span outside those lines is no command.
- **Fail before the kind.** The check runs before `_kind`, so no message can say `kind other`.
- **One message.** It names the group and the span and shows the marked form.

## Risks

- A line with a marked span and an unmarked span is refused. The unmarked span is a fault in the plan grammar.

## Tests

- An unmarked span gives the marker message and no `kind other` text.
- A marked plan reads.
- An inline span outside a `Verification:` line reads.
