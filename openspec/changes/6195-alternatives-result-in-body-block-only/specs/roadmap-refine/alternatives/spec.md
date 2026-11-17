## MODIFIED Requirements

### Requirement: The request holds the recorded check for alternatives
The proposal request and the investigation request of an item SHALL hold the key `alternatives`. For an item whose body holds the alternatives job's block and whose job record holds a verdict, it SHALL be an object with the verdict, the tool URL or null, the block, and the job's latest comment whole, with no cut. The block SHALL be the source of the result: the reason, and what the tool covers and lacks. The comment SHALL be the evidence of the run; the comment of an older check also holds what the tool covers and lacks, and the request keeps it. Otherwise the key SHALL be null. The comment of the job SHALL NOT be one of the `replies`. The prompts SHALL name the block as the source, SHALL tell the model to cite the block and not restate it, and SHALL tell the model not to write that no check has run when the key is not null.

#### Scenario: A partly check
- **WHEN** refine plans an item whose job record holds the verdict `partly` and a tool, with the block in its body
- **THEN** the proposal request holds `alternatives` with that verdict, that tool and the text of the job's comment, and the `replies` hold no comment of the job

#### Scenario: A long comment of the job
- **WHEN** the block of an item holds the reason and the lacks, and the latest comment of the job lists more sources than `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS` tokens hold
- **THEN** the request holds the block with the reason and the lacks, and the comment whole

#### Scenario: No check
- **WHEN** refine plans an item with no block in its body
- **THEN** the request holds `alternatives` null

#### Scenario: A block that a person deleted
- **WHEN** the job record holds a verdict and the body holds no block
- **THEN** the request holds `alternatives` null
