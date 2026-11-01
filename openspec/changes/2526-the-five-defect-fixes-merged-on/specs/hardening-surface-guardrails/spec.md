## Purpose
The root-cause guardrails that each defect fix records in a declared hardening surface, so the defect class does not return.

## ADDED Requirements

### Requirement: guardrail_per_defect
Each defect fix SHALL record its root-cause lesson in at least one declared hardening surface.

#### Scenario: guardrail_text_present_in_surface
- **WHEN** a test reads the declared hardening surfaces for a defect PR's guardrail
- **THEN** the guardrail text is present in at least one surface, naming the defect class and the prevention rule

### Requirement: guardrail_names_defect_class
Each guardrail entry SHALL name the defect class it prevents and the rule that prevents it.

#### Scenario: guardrail_text_is_specific
- **WHEN** a test reads a guardrail entry in its surface
- **THEN** the entry contains the defect class name and the prevention rule text

### Requirement: guardrail_in_best_fit_surface
Each guardrail SHALL appear in exactly one declared surface that best fits its defect class.

#### Scenario: single_surface_per_guardrail
- **WHEN** a test searches all declared surfaces for a guardrail's defect class name
- **THEN** the defect class name appears in exactly one surface
