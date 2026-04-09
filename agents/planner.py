from typing import Any, Dict, List

from agents.base_agent import BaseAgent


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Planner")

    async def process(self, suggestions: List[Dict[str, Any]], critiques: Dict[str, Any]) -> Dict[str, Any]:
        critique_map = {item["suggestion_id"]: item for item in critiques["critiques"]}
        candidates = []

        for suggestion in suggestions:
            critique = critique_map.get(suggestion["id"])
            if not critique:
                continue
            if critique["status"] not in {"APPROVED", "WARNING"}:
                continue

            final_score = critique["safety_score"] + max(0, 50 - suggestion.get("priority", 50))
            candidates.append(
                {
                    "suggestion": suggestion,
                    "critique": critique,
                    "safety_score": final_score,
                    "execution_order": suggestion.get("priority", 50),
                }
            )

        candidates.sort(key=lambda item: (item["execution_order"], -item["safety_score"], item["suggestion"]["line"]))
        selected_plans = [item for item in candidates if item["suggestion"]["type"] != "NOOP"]

        return {
            "selected_plan": selected_plans[0] if selected_plans else None,
            "selected_plans": selected_plans,
            "total_candidates": len(suggestions),
            "approved_count": len(selected_plans),
            "candidates": candidates,
        }
