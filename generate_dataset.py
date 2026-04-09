"""
Legacy compatibility wrapper.

Use the scripts under `ml/` instead:
- `ml/build_seed_modernization_dataset.py`
- `ml/curate_dataset.py`
- `ml/train_modernizer_unsloth.py`
"""

from pathlib import Path


def main() -> None:
    print("Dataset generation moved to the `ml/` folder.")
    print("Recommended flow:")
    print("  1. python3 ml/build_seed_modernization_dataset.py")
    print("  2. python3 ml/curate_dataset.py")
    print("  3. python3 ml/train_modernizer_unsloth.py")
    print(f"Project root: {Path(__file__).resolve().parent}")


if __name__ == "__main__":
    main()
