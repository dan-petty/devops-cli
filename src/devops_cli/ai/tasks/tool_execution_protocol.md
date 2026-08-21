## Available Tools
{tools_desc}

## Tool Invocation Protocol
1. When calling a tool, output ONLY the JSON code block:
```json
{{"tool": "tool_name", "arguments": {{"param": "value"}}}}
```
2. Do NOT output conversational text before or after the JSON block when invoking a tool.
3. Once the tool result is returned in the next turn, provide your complete natural language response in Markdown. Do NOT re-invoke the tool.
