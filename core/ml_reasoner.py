import importlib.util
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


PROMPT_TEMPLATE = """You are Helix AI, a legacy Python modernization model.
Convert old Python code to current Python while preserving behavior.
Return only the final migrated code.

### Instruction:
Modernize this legacy Python code to current Python while preserving behavior.

### Input:
{input_code}

### Response:
"""

PROMPT_TEMPLATE_WITH_EXAMPLES = """You are Helix AI, a legacy Python modernization model.
Convert old Python code to current Python while preserving behavior.
Return only the final migrated code.

Here are some examples of successful migrations:
{examples_text}

### Instruction:
Modernize this legacy Python code to current Python while preserving behavior.

### Input:
{input_code}

### Response:
"""


@dataclass
class MLInferenceResult:
    enabled: bool
    available: bool
    output: str = ""
    error: str = ""
    model_path: str = ""


class MLReasoner:
    def __init__(self, enabled: bool, adapter_path: str, base_model: str):
        self.enabled = enabled
        self.adapter_path = adapter_path
        self.base_model = base_model
        self._model = None
        self._tokenizer = None
        self._device = "cpu"
        self._load_error: Optional[str] = None

    def is_available(self) -> bool:
        return self.enabled and self._readiness_error() is None

    def explain_status(self) -> dict:
        readiness_error = self._readiness_error() if self.enabled else None
        return {
            "enabled": self.enabled,
            "available": self.enabled and readiness_error is None,
            "model_path": self.adapter_path,
            "adapter_exists": self._adapter_exists(),
            "device": self._device,
            "loaded": self._model is not None and self._tokenizer is not None,
            "error": self._load_error or readiness_error,
        }

    def modernize(self, code: str, max_new_tokens: int = 256, few_shot_examples: List[Dict[str, Any]] = None) -> MLInferenceResult:
        if not self.enabled:
            return MLInferenceResult(enabled=False, available=False, error="ML model is disabled.")
        readiness_error = self._readiness_error()
        if readiness_error:
            return MLInferenceResult(
                enabled=True,
                available=False,
                error=readiness_error,
                model_path=self.adapter_path,
            )

        try:
            self._ensure_loaded()
            if few_shot_examples:
                examples_texts = []
                for i, ex in enumerate(few_shot_examples, 1):
                    examples_texts.append(
                        f"Example {i}:\n### Input:\n{ex['input_code']}\n### Response:\n{ex['output_code']}"
                    )
                examples_text = "\n\n".join(examples_texts)
                prompt = PROMPT_TEMPLATE_WITH_EXAMPLES.format(examples_text=examples_text, input_code=code)
            else:
                prompt = PROMPT_TEMPLATE.format(input_code=code)

            inputs = self._tokenizer([prompt], return_tensors="pt").to(self._device)
            outputs = self._model.generate(**inputs, max_new_tokens=max_new_tokens)
            decoded = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            final_output = self._clean_generated_code(decoded.split("### Response:")[-1])
            return MLInferenceResult(
                enabled=True,
                available=True,
                output=final_output,
                model_path=self.adapter_path,
            )
        except Exception as exc:
            self._load_error = str(exc)
            return MLInferenceResult(
                enabled=True,
                available=False,
                error=str(exc),
                model_path=self.adapter_path,
            )

    def _adapter_exists(self) -> bool:
        return bool(self.adapter_path) and os.path.exists(self.adapter_path)

    def _dependency_error(self) -> Optional[str]:
        missing = [
            package
            for package in ("torch", "peft", "transformers")
            if importlib.util.find_spec(package) is None
        ]
        if missing:
            return f"ML dependencies are missing: {', '.join(missing)}. Install requirements-ml.txt."
        return None

    def _readiness_error(self) -> Optional[str]:
        if not self._adapter_exists():
            return "Adapter path is missing or not trained yet."
        return self._dependency_error()

    def _clean_generated_code(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        for marker in (
            "\n```",
            "\n### Instruction:",
            "\n### Input:",
            "\n### Response:",
            "\n<|fim_middle|>",
            "\n<|im_end|>",
            "\n\\end{document}",
            "\n'''",
            '\n"""',
            "\n# Example",
        ):
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0]
        return cleaned.strip()

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return

        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("ML dependencies are missing. Install requirements-ml.txt.") from exc

        # Use CUDA if available, otherwise fall back to CPU.
        # MPS (Apple Metal) is intentionally skipped because the Qwen2.5-Coder
        # model requires ~11.8 GB of contiguous GPU memory, which exceeds the
        # Metal buffer allocation limit on most Apple Silicon Macs.
        if torch.cuda.is_available():
            self._device = "cuda"
        else:
            self._device = "cpu"

        try:
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(self.adapter_path)
            except Exception:
                self._tokenizer = AutoTokenizer.from_pretrained(self.base_model)
            model = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
            )
            self._model = PeftModel.from_pretrained(model, self.adapter_path)
            self._model.to(self._device)
        except Exception as exc:
            self._load_error = f"Model loading failed: {exc}"
            self._model = None
            self._tokenizer = None
            raise RuntimeError(self._load_error) from exc
