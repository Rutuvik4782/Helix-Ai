import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter-dir", default="ml/models/nebula-modernizer-qwen25-1.5b")
    parser.add_argument("--output-prefix", default="nebula-modernizer-qwen25-1.5b")
    args = parser.parse_args()

    adapter_dir = Path(args.adapter_dir)
    if not adapter_dir.exists():
        raise SystemExit(f"Adapter directory not found: {adapter_dir}")

    archive_path = shutil.make_archive(args.output_prefix, "zip", root_dir=str(adapter_dir))
    print(f"Created adapter archive: {archive_path}")


if __name__ == "__main__":
    main()
