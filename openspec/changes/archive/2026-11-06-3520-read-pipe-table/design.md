# Design

## Decisions

- **Read the pipe in `ShellRefusal`, and give the harness the denied operators without `|`.**: The harness matches an operator as plain text, so it cannot admit a pipe and refuse a second shell (`| sh`). The wrapper runs before the harness for every call. It reads the stages of the command and refuses a pipe to a program outside the table. `|` stays in `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS`, so the wrapper and a test read one tuple, and `_tune` removes only the pipe for the harness.
- **Split the command with `shlex` and `punctuation_chars=True`.**: A quoted `|` and an escaped `\|` are part of a word, so a `grep` pattern with an alternation runs. A `|` token splits the stages.
- **Refuse a token that holds `|` and no other kind of character, when it is not exactly `|`.**: `|&` and `)|` start a pipe in the shell. `||` is still in the tuple for the harness.
- **Check the redirect of each right-hand stage with the same function as the first stage.**: A stage such as `head > out.txt` would write a file. The stage program has access `read` in `SHELL_PROGRAMS`, so `_refused_word` refuses the redirect.
- **Strip the exact prefix `cd <checkout> &&`, and pass the rest to the harness.**: The prefix changes the directory to the directory that every command already has. The harness then sees no `&&`, and any other `&&` stays refused by the harness. The model does not have to know the rule.
- **Add `wc` to `SHELL_PROGRAMS`.**: One table holds the allowlist, the prompt, the document and the log. A pipe table that names a program outside it would need a second table.
- **Log an unknown first word as `other:<digest>`.**: The digest is the first 12 hexadecimal characters of the HMAC-SHA256 of the word. The key is random and lives in the process only. One word has one digest in a run, so a person groups the unknown programs of a step, and the log never holds the word. The line before a call keeps the plain `other`. The line of a call that starts with `cd <checkout> &&` names the program after the prefix.

## Rejected alternatives

- **Remove `|` from `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS`.**: The harness reads the first word only, so `ls | sh` would run.
- **Subclass `Shell` of the harness.**: It uses a private method of the harness.
- **Use `bashlex`.**: It adds a third-party parser. The policy needs only the pipe tokens that `shlex` gives.
- **Admit `sort`, `uniq`, `sed`, `awk`, `cat` or `ls` to the right of a pipe.**: `sort -o` and `sed -i` write a file, and `awk` runs commands. `cat` and `ls` give no gain at the end of a pipe.
- **Write the free first word to the log.**: The first word can hold a secret (`implement_tool_log.py`).
- **A plain SHA-256 of the word, as the trace writes a digest.**: The log goes to GitHub comments. A first word can be a weak password, and a dictionary finds the word from a 12-character plain hash. A keyed digest groups the words of one run and cannot be reversed. A person who wants the same digest in every run must allow the plain hash: that is a decision of the owner.
