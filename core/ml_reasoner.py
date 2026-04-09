import os
from dataclasses import dataclass
from typing import Optional


PROMPT_TEMPLATE = """You are Helix AI, a legacy Python modernization model.
Convert old Python code to current Python while preserving behavior.
Return only the final migrated code.

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
        return self.enabled and bool(self.adapter_path) and os.path.exists(self.adapter_path)

    def explain_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "available": self.is_available(),
            "model_path": self.adapter_path,
            "error": self._load_error,
        }

    def modernize(self, code: str, max_new_tokens: int = 256) -> MLInferenceResult:
        if not self.enabled:
            return MLInferenceResult(enabled=False, available=False, error="ML model is disabled.")
        if not self.is_available():
            return MLInferenceResult(
                enabled=True,
                available=False,
                error="Adapter path is missing or not trained yet.",
                model_path=self.adapter_path,
            )

        try:
            self._ensure_loaded()
            prompt = PROMPT_TEMPLATE.format(input_code=code)
            inputs = self._tokenizer([prompt], return_tensors="pt").to(self._device)
            outputs = self._model.generate(**inputs, max_new_tokens=max_new_tokens)
            decoded = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            final_output = decoded.split("### Response:")[-1].strip()
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

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return

        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("ML dependencies are missing. Install requirements-ml.txt.") from exc

        self._device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.adapter_path)
        except Exception:
            self._tokenizer = AutoTokenizer.from_pretrained(self.base_model)
        model = AutoModelForCausalLM.from_pretrained(
            self.base_model,
            torch_dtype=torch.float16 if self._device != "cpu" else torch.float32,
        )
        self._model = PeftModel.from_pretrained(model, self.adapter_path)
        self._model.to(self._device)
