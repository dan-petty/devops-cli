Provide technical pseudocode representing key structure and logic (targeting 6-10 lines for complex files, down to 1 line for simple assets).

CRITICAL REQUIREMENTS:
- Output 1 to 20 lines of pseudocode steps, one per line.
- Focus strictly on technical logic, specific function/method calls, data structures, configuration keys, and exact operational steps.
- Output should look like an absolutely minimalistic interpretation of the source file.
- STRICTLY EXCLUDE ALL IMPORT STATEMENTS AND DEPENDENCIES (e.g. NEVER output lines starting with "import ", "from ... import ...", "require(...)", or "#include"). Imports and dependencies are strictly extracted into separate metadata fields.
- Do not reference the filename in pseudocode.
- Do not use explanatory or descriptive text.
- Limit output to a subset of abbreviated words used in the source document.

EXAMPLE:
``` python
#SOURCE
def parse_json_data(
    buffer: Buffer,
    context: ParseContext,
) -> Result[ParsedJSON, LexError]:
    """
    Parses a JSON object from a buffer.
    """
    buffer.drop_comments()
    if buffer.current().is_whitespace():
        return Err(LexError.unexpected_eof())
    if buffer.peek_next().is_number() or buffer.peek_next().is_literal():
        value_result = parse_value(buffer, context)
        return value_result.map(
            lambda v: ParsedJSON(JSONType.VALUE, [v], buffer.position())
        )
    elif buffer.current() == TOKEN_OPEN_BRACE:
        return parse_object(buffer, context)
    elif buffer.current() == TOKEN_OPEN_BRACKET:
        return parse_array(buffer, context)
    else:
        raise LexicalError(
            f"Invalid JSON value at position {buffer.position()}",
            Context("JSON Parse", "BufferRead"),
        )
```

``` pseudocode
#PSEUDOCODE OUTPUT
p_j_d(b, c) -> Result[ParsedJSON, LexError]:
    b.drop_comments()
    if b.curr().is_w():
        r e(unexp_eof)
    if b.p_n().is_n() or b.p_n().is_l():
        r parse_v(b, c).m(l)
    elif b.curr() == T_O_B:
        r parse_o(b,c)
    elif b.curr() == T_O_BKT:
        r parse_a(b,c)
    else:
        raise LexicalError(INVALID_JSON_ERROR, c)
```
