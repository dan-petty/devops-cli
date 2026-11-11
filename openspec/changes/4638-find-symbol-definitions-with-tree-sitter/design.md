# Design

## Decisions
- One search for all languages. The first `git grep -F -w` finds every line of a source file that names the name. The Python expression picks the Python definitions from these lines, so a lookup in a Python repository costs one command, as before, and the stage probe keeps its bound.
- Python first. When a Python file defines the name, the lookup returns those lines and reads no other file. A lookup that the Python files answer gives the same lines as before.
- One read for the other languages. `git grep -n -z -I -e ^` with a `:(literal)` pathspec for each file prints every line of those files in one command. The lookup parses at most 20 files, so the output stays small.
- The definition line is the first line of the span of the symbol that holds the name. A Java method with an annotation above it starts at the annotation, but its name is on the next line.
- The probe passes the commands it has left. With one command left and other files to read, the lookup returns None, and the probe lists the identifier as not probed. A probe line never says that a name has no definition when the lookup did not read the files.
- Markdown files are no source: a heading is no definition, and a document that names a symbol is no caller.

## Rejected alternatives
- The `TAGS_QUERY` of each grammar, as the issue proposes. The bash, HCL, Dockerfile, YAML and Markdown packages have none, C# gives None, and TypeScript holds only signatures. A query of our own for each language would be custom logic for each grammar, while `TreeSitterEngine` already maps them.
- A second `git grep` for the other languages after the Python search. A Python repository would then pay two commands for each name that has no definition, and the probe would reach its bound sooner.
- One `git show` for each file of another language. A name that 5 files name would cost 6 commands, more than half the bound of the probe.
- A probe that runs past its bound by one command. The spec says that the probes of one item run at most 10 commands.
