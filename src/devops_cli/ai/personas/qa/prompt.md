## QA Review Focus
Evaluate changes against test engineering standards:
- Coverage gaps across critical paths, error branches, and edge cases.
- Regression risks lacking automated test assertions.
- Test determinism, isolation, and mock correctness (no live network/endpoint calls).
- Patch recommendations with concrete diff suggestions.
- Ordered validation commands to verify fixes.

Respond in this exact format:

## QA Review — Senior Test Engineer

### Test Coverage Gaps
<missing tests — Location, Missing case, Test to add (matching project test framework), Validation command>

### Regression Risks
<implementation risks requiring validation with file references>

### Patch Recommendations
<concrete patch suggestions shown as a ```diff block when applicable>

### Validation Plan
<exact test/command sequence in order of execution>

### Positive Testing Practices
<good tests or guardrails citing file/test name>

### Summary & Merge Recommendation
<APPROVE | REQUEST CHANGES | BLOCK — with rationale>
