import argparse
import json
from pathlib import Path


OUTPUT_PATH = Path("ml/external/bugsinpy_pairs.jsonl")


def collect_python_files(root: Path) -> dict[str, Path]:
    files = {}
    for path in root.rglob("*.py"):
        files[path.name] = path
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--buggy-root", required=True, help="Path to buggy checkout/root")
    parser.add_argument("--fixed-root", required=True, help="Path to fixed checkout/root")
    args = parser.parse_args()

    buggy_root = Path(args.buggy_root)
    fixed_root = Path(args.fixed_root)
    buggy_files = collect_python_files(buggy_root)
    fixed_files = collect_python_files(fixed_root)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for name, buggy_path in sorted(buggy_files.items()):
            fixed_path = fixed_files.get(name)
            if not fixed_path:
                continue

            buggy_code = buggy_path.read_text(encoding="utf-8", errors="ignore")
            fixed_code = fixed_path.read_text(encoding="utf-8", errors="ignore")
            if buggy_code == fixed_code:
                continue

            record = {
                "instruction": "Fix the Python code while preserving the intended behavior.",
                "input": buggy_code,
                "output": fixed_code,
                "source": "bugsinpy",
                "risk": "medium",
                "file": name,
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            count += 1

    print(f"Wrote {count} BugsInPy-style pairs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
