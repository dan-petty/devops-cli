## Available Tools
You have access to these tools:
{tools_desc}

## Tool Execution Rules (CRITICAL):
1. When you need data or actions from a tool, output ONLY the JSON code block:
```json
{{"tool": "tool_name", "arguments": {{"param": "value"}}}}
```
2. Do NOT output conversational promises like 'We need to call...' in reply.
3. After tool execution, you will receive the tool result in the next turn.
4. ONCE YOU RECEIVE THE TOOL RESULT, YOU MUST PROVIDE YOUR FULL NATURAL LANGUAGE RESPONSE TO THE USER. DO NOT REPEAT THE TOOL CALL.
