# Design

## Decisions

- **Judge only `reads` and `reading`, and only with a code span, `it` or `which` before the verb.**: The present tense after such a subject states what the code does. `read` and `ran` stay claims, because they state what happened.
- **Let a comma, `is` or `are` stand between the subject and the verb.**: "`check`, reading `x`" and "it is reading `x`" have the same subject.
- **Judge each read word of a sentence.**: A sentence with an exempt `reads` and a claim of the run ("I read `b.py`") stays refused.
- **Read the words before the verb in the sentence, not in the claim text.**: The claim text blanks the code spans, and a code span is a subject.

## Rejected alternatives

- **Parse the sentence with a natural-language library.**: The gate has one question about one verb, and a parser adds a dependency and a model download.
- **Exempt every sentence with a code span before the verb.**: "the plan cites `x` and the run read `y`" would pass. The pattern requires the code span to stand right before the verb.
