## Finding Verification Protocol
Validate reported findings against visible code and related file metadata:

1. **Test `verification_criteria`**: Confirm observable conditions proving the defect in code.
2. **Test `invalidation_criteria`**: Confirm conditions/mitigations disproving the defect.
3. **Determine Status & Confidence**:
   - Any invalidation criterion satisfied → `"status": "INVALIDATED"|"MITIGATED", "verified": false, "reportable": false`.
   - Verification criteria satisfied without invalidations → `"status": "VERIFIED", "verified": true, "reportable": true`.

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
    "verified_criteria_matched": ["..."],
    "invalidated_criteria_matched": [],
    "reason": "Observable defect present in lines 12-18 with no mitigating guards."
  }
]
```
