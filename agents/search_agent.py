from typing import Any, Dict, List
from agents.base_agent import BaseAgent
from core.database import search_knowledge_base

class SearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("SearchAgent")

    async def process(self, pattern_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve relevant few-shot modernization examples from the database."""
        return search_knowledge_base(pattern_ids, limit=3)
