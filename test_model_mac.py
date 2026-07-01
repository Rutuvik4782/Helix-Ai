BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
ADAPTER_PATH = "./ml/models/nebula-modernizer-qwen25-1.5b"

PROMPT = """You are Helix AI, a legacy Python modernization model.
Convert old Python code to current Python while preserving behavior.
Return only the final migrated code.

### Instruction:
Modernize this legacy Python code to current Python while preserving behavior.

### Input:
name = raw_input("Name: ")
print name

### Response:
"""


def main() -> None:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

    print("Loading tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")

    print("Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        dtype=torch.float32 if device == "cpu" else torch.float16,
    )

    print("Applying trained adapters...")
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    model.to(device)

    inputs = tokenizer([PROMPT], return_tensors="pt").to(device)
    streamer = TextStreamer(tokenizer)
    print("\n--- NEBULA MODERNIZER ---\n")
    _ = model.generate(**inputs, streamer=streamer, max_new_tokens=128)


if __name__ == "__main__":
    main()
