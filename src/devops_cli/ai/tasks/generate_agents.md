Generate a comprehensive `AGENTS.md` file providing structured guidance and engineering principles for AI coding assistants using a 4-step chain-of-thought synthesis:

### Step 1: Project Stack & Runtime Deconstruction
- Analyze the project runtime (e.g. Python, Go, Rust, TypeScript, Java, C#, HCL), toolchains, package managers, and lockfiles.

### Step 2: Verification & Workflow Scaffolding
- Detail the progressive testing strategy and mandatory iterative CI loop: make all planned code changes, run the primary CI verification gate (e.g. `devops ci` or project test suite), fix reported issues, and run verification again until passing.
- Define Git hygiene: topic branch hierarchy (`feat/*`, `fix/*` targeting `release/v*`), Conventional Commits, and remote CI checks monitoring.

### Step 3: Architecture & Security Synthesis
- Define clean architecture: separation of concerns, static typing, and aiming for fewer than 6 indentations project-wide by decomposing complex nested logic into dedicated functions.
- Define zero-trust security: secure credential management, SSRF mitigation, bounded subprocesses, and strict prohibition on leaking data from hidden, private, or `.gitignored` files into documents or code.
- Define prompt isolation: all LLM system prompts and task instructions in dedicated markdown files (zero inline strings).
- Define canonical output convention: project-wide `filename.ext:n-n` location referencing.

### Step 4: Output Assembly
- Format the final document with clear Markdown headings, tables, and clickable references.
