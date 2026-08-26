Generate a comprehensive `AGENTS.md` file providing structured guidance and engineering principles for AI coding assistants using a 4-step chain-of-thought synthesis:

### Step 1: Project Stack & Runtime Deconstruction
- Analyze the project runtime (Python 3.14+, Astral `uv`, lockfiles, build systems) and core libraries.

### Step 2: Verification & Workflow Scaffolding
- Detail the progressive testing strategy and mandatory iterative CI loop: make all planned code changes, run `devops ci`, fix reported issues, and run `devops ci` again until passing, avoiding redundant separate tooling already covered by `devops ci`.
- Define Git hygiene: topic branch hierarchy (`feat/*`, `fix/*` targeting `release/v*`), Conventional Commits, and remote CI checks monitoring.

### Step 3: Architecture & Security Synthesis
- Define clean architecture: separation of concerns, strict typing (`mypy --strict`), and aiming for fewer than 6 indentations project-wide by decomposing complex nested logic into dedicated functions.
- Define zero-trust security: OS Keyring credentials, SSRF mitigation, bounded subprocesses, and strict prohibition on leaking data from hidden, private, or `.gitignored` files into documents or code.
- Define prompt isolation: all LLM prompts in dedicated markdown files under `src/devops_cli/ai/tasks/` (zero inline strings).
- Define canonical output convention: project-wide `filename.ext:n-n` location referencing.

### Step 4: Output Assembly
- Format the final document with clear Markdown headings, tables, and clickable references.
