from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        pass
