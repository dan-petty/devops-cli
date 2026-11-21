# Design

## Decisions

- **Run the check after the model writes the plan and before the stage job commits it.**: A model can ignore a prompt rule, and the job then commits the text; a deterministic gate stops the bad plan at the reply.
- **Keep a bounded list of phrases that name an earlier reply or a self-correction, and read only the Feasibility lines.**: The defect is one class of text, and a bounded list keeps the probe quotations and the file citations that the section must hold.
- **Fail with the line number and the phrase, and report every refused line in one reply.**: A person and the model read which line and which phrase the gate refused, and one repair fixes them all.
- **Ignore each line inside a fenced code block and each block quotation, and the text inside an inline code span.**: A probe quotation can hold the same words as the defect, and a plan quotes a probe line in a code span, so the rule refuses the text of the model, not the evidence that it quotes.
- **Give the rule a gate name of its own, `meta-text`.**: `devops roadmap plan-recheck` and the log of a refused reply name the rule that refused a plan, and one gate is one name.

## Rejected alternatives

- **Write the rule in the stage prompt only.**: A model that ignores the instruction writes the text, and the stage job commits it; the issue reports that outcome in a merged plan.
- **Judge the plan with a second model call.**: The answer of a model changes between runs and costs a call, and the project keeps its findings from tools and checked facts.
- **Refuse every first-person word in the Feasibility section.**: A probe line or a command line can hold `I`, and the rule would then refuse objective evidence.
- **Read the whole proposal for repair text.**: The issue scopes the defect to the Feasibility section, and another section can quote a person or a model without becoming a system fact.
