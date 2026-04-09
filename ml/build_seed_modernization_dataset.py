import json
from pathlib import Path


OUTPUT_PATH = Path("ml/data/seed_modernization_dataset.jsonl")


EXAMPLES = [
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": 'print "hello world"\n',
        "output": 'print("hello world")\n',
        "tags": ["print_statement", "python2"],
        "risk": "low",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "for i in xrange(5):\n    print i\n",
        "output": 'for i in range(5):\n    print(i)\n',
        "tags": ["xrange", "print_statement", "python2"],
        "risk": "low",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": 'name = raw_input("Name: ")\nprint name\n',
        "output": 'name = input("Name: ")\nprint(name)\n',
        "tags": ["raw_input", "print_statement", "python2"],
        "risk": "low",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "try:\n    risky()\nexcept ValueError, exc:\n    print exc\n",
        "output": "try:\n    risky()\nexcept ValueError as exc:\n    print(exc)\n",
        "tags": ["except_as", "print_statement", "python2"],
        "risk": "low",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "if a <> b:\n    print a\n",
        "output": "if a != b:\n    print(a)\n",
        "tags": ["not_equal", "print_statement", "python2"],
        "risk": "low",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "for key, value in data.iteritems():\n    print key, value\n",
        "output": "for key, value in data.items():\n    print(key, value)\n",
        "tags": ["iteritems", "print_statement", "python2"],
        "risk": "low",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "if config.has_key('debug'):\n    print config['debug']\n",
        "output": "if 'debug' in config:\n    print(config['debug'])\n",
        "tags": ["has_key", "print_statement", "python2"],
        "risk": "medium",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "value = long(10)\nprint unicode(value)\n",
        "output": "value = int(10)\nprint(str(value))\n",
        "tags": ["long", "unicode", "print_statement", "python2"],
        "risk": "medium",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "def load_all(data):\n    results = []\n    for key in data.iterkeys():\n        results.append(key)\n    return results\n",
        "output": "def load_all(data):\n    results = []\n    for key in data.keys():\n        results.append(key)\n    return results\n",
        "tags": ["iterkeys", "python2"],
        "risk": "low",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "def read_all(data):\n    results = []\n    for value in data.itervalues():\n        results.append(value)\n    return results\n",
        "output": "def read_all(data):\n    results = []\n    for value in data.values():\n        results.append(value)\n    return results\n",
        "tags": ["itervalues", "python2"],
        "risk": "low",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "def check_text(value):\n    return isinstance(value, basestring)\n",
        "output": "def check_text(value):\n    return isinstance(value, str)\n",
        "tags": ["basestring", "python2"],
        "risk": "medium",
    },
    {
        "instruction": "Modernize this legacy Python code to current Python while preserving behavior.",
        "input": "total = 5 / 2\nprint total\n",
        "output": "total = 5 / 2\nprint(total)\n",
        "tags": ["division_semantics", "print_statement", "python2"],
        "risk": "high",
        "note": "Division semantics should be manually reviewed after modernization.",
    },
]


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for example in EXAMPLES:
            handle.write(json.dumps(example, ensure_ascii=True) + "\n")
    print(f"Wrote {len(EXAMPLES)} examples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
