import argparse
import json
from pathlib import Path


OUTPUT_PATH = Path("ml/external/quixbugs_pairs.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True, help="Path to a local clone of jkoppel/QuixBugs")
    args = parser.parse_args()

    repo_path = Path(args.repo_path)
    buggy_dir = repo_path / "python_programs"
    fixed_dir = repo_path / "correct_python_programs"

    if not buggy_dir.exists() or not fixed_dir.exists():
        raise SystemExit("Expected QuixBugs python_programs/ and correct_python_programs/ directories.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for buggy_file in sorted(buggy_dir.glob("*.py")):
            fixed_file = fixed_dir / buggy_file.name
            if not fixed_file.exists():
                continue

            record = {
                "instruction": "Fix the Python code while preserving the original intent.",
                "input": buggy_file.read_text(encoding="utf-8"),
                "output": fixed_file.read_text(encoding="utf-8"),
                "source": "quixbugs",
                "risk": "low",
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            count += 1

    print(f"Wrote {count} QuixBugs pairs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
