import argparse
import json
from pathlib import Path


OUTPUT_PATH = Path("ml/external/gumtree_python_pairs.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before-root", required=True, help="Path containing pre-change Python files")
    parser.add_argument("--after-root", required=True, help="Path containing post-change Python files")
    args = parser.parse_args()

    before_root = Path(args.before_root)
    after_root = Path(args.after_root)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for before_path in before_root.rglob("*.py"):
            relative = before_path.relative_to(before_root)
            after_path = after_root / relative
            if not after_path.exists():
                continue

            before_code = before_path.read_text(encoding="utf-8", errors="ignore")
            after_code = after_path.read_text(encoding="utf-8", errors="ignore")
            if before_code == after_code:
                continue

            record = {
                "instruction": "Transform the earlier Python file into the corrected later version.",
                "input": before_code,
                "output": after_code,
                "source": "gumtree_python",
                "risk": "medium",
                "file": str(relative),
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            count += 1

    print(f"Wrote {count} GumTree-style Python pairs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
