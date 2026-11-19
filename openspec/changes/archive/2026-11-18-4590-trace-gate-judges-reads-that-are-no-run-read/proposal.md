# Proposal

## Problem
The Feasibility trace gate of the stage job refuses sentences that make no claim that the run read a file. The gate judges the last path before a relative-clause read. It judges the object after a code subject in parentheses. It judges the object after a subject of code spans only. It also treats `cannot` as no negation.

## Solution
1. Update `_object_span` to not judge the last path before a relative-clause read whose object holds no path.
2. Update `_CODE_READS` to permit parenthesized citations after code subjects.
3. Update `_is_code_reading` to recognize a plural list of code spans before `read`.
4. Update `_NEGATION` to include `cannot`.
5. Update `_citation` to strip a trailing line range from a path span.

## Impact
Removes false refusals in the stage job Feasibility trace gate while preserving checks on true claims of run reads.
