MODEL_PATH = "./ml/models/nebula-modernizer-qwen25-1.5b"
BASE_MODEL = "unsloth/Qwen2.5-Coder-1.5B-Instruct"


PROMPT = """You are Helix AI, a legacy Python modernization model.
Convert old Python code to current Python while preserving behavior.
Return only the final migrated code.

### Instruction:
Modernize this legacy Python code to current Python while preserving behavior.

### Input:
for i in xrange(3):
    print i

### Response:
"""


def main() -> None:
    import torch
    from transformers import TextStreamer
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_PATH,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )

    FastLanguageModel.for_inference(model)
    inputs = tokenizer([PROMPT], return_tensors="pt").to("cuda" if torch.cuda.is_available() else "cpu")
    streamer = TextStreamer(tokenizer)
    print("\n--- NEBULA MODERNIZER ---\n")
    _ = model.generate(**inputs, streamer=streamer, max_new_tokens=128)


if __name__ == "__main__":
    main()
