# ML Fine-Tuning Workflow

This folder now contains a stronger training strategy for the actual project goal: legacy Python modernization with agent-assisted reasoning.

## Recommended training strategy

Use a 3-stage pipeline instead of one small fine-tune:

1. Domain adaptation on Python code
2. Supervised fine-tuning on legacy-modernization pairs
3. Optional issue/patch reasoning fine-tuning for the planner/critic layer

## Recommended public data sources

### Stage 1: Python code domain adaptation

- `bigcode/the-stack` or `bigcode/the-stack-dedup` Python subset
  Source: [The Stack dataset card](https://huggingface.co/datasets/bigcode/the-stack)
  Purpose: continued pretraining / domain adaptation on Python code
  Note: access requires accepting the dataset terms and license obligations

### Stage 2: modernization and repair pairs

- Local curated modernization pairs
  File: [ml/data/modernization_train.jsonl](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/data/modernization_train.jsonl)
  Purpose: direct old-to-modern Python code transformation

- QuixBugs
  Source: [jkoppel/QuixBugs](https://github.com/jkoppel/QuixBugs)
  Purpose: buggy/correct Python program pairs for low-level repair behavior

- BugsInPy
  Source: [soarsmu/BugsInPy](https://github.com/soarsmu/BugsInPy)
  Purpose: real Python bug-fix instances and reproducible debugging data

- GumTree Python diff datasets
  Source: [GumTreeDiff/datasets](https://github.com/GumTreeDiff/datasets)
  Purpose: before/after Python file pairs mined from real commits

- PyBugHive
  Source: [PyBugHive](https://pybughive.github.io/)
  Purpose: manually validated reproducible Python bugs for evaluation and targeted data collection

### Stage 3: issue-to-patch reasoning

- SWE-bench Lite / SWE-bench Verified
  Sources:
  - [SWE-bench dataset card](https://huggingface.co/datasets/SWE-bench/SWE-bench)
  - [SWE-bench Lite dataset card](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite)
  - [Official SWE-bench dataset guide](https://www.swebench.com/SWE-bench/guides/datasets/)
  Purpose: improve planner/critic reasoning over issue descriptions, patches, and test constraints

## Why this is better than the old setup

- the previous training data mixed generic clean-code refactoring with modernization tasks
- it contained noisy nested records and mismatched input/output pairs
- it was too small and too broad for your actual project goal

The new approach separates:
- code-domain adaptation
- direct modernization learning
- software-engineering reasoning

## Files in this folder

- [build_seed_modernization_dataset.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/build_seed_modernization_dataset.py)
- [curate_dataset.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/curate_dataset.py)
- [public_dataset_manifest.json](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/public_dataset_manifest.json)
- [prepare_quixbugs_pairs.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/prepare_quixbugs_pairs.py)
- [prepare_swebench_lite.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/prepare_swebench_lite.py)
- [build_training_mixture.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/build_training_mixture.py)
- [train_modernizer_unsloth.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/train_modernizer_unsloth.py)
- [infer_modernizer.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/infer_modernizer.py)

## Practical workflow

1. Build the local seed set:

```bash
python3 ml/build_seed_modernization_dataset.py
```

2. Curate the existing local dataset:

```bash
python3 ml/curate_dataset.py
```

3. Optionally prepare external sources:

```bash
python3 ml/prepare_quixbugs_pairs.py --repo-path /path/to/QuixBugs
python3 ml/prepare_swebench_lite.py --split dev
```

4. Build the final mixture:

```bash
python3 ml/build_training_mixture.py
```

5. Train locally or on Colab:

```bash
pip install -r requirements-ml.txt
python3 ml/train_modernizer_unsloth.py --data-path ml/data/training_mixture.jsonl
```

For the best practical route, use Google Colab and the assets in:

- [ml/COLAB_TRAINING.md](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/COLAB_TRAINING.md)
- [ml/Helix_AI_Modernizer_Colab.ipynb](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/Helix_AI_Modernizer_Colab.ipynb)

Recommended Colab base model:

- `unsloth/Qwen2.5-Coder-1.5B-Instruct`

## Notes

- The strongest architecture for this project is still hybrid:
  - deterministic migration rules for safe rewrites
  - ML model for ranking, ambiguity resolution, and fallback modernization
- Use The Stack primarily for domain adaptation, not as direct old->new supervision.
- Use SWE-bench primarily for planner/critic reasoning, not as direct snippet modernization supervision.
