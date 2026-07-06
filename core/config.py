import os

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Helix AI Legacy Python Modernizer"
    VERSION: str = "2.1.0"
    DEBUG_MODE: bool = True
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    ML_MODEL_ENABLED: bool = os.getenv("ML_MODEL_ENABLED", "false").lower() == "true"
    ML_MODEL_BASE: str = os.getenv("ML_MODEL_BASE", "Qwen/Qwen2.5-Coder-1.5B-Instruct")
    ML_MODEL_ADAPTER_PATH: str = os.getenv("ML_MODEL_ADAPTER_PATH", "ml/models/nebula-modernizer-qwen25-1.5b")
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TEMPLATE_DIR: str = os.path.join(BASE_DIR, "templates")
    STATIC_DIR: str = os.path.join(BASE_DIR, "static")
    RUN_HISTORY_FILE: str = os.getenv("RUN_HISTORY_FILE", os.path.join(BASE_DIR, "data", "modernization_runs.jsonl"))
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "data", "helix_ai.db"))
    MAX_INPUT_LINES: int = int(os.getenv("MAX_INPUT_LINES", "2500"))
    MAX_INPUT_CHARS: int = int(os.getenv("MAX_INPUT_CHARS", "200000"))


settings = Settings()
