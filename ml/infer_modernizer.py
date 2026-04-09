import argparse


BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
DEFAULT_ADAPTER_PATH = "ml/models/nebula-modernizer-qwen25-1.5b"


PROMPT_TEMPLATE = """You are Helix AI, a legacy Python modernization model.
Convert old Python code to current Python while preserving behavior.
Return only the final migrated code.

### Instruction:
Modernize this legacy Python code to current Python while preserving behavior.

### Input:
{input_code}

### Response:
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter-path", default=DEFAULT_ADAPTER_PATH)
    parser.add_argument("--code", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Missing ML dependencies. Install with `pip install -r requirements-ml.txt`."
        ) from exc

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    try:
        tokenizer = AutoTokenizer.from_pretrained(args.adapter_path)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16 if device != "cpu" else torch.float32,
    )
    model = PeftModel.from_pretrained(model, args.adapter_path)
    model.to(device)

    prompt = PROMPT_TEMPLATE.format(input_code=args.code)
    inputs = tokenizer([prompt], return_tensors="pt").to(device)
    outputs = model.generate(**inputs, max_new_tokens=args.max_new_tokens)
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(decoded.split("### Response:")[-1].strip())


if __name__ == "__main__":
    main()
