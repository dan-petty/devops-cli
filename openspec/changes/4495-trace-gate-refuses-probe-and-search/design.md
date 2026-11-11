# Design

## Decisions

- **The subject is the words of the clause before the read word.** A clause starts after a `,`, `;`, `:`, a parenthesis, or a word such as `and`, `so`, `because`, `after`, `by`, `that` or `which`. A relative pronoun, `and` or `or` with no word after it shares the subject of the words before it ("the code that reads", "it fetches the head and reads"). A comma does the same for a verb ("this plan cites `x`, reads `y`") but not for `reading`, which is its own subject ("After the probe, reading `x` shows").
- **An empty subject is a claim of the run.** Articles, determiners, auxiliary verbs and adverbs name no reader. So "Read `x`", "Reading `x` shows", "the same read shows" and "`x` was read" stay claims, as before. Only a subject with another word is no claim, unless the word names the run or its author: `I`, `we`, `my`, `our`, `run`, `runs`, `planner`, `agent`.
- **The object is the path that the read takes.** For a passive it is the first path of the subject. Else it is the first path after the read word, up to `;` or a comma before a new clause. With no path after it, the read reads the last path before it in the sentence, so "`read_file` of it" and "the same file" keep their claim. A sentence with no such path makes no path claim.
- **A search match supports a citation of its line only.** `ToolCallRecord.matches` holds the `path:line` of each match line of a `search_code` or `callers` answer, and `TraceFacts.lines` joins them. A `path:line` or `path:line:text` citation of such a line is seen. A bare path and a line range are not, because the run saw one line.
- **A probe line is no read.** The gate already removes a quoted probe sentence (#4463), and "the probe reads" now has a subject that is not the run.

## Rejected alternatives

- **Exempt a list of subjects (`the plan`, `the group`, `the probe`).** Each new subject would cause one more false refusal. The change lists the reader words instead.
- **Count every path of a search answer or a probe line as read.** It would accept a claim of a whole file from one line, and of a path that the probe says is no file.
- **A dependency parser (spaCy).** It needs a model download and a large dependency, and it does not read code spans. The gate needs only the clause of one word.
- **Keep the first path of the sentence when the read has no object.** It refuses the search hit of #3453, which a later clause names.
