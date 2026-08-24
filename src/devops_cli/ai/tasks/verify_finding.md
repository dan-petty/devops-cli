## Finding Verification Protocol
Validate reported findings against visible code, surrounding architecture, build system, and lockfile context:

1. **Test `verification_criteria`**: Confirm observable, concrete conditions proving the defect in visible code, AST structure, and manifest configuration.
2. **Test `invalidation_criteria` & Avoidance Context**:
   - Confirm conditions, parameter validations, type guards, or surrounding architectural mitigations disproving the defect.
   - Confirm presence of modern project configuration and lockfile standards (e.g. `uv.lock`, `poetry.lock`, `package-lock.json`, `Cargo.lock`, `go.sum` proving deterministic dependency resolution when loose dependency ranges are alleged).
   - Confirm whether flagged packages exist and are legitimately pinned or resolved in the project's lockfile before alleging non-existent or confused packages.
   - Confirm if the flagged content is documentation, tutorials, knowledge base articles, test assertions/fixtures, test mocks, template files, or prompt tasks explaining known vulnerabilities or describing insecure configurations in the context of avoiding, preventing, or mitigating them.
3. **Evaluate Fix Actionability & Self-Healing**: Confirm that the proposed `fix` addresses the root cause without introducing regressions, secondary flaws, or breaking type contracts.
4. **Calibrate Confidence & Status**:
   - Any invalidation criterion satisfied, educational/avoidance context detected, or mitigation present → `"status": "INVALIDATED"|"MITIGATED", "verified": false, "reportable": false`.
   - Verification criteria satisfied without invalidation or mitigation → `"status": "VERIFIED", "verified": true, "reportable": true`.
   - Inconclusive, theoretical, or unprovable finding → `"status": "UNVERIFIED", "verified": false, "reportable": false`.

## Output Format
Return ONLY a JSON array with one object per input finding:
```json
[
  {
    "verified": true,
    "mitigated": false,
    "invalidated": false,
    "status": "VERIFIED",
    "reportable": true,
    "severity": "HIGH",
    "location": "path/to/file.ext:12-18",
    "confidence_score": 0.95,
    "verified_criteria_matched": ["Observable defect condition confirmed in source."],
    "invalidated_criteria_matched": [],
    "reason": "Observable defect present in lines 12-18 with no mitigating guards."
  }
]
```
