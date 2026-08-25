Extract factual file metadata for code review using a structured chain-of-thought analysis:
1. **Module Responsibility**: Formulate a concise, factual one-sentence summary of the file's primary responsibility.
2. **Symbol Extraction**: Enumerate declared classes, functions, and primary constants directly defined in the file.
3. **Dependency Mapping**: List imported third-party libraries and local package submodules.
4. **Structural Pseudocode**: Trace 4-10 concise structural logic steps representing core execution flow without imports.
5. **Score Calibration**: Reason through complexity (`Low` | `Medium` | `High`), confidence (0.0–1.0), and code quality (0.0–1.0).

Return ONLY a JSON object:
```json
{
  "primary_purpose": "One-sentence summary of file responsibility",
  "key_symbols": ["List", "of", "defined", "classes_or_functions"],
  "dependencies": ["imported_modules"],
  "pseudocode": ["4-10 concise structural logic steps"],
  "complexity_score": "Low" | "Medium" | "High",
  "confidence_score": 0.95,
  "quality_score": 0.90
}
```
