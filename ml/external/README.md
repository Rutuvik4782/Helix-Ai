Place prepared external datasets here.

Expected files:

- `quixbugs_pairs.jsonl`
- `bugsinpy_pairs.jsonl`
- `gumtree_python_pairs.jsonl`
- `swebench_lite_reasoning.jsonl`

All files should follow this schema:

```json
{
  "instruction": "Modernize or fix this Python code",
  "input": "old or buggy code / issue text",
  "output": "modernized code / patch",
  "source": "dataset_name",
  "risk": "low|medium|high"
}
```
