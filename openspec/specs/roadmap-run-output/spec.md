# roadmap-run-output Specification

## Purpose
The masked, capped and quoted text of one command that the planner runs (ADR 0018): at most 8192 bytes and 120 lines with a counted trailer, masked before the cut, and fenced for the `## Feasibility` section.

## Requirements

### Requirement: The output of one run has a cap
`cap_run_output` SHALL return at most 8192 UTF-8 bytes and at most 120 lines, the trailer line included, and SHALL cut only at a line boundary.

#### Scenario: Long output is cut
- **WHEN** the input holds 20000 bytes over 400 lines
- **THEN** the returned text holds at most 8192 bytes and at most 120 lines

### Requirement: The trailer names the omitted counts
The returned text SHALL end with one line `[truncated: N bytes and M lines omitted]` when the cut leaves text out, and the kept body plus the counts SHALL equal the masked input.

#### Scenario: The cut leaves text out
- **WHEN** the input holds 20000 bytes over 400 lines
- **THEN** the last line matches the trailer form, and the kept body plus the counts equal the input counts

### Requirement: A short output has no trailer
The function SHALL return the masked input with no trailer line when the text fits within both caps.

#### Scenario: Short output is kept whole
- **WHEN** the input holds 200 bytes over 3 lines
- **THEN** the returned text equals the masked input and holds no `[truncated:` line

### Requirement: The output is masked before the cut
`cap_run_output` SHALL pass the whole text through `mask_secrets` before it cuts, so a private-key block whose end marker is past the cap is masked whole.

#### Scenario: A token on stderr
- **WHEN** the input holds a GitHub token
- **THEN** the returned text holds `<masked-github-token>` and none of the token characters

#### Scenario: The cap falls inside a private-key block
- **WHEN** the input holds a PEM private key whose end marker sits after byte 8192
- **THEN** the returned text holds `<masked-private-key>` and no line of the key body

### Requirement: The quote block holds the command and the exit code
`quote_run` SHALL open a fence one backtick longer than the longest backtick run in the text, and never fewer than three, then write the command line, `exit <code>`, the text and a closing fence of the same length.

#### Scenario: A failed run
- **WHEN** the command exits 1 and writes 3 lines with one three-backtick line
- **THEN** the block opens with ````, holds the command line and `exit 1`, and closes with ````
