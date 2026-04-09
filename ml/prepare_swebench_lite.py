import argparse
import json
from pathlib import Path


OUTPUT_PATH = Path("ml/external/swebench_lite_reasoning.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "test", "train"])
    parser.add_argument("--max-rows", type=int, default=300)
    args = parser.parse_args()

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit("Install datasets first: pip install -r requirements-ml.txt") from exc

    dataset = load_dataset("SWE-bench/SWE-bench_Lite", split=args.split)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for row in dataset:
            if count >= args.max_rows:
                break

            patch = row.get("patch", "")
            problem_statement = row.get("problem_statement", "")
            if not patch or ".py" not in patch:
                continue

            record = {
                "instruction": "Given the software issue description, generate a Python patch plan or patch-oriented response.",
                "input": problem_statement,
                "output": patch,
                "source": "swebench_lite",
                "risk": "medium",
                "repo": row.get("repo", ""),
                "instance_id": row.get("instance_id", ""),
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            count += 1

    print(f"Wrote {count} SWE-bench Lite reasoning examples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
