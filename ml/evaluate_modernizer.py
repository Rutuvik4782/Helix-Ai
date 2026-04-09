import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.analyzer import AnalyzerAgent
from agents.critic import CriticAgent
from agents.planner import PlannerAgent
from agents.suggester import SuggestionAgent
from core.execution import ExecutionCore
from core.ml_reasoner import MLReasoner
from core.validation import ValidationCore


DEFAULT_BENCHMARK = Path("ml/data/eval_benchmark.jsonl")


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


async def run_rule_pipeline(code: str) -> dict:
    analysis = await AnalyzerAgent().process(code)
    suggestions = await SuggestionAgent().process(analysis, code)
    critiques = await CriticAgent().process(suggestions)
    plan = await PlannerAgent().process(suggestions, critiques)
    output = ExecutionCore().apply_changes(code, plan.get("selected_plans", []))
    validation = ValidationCore().validate(code, output)
    return {"analysis": analysis, "plan": plan, "output": output, "validation": validation}


def contains_all(text: str, expected: list[str]) -> bool:
    return all(item in text for item in expected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--enable-ml", action="store_true")
    parser.add_argument("--adapter-path", default="ml/models/nebula-modernizer-qwen25-1.5b")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    args = parser.parse_args()

    benchmark = load_jsonl(Path(args.benchmark))
    reasoner = MLReasoner(args.enable_ml, args.adapter_path, args.base_model)

    rule_pass = 0
    ml_pass = 0
    rows = []
    for item in benchmark:
        rule_result = asyncio.run(run_rule_pipeline(item["input"]))
        rule_ok = rule_result["validation"]["success"] and contains_all(rule_result["output"], item["expected_contains"])
        if rule_ok:
            rule_pass += 1

        ml_ok = False
        ml_output = ""
        if args.enable_ml:
            ml_result = reasoner.modernize(item["input"])
            ml_output = ml_result.output
            ml_ok = ml_result.available and contains_all(ml_output, item["expected_contains"])
            if ml_ok:
                ml_pass += 1

        rows.append(
            {
                "name": item["name"],
                "rule_ok": rule_ok,
                "rule_validation": rule_result["validation"]["success"],
                "ml_ok": ml_ok,
                "rule_output": rule_result["output"],
                "ml_output": ml_output,
            }
        )

    print(json.dumps(
        {
            "benchmark_size": len(benchmark),
            "rule_pass": rule_pass,
            "ml_pass": ml_pass if args.enable_ml else None,
            "details": rows,
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
