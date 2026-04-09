# Google Colab Training Plan

For this project, Google Colab is the best place to train the ML model because the local Mac environment does not expose CUDA or MPS for efficient fine-tuning.

## Recommended model

- Base model: `unsloth/Qwen2.5-Coder-1.5B-Instruct`

Reason:
- strong enough for code modernization tasks
- much more realistic for Colab than 7B
- integrates cleanly with the current app through `ML_MODEL_BASE`

## Files to use

- Training data: [ml/data/training_mixture.jsonl](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/data/training_mixture.jsonl)
- Trainer: [ml/train_modernizer_colab.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/train_modernizer_colab.py)
- Notebook: [ml/Helix_AI_Modernizer_Colab.ipynb](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/Helix_AI_Modernizer_Colab.ipynb)
- Adapter packager: [ml/package_adapter.py](/Users/rutwikbhondave/Desktop/Helix%20AI%20Project/ml/package_adapter.py)

## Recommended Colab runtime

- GPU runtime
- T4 is acceptable
- L4 is better if available

## High-level steps

1. Upload `training_mixture.jsonl` to Colab
2. Run the notebook
3. Download the generated adapter zip
4. Place the extracted adapter in:

```bash
ml/models/nebula-modernizer-qwen25-1.5b
```

5. Enable model-assisted runtime:

```bash
export ML_MODEL_ENABLED=true
export ML_MODEL_BASE=Qwen/Qwen2.5-Coder-1.5B-Instruct
export ML_MODEL_ADAPTER_PATH=ml/models/nebula-modernizer-qwen25-1.5b
python -m uvicorn main:app --reload
```

## After training

Run:

```bash
python3 ml/evaluate_modernizer.py --enable-ml --adapter-path ml/models/nebula-modernizer-qwen25-1.5b --base-model Qwen/Qwen2.5-Coder-1.5B-Instruct
```
