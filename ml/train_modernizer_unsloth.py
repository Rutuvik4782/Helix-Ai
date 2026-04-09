import argparse
import json
from pathlib import Path


DEFAULT_BASE_MODEL = "unsloth/Qwen2.5-Coder-1.5B-Instruct"
DEFAULT_DATA_PATH = Path("ml/data/modernization_train.jsonl")
DEFAULT_OUTPUT_DIR = Path("ml/models/nebula-modernizer-qwen25-1.5b")
MAX_SEQ_LENGTH = 2048


PROMPT_TEMPLATE = """You are Helix AI, a legacy Python modernization model.
Convert old Python code to current Python while preserving behavior.
Return only the final migrated code.

### Instruction:
{instruction}

### Input:
{input_code}

### Response:
{output_code}"""


def load_records() -> list[dict]:
    records = []
    with DATA_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def formatting_prompts_func(examples):
    texts = []
    for instruction, input_code, output_code in zip(
        examples["instruction"],
        examples["input"],
        examples["output"],
    ):
        texts.append(
            PROMPT_TEMPLATE.format(
                instruction=instruction,
                input_code=input_code,
                output_code=output_code,
            )
        )
    return {"text": texts}


def main() -> None:
    try:
        from datasets import Dataset
        from trl import SFTConfig, SFTTrainer
        from unsloth import FastLanguageModel
    except ImportError as exc:
        raise SystemExit(
            "Missing ML dependencies. Install with `pip install -r requirements-ml.txt`."
        ) from exc

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--data-path", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    args = parser.parse_args()

    data_path = Path(args.data_path)
    output_dir = Path(args.output_dir)

    if not data_path.exists():
        raise SystemExit(
            f"Training data not found at {data_path}. Run `python3 ml/build_seed_modernization_dataset.py` "
            f"and `python3 ml/curate_dataset.py` first."
        )

    global DATA_PATH
    DATA_PATH = data_path
    raw_records = load_records()
    dataset = Dataset.from_list(raw_records)
    dataset = dataset.shuffle(seed=42)
    dataset = dataset.map(formatting_prompts_func, batched=True)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=SFTConfig(
            output_dir=str(output_dir),
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            learning_rate=args.learning_rate,
            num_train_epochs=args.epochs,
            warmup_ratio=0.05,
            logging_steps=5,
            save_strategy="epoch",
            lr_scheduler_type="cosine",
            weight_decay=0.01,
            report_to=[],
        ),
    )

    trainer.train()
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    print(f"Saved adapter to {output_dir}")


if __name__ == "__main__":
    main()
