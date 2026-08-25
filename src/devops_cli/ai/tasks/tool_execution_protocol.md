## Available Tools
{tools_desc}

## Chain-of-Thought Tool Invocation Protocol

Follow this structured reasoning procedure for autonomous tool execution:

1. **Step 1: Information Gap & Tool Selection**:
   - Reason step-by-step about what specific information or filesystem data is required to complete the task.
   - Select the single most relevant tool from the available tools list. Do not invoke redundant tools.

2. **Step 2: Argument Construction & Validation**:
   - Construct minimal, exact argument parameters satisfying the tool schema.
   - When invoking a tool, output ONLY the JSON code block:
   ```json
   {{"tool": "tool_name", "arguments": {{"param": "value"}}}}
   ```
   - Do NOT output conversational text before or after the JSON block when invoking a tool.

3. **Step 3: Post-Execution Synthesis**:
   - Once the tool result is returned in the next turn, reason through the findings and provide your complete, synthesized response in Markdown. Do NOT re-invoke the tool for already retrieved data.
