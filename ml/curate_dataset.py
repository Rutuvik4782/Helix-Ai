import json
import re
import ast
from pathlib import Path
from typing import Any, Optional


SOURCE_PATH = Path("phase2_refactoring_dataset.jsonl")
SEED_PATH = Path("ml/data/seed_modernization_dataset.jsonl")
OUTPUT_PATH = Path("ml/data/modernization_train.jsonl")
REJECTS_PATH = Path("ml/data/rejected_examples.jsonl")


LEGACY_HINTS = (
    "xrange",
    "raw_input",
    ".iteritems(",
    ".iterkeys(",
    ".itervalues(",
    ".has_key(",
    "<>",
    "unicode",
    "basestring",
    "long(",
)

LEGACY_REGEX_HINTS = (
    re.compile(r"^\s*print\s+[^(\n].*$", re.MULTILINE),
    re.compile(r"^\s*except\s+[^:\n]+,\s*[A-Za-z_]\w*\s*:", re.MULTILINE),
)

NON_PYTHON_REJECT_PATTERNS = (
    re.compile(r"^\s*function\s+", re.MULTILINE),
    re.compile(r"[{}];?"),
)

STOPWORDS = {
    "def", "class", "for", "if", "try", "except", "return", "print", "import", "from",
    "while", "in", "as", "True", "False", "None",
}


def extract_code(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        candidates = []
        for value in payload.values():
            extracted = extract_code(value)
            if extracted:
                candidates.append(extracted)
        candidates.sort(key=len, reverse=True)
        return candidates[0] if candidates else ""
    if isinstance(payload, list):
        for value in payload:
            extracted = extract_code(value)
            if extracted:
                return extracted
    return ""


def looks_like_python(code: str) -> bool:
    if not code:
        return False
    tokens = ("def ", "class ", "for ", "if ", "try:", "except", "return", "print", "import ")
    return any(token in code for token in tokens) and not any(pattern.search(code) for pattern in NON_PYTHON_REJECT_PATTERNS)


def parses_as_python3(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def identifier_overlap_ratio(input_code: str, output_code: str) -> float:
    tokens = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
    input_tokens = {tok for tok in tokens.findall(input_code) if tok not in STOPWORDS}
    output_tokens = {tok for tok in tokens.findall(output_code) if tok not in STOPWORDS}
    if not input_tokens:
        return 0.0
    return len(input_tokens & output_tokens) / len(input_tokens)


def is_modernization_example(instruction: str, input_code: str) -> bool:
    if any(hint in input_code for hint in LEGACY_HINTS):
        return True
    return any(pattern.search(input_code) for pattern in LEGACY_REGEX_HINTS)


def normalize_record(record: dict) -> Optional[dict]:
    instruction = str(record.get("instruction", "")).strip()
    input_code = extract_code(record.get("input", ""))
    output_code = extract_code(record.get("output", ""))

    if not looks_like_python(input_code) or not looks_like_python(output_code):
        return None
    if not parses_as_python3(output_code):
        return None
    if not is_modernization_example(instruction, input_code):
        return None
    if identifier_overlap_ratio(input_code, output_code) < 0.35:
        return None

    return {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": input_code,
        "output": output_code,
        "source": "phase2_refactoring_dataset",
        "risk": infer_risk(input_code),
    }


def infer_risk(code: str) -> str:
    if re.search(r"(?<!/)/(?!/)", code):
        return "high"
    if any(token in code for token in ("unicode", "basestring", ".has_key(")):
        return "medium"
    return "low"


def load_seed_examples() -> list[dict]:
    if not SEED_PATH.exists():
        return []
    examples = []
    with SEED_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    accepted = []
    rejected = []

    if SOURCE_PATH.exists():
        with SOURCE_PATH.open(encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                record = json.loads(raw)
                normalized = normalize_record(record)
                if normalized:
                    accepted.append(normalized)
                else:
                    rejected.append(record)

    accepted.extend(load_seed_examples())

    deduped = []
    seen = set()
    for record in accepted:
        key = (record["input"], record["output"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for record in deduped:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    with REJECTS_PATH.open("w", encoding="utf-8") as handle:
        for record in rejected[:500]:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    print(f"Accepted {len(deduped)} modernization examples -> {OUTPUT_PATH}")
    print(f"Rejected {len(rejected)} noisy examples -> {REJECTS_PATH}")


if __name__ == "__main__":
    main()
