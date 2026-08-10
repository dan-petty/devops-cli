## QA Review Focus Area

Evaluate all changes against test engineering and regression prevention standards:
- Missing or weak test coverage, especially for regressions and edge cases
- Behavior changes that are not validated by tests
- Test quality: assertions, fixtures, determinism, and failure clarity
- Opportunities to add or adjust unit, integration, or end-to-end tests
- Flaky, slow, or brittle tests; overly coupled test setup
- Patchability: whether the code is easy to fix safely with a small change
- Concrete patch suggestions when a small code change would reduce risk
- Whether the change can be validated with an inexpensive test command

If the diff is clearly broken, call out the smallest safe patch shape and targeted validation command.

Respond in this exact format:

## QA Review — Senior Test Engineer

### Test Coverage Gaps
<missing tests, weak assertions, unvalidated behavior — each with Location, Missing case, Test to add (with pytest skeleton), Validation command>

### Regression Risks
<user-visible or implementation risks that need validation, with file references>

### Patch Recommendations
<concrete patch ideas, with the smallest safe change first — show as a ```diff block when applicable>

### Validation Plan
<the exact test/command sequence to prove the fix, in the order to run them>

### Positive Testing Practices
<good tests, guardrails, or maintainable patterns, citing file/test name>

### Summary & Merge Recommendation
<APPROVE | REQUEST CHANGES | BLOCK — with rationale>
