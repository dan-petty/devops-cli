## Finding Verification Protocol
Validate reported findings against visible code, surrounding architecture, and file context:

1. **Test `verification_criteria`**: Confirm observable, concrete conditions proving the defect in code.
2. **Test `invalidation_criteria`**: Confirm conditions, parameter validations, or surrounding mitigations disproving the defect.
3. **Calibrate Confidence & Status**:
   - Any invalidation criterion satisfied or mitigation present → `"status": "INVALIDATED"|"MITIGATED", "verified": false, "reportable": false`.
   - Verification criteria satisfied without invalidation or mitigation → `"status": "VERIFIED", "verified": true, "reportable": true`.
   - Inconclusive or unprovable finding → `"status": "UNVERIFIED", "verified": false, "reportable": false`.

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
