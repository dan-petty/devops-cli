# Design

## Decisions

- **Count words, parse no grammar.** A task is refused when it has fewer than two words after each code span becomes one word. The test text of the issue, `Add a test in tests/roadmap/test_roadmap_stage_text_lines.py for a bare filename task`, passes, and so does `Add `form_problems``. The gate cannot tell whether the text names the behavior that the test fails on, and no deterministic rule can. The prompt and the model review keep that duty.
- **Judge three texts.** The `test` text is the first task of a behavior group. The `implementation` text and the `documentation` text are the other tasks, and a bare filename in them says as little. `process` and `verify` have their own rules.
- **Name the group by number and title.** The other problems of the file name the group by its number. The title helps the model find the group in a long reply.
- **Lead word and number only for a title.** The rule reads a summary that starts with `<word> #<number>`, the lead of every plan title. It refuses the word as the first word after the number, and the number as a later token. Another use of the word stays valid, because the titles of #3260 and #3350 hold `plan` later.

## Rejected

- **Refuse every repeated word of a title.** It refuses `fix the fix of the parser` and any title that repeats a noun by need.
- **Refuse `plan` anywhere after the prefix.** Merged plan titles such as `plan #3200 Refuse placeholder and cut plan text` hold the word, and the stage job would stop on a right title.
- **A verb list for the task.** It needs a word list that goes stale, and it refuses a right task that starts with a verb it does not hold.
