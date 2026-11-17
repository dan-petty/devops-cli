## MODIFIED Requirements

### Requirement: The request holds the recorded check for alternatives
The proposal request and the investigation request of an item SHALL hold the key `alternatives`. For an item whose body holds the job's block and whose job record holds a verdict, it SHALL hold the verdict, the tool URL or null, the block (the result), and the job's latest comment whole (the evidence). Otherwise it SHALL be null. The comment of the job SHALL NOT be one of the `replies`. The prompts SHALL tell the model to cite the block and not to restate it.

#### Scenario: A partly check
- **WHEN** refine plans an item whose job record holds the verdict `partly` and a tool, with the block in its body
- **THEN** the proposal request holds `alternatives` with that verdict, that tool and the text of the job's comment, and the `replies` hold no comment of the job

#### Scenario: A long comment of the job
- **WHEN** the block of an item holds the reason and the lacks, and the latest comment of the job lists more sources than `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS` tokens hold
- **THEN** the request holds the block with the reason and the lacks, and the comment whole

#### Scenario: A check of an older form
- **WHEN** the block of an item holds no `Lacks:` list, and the latest comment of the job lists what the tool lacks
- **THEN** the request holds that comment with the lacks

#### Scenario: No check
- **WHEN** refine plans an item with no block in its body
- **THEN** the request holds `alternatives` null

#### Scenario: A block that a person deleted
- **WHEN** the job record holds a verdict and the body holds no block
- **THEN** the request holds `alternatives` null
