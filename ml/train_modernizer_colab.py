"""
Colab-friendly trainer wrapper.

Recommended usage on Colab:
python ml/train_modernizer_colab.py --data-path /content/training_mixture.jsonl
"""

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default="ml/data/training_mixture.jsonl")
    parser.add_argument("--output-dir", default="ml/models/nebula-modernizer-qwen25-1.5b")
    parser.add_argument("--batch-size", default="4")
    parser.add_argument("--gradient-accumulation-steps", default="2")
    parser.add_argument("--epochs", default="2")
    parser.add_argument("--learning-rate", default="2e-4")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    train_script = repo_root / "ml" / "train_modernizer_unsloth.py"
    command = [
        sys.executable,
        str(train_script),
        "--base-model",
        "unsloth/Qwen2.5-Coder-1.5B-Instruct",
        "--data-path",
        args.data_path,
        "--output-dir",
        args.output_dir,
        "--batch-size",
        args.batch_size,
        "--gradient-accumulation-steps",
        args.gradient_accumulation_steps,
        "--epochs",
        args.epochs,
        "--learning-rate",
        args.learning_rate,
    ]
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    main()
