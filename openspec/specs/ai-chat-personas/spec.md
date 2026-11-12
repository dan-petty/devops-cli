# ai-chat-personas Specification

## Purpose
What `devops ai chat` gives each persona: the system prompt, the agent tools and the RAG search terms.

## Requirements

### Requirement: Each chat persona gets its prompt, its own tools and its RAG terms
The chat prompt of a persona SHALL be its `role.md`, `tasks/chat.md` and `prompt.md`. The tool map and the RAG search terms SHALL have one entry for each `Persona`, and no persona SHALL get the default tool set. Challenger SHALL get only read and search tools. A RAG search for a name that is not a `Persona` SHALL keep its query.

#### Scenario: Challenger in chat
- **WHEN** a person chats with challenger
- **THEN** the system prompt holds the text of `personas/challenger/prompt.md`, and the agent gets 6 read-only tools

#### Scenario: A name that holds "sec"
- **WHEN** a RAG search runs for the name "security-lead"
- **THEN** the query gets no security terms
