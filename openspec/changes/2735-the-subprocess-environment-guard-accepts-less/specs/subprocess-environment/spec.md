## ADDED Requirements

### Requirement: Refuse LESS override
build_subprocess_env SHALL raise SecurityError when a caller overrides the key LESS, in upper or lower case, regardless of the isolate_env setting.

#### Scenario: Caller sets LESS to a command string
- **WHEN** A caller calls build_subprocess_env with env={"LESS": "+!x\n"}
- **THEN** The call raises SecurityError with the message "Prohibited dangerous environment variable override: 'LESS'"

#### Scenario: Caller sets LESS with isolation disabled
- **WHEN** A caller calls build_subprocess_env with env={"LESS": "+!x\n"} and isolate_env=False
- **THEN** The call raises SecurityError with the message "Prohibited dangerous environment variable override: 'LESS'"

#### Scenario: Caller sets LESSOPEN after the fix
- **WHEN** A caller calls build_subprocess_env with env={"LESSOPEN": "|x %s"}
- **THEN** The call raises SecurityError as before
