import json
from pathlib import Path


MANIFEST_PATH = Path("ml/public_dataset_manifest.json")
OUTPUT_PATH = Path("ml/data/training_mixture.jsonl")


def load_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    mixture = []
    for source in manifest["sources"]:
        path_value = source.get("path") or source.get("prepared_path")
        if not path_value:
            continue

        path = Path(path_value)
        if not path.exists():
            print(f"Skipping missing source: {path}")
            continue

        records = load_jsonl(path)
        weight = int(source.get("weight", 1))
        for record in records:
            enriched = dict(record)
            enriched["mixture_source"] = source["name"]
            for _ in range(max(weight, 1)):
                mixture.append(enriched)

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for record in mixture:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    print(f"Wrote {len(mixture)} training examples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
