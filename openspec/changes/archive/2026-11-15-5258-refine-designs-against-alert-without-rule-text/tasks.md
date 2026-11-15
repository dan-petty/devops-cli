# Tasks

## 1. Behavior

- [x] 1.1 Write tests for alert reading and refine judge validation
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alert.py`
- [x] 1.2 Implement `rule_description` and `read_alert` in `alert_filer.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alert.py`
- [x] 1.3 Implement `alert_number_of` and alert context injection in `refine.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alert.py`
- [x] 1.4 Implement alert comparison in `refine_judge.py`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alert.py`

## 2. Documents

- [x] 2.1 Update OpenSpec change artifacts
  - Verification: `$ uv run devops openspec validate 5258-refine-designs-against-alert-without-rule-text`
