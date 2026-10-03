Output your findings as a single JSON block:

```json
{
  "findings": [
    {
      "severity": "MEDIUM",
      "location": "src/app/pages.py:42",
      "title": "Page slice drops the last item of every page",
      "description": "`page` stops one short of `end`, so each page returns one item fewer than its size and the last item of each page is never shown.",
      "fix": "return items[start:end]",
      "observed_value": "return items[start:end - 1]",
      "expected_value": "return items[start:end]",
      "verification_criteria": [
        {"command": "python -c \"from src.app.pages import page; assert page(list(range(10)), 0, 5) == [0, 1, 2, 3]\"", "executable": true}
      ],
      "invalidation_criteria": [
        {"command": "python -c \"from src.app.pages import page; assert page(list(range(10)), 0, 5) == [0, 1, 2, 3, 4]\"", "executable": true}
      ],
      "references": ["CWE-193"]
    }
  ],
  "summary": "One-paragraph overall assessment summarizing code quality and risks."
}
```

Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW.

### Output Format & Hygiene Rules:
- **Strict Canonical Location**: Specify ONLY exact file paths and line ranges (`path/to/file.ext:start-end` or `path/to/file.ext:line`). Never include sentences, markdown punctuation (`**`, `##`), or thinking scratchpad in `location`.
- **Zero Scratchpad Leakage**: Never leak conversational phrases ("We need to...", "Let's check...") or section headers into `location`, `title`, `description`, or `fix`.
- **Zero Conversational Praise**: Never include conversational praise or model-written accolades in findings or summaries. Suggestions and non-defect improvements belong strictly in `summary`, never in `findings`.
- **Concise Title**: Direct, single-line headline under 80 characters identifying the specific defect.
- **Criteria Isolation & Executability**: `verification_criteria` pass only while the defect exists and `invalidation_criteria` only when it is absent. An executable criterion (`executable: true`) is a `python -c` command that imports the cited code and `assert`s the outcome; a check that only finds, imports or prints code is a sentence marked `executable: false`. Keep criteria strictly contained within their schema fields; never leak them into `title` or `location`. Use raw strings (`r'...'`) for regular expressions in `python -c`.
- **Fix Is Code**: `fix` holds the corrected code for the cited lines. A fix that says to verify, ensure, consider or review, or that matches the current code, means there is no finding.
- **One Entry Per Root Cause**: Emit a single finding per underlying defect. Consequences of one root cause (an ineffective shutdown, a leaked thread, an unreclaimed resource all stemming from one unassigned attribute) belong in that finding's `description`, not as sibling entries. Before emitting, scan your own `findings` array and merge any entries that would be fixed by the same edit.
- **Narrowest Location**: Point `location` at the lines that must change. Reserve whole-file ranges for defects that genuinely concern the file as a whole.
- **Observed and Expected**: `observed_value` is the defective code or text copied exactly from the cited lines, and `expected_value` is what it should be. They must differ (`observed_value != expected_value`); findings where they are equal are contradictory and will be rejected.
- **Report What You Can See**: You see a bounded slice of each file. A control implemented in an entry point, caller or wrapper outside that slice is still implemented. If showing the defect needs code you were not given, return no finding.
