import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class MLAssetTests(unittest.TestCase):
    def test_curated_dataset_exists_and_has_examples(self):
        dataset_path = ROOT / "ml/data/modernization_train.jsonl"
        self.assertTrue(dataset_path.exists())

        with dataset_path.open(encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]

        self.assertGreater(len(rows), 50)
        self.assertTrue(all("instruction" in row and "input" in row and "output" in row for row in rows))

    def test_evaluator_script_runs(self):
        process = subprocess.run(
            [sys.executable, "ml/evaluate_modernizer.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(process.stdout)
        self.assertEqual(payload["benchmark_size"], 4)
        self.assertEqual(payload["rule_pass"], 4)


if __name__ == "__main__":
    unittest.main()
