## ADDED Requirements

### Requirement: The Terraform lint tool runs the tflint adapter
The agent tool `tf_lint` SHALL run the tflint adapter over its target, a path inside the workspace. It SHALL keep no command line of its own, and SHALL reply as the other agent scan tools reply. No agent tool SHALL analyze the layers of an image.

#### Scenario: tflint is not installed
- **WHEN** no directory of PATH holds tflint, and the agent calls `tf_lint` over a directory of the workspace
- **THEN** the reply is `TFLint scan status: not installed`, then `Reason: Binary 'tflint' not found on PATH`, then `The scan gave no result. Do not report the target as clean.`

#### Scenario: tflint finds an issue
- **WHEN** the agent calls `tf_lint` over a directory in which tflint reports one issue
- **THEN** the reply is `TFLint scan status: ok`, then `Findings (1):`, then one line for the finding

#### Scenario: The agent tools are listed
- **WHEN** a test lists the names of the agent tools
- **THEN** no name is `docker_analyze_layers`
