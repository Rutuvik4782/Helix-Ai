from typing import Any, Dict, List

from agents.base_agent import BaseAgent


TYPE_BASE_SCORE = {
    "SYNTAX_UPGRADE": 98,
    "API_UPGRADE": 94,
    "TYPE_UPGRADE": 88,
    "SEMANTIC_UPGRADE": 82,
    "NOOP": 100,
}


class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__("Critic")

    async def process(self, suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        critique_results = []

        for suggestion in suggestions:
            score = TYPE_BASE_SCORE.get(suggestion["type"], 75)
            status = "APPROVED"
            reasons = []

            if suggestion["type"] == "NOOP":
                reasons.append("No migration action needed.")
            if suggestion["type"] == "SEMANTIC_UPGRADE":
                status = "WARNING"
                score -= 10
                reasons.append("Semantic rewrite requires careful validation.")
            if suggestion["type"] == "TYPE_UPGRADE":
                status = "WARNING"
                score -= 5
                reasons.append("Type migration may affect string/bytes behavior.")
            if suggestion["confidence"] < 0.9:
                status = "WARNING"
                score -= 5
                reasons.append("Confidence is below strict auto-apply threshold.")

            critique_results.append(
                {
                    "suggestion_id": suggestion["id"],
                    "status": status,
                    "safety_score": max(score, 0),
                    "reasons": reasons,
                }
            )

        return {"critiques": critique_results}
