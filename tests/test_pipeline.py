import asyncio
import unittest

from agents.analyzer import AnalyzerAgent
from agents.critic import CriticAgent
from agents.planner import PlannerAgent
from agents.suggester import SuggestionAgent
from core.execution import ExecutionCore
from core.validation import ValidationCore


LEGACY_SAMPLE = """def legacy_scan(values):
    print "starting migration"
    for i in xrange(len(values)):
        if values.has_key(i):
            print values[i]
    return raw_input("done? ")
"""

VERY_OLD_SAMPLE = """def legacy_formatter(value, args):
    print `value`
    return apply(str, args)
"""


class PipelineTests(unittest.TestCase):
    def test_analyzer_detects_legacy_python_patterns(self):
        analysis = asyncio.run(AnalyzerAgent().process(LEGACY_SAMPLE))

        self.assertTrue(analysis["success"])
        self.assertEqual(analysis["probable_source_version"], "Python 2.x / early legacy Python")
        self.assertGreaterEqual(len(analysis["legacy_issues"]), 4)
        issue_ids = {issue["id"] for issue in analysis["legacy_issues"]}
        self.assertIn("print_statement", issue_ids)
        self.assertIn("xrange_usage", issue_ids)
        self.assertIn("has_key_usage", issue_ids)
        self.assertIn("raw_input_usage", issue_ids)

    def test_pipeline_modernizes_legacy_code(self):
        analyzer = AnalyzerAgent()
        suggester = SuggestionAgent()
        critic = CriticAgent()
        planner = PlannerAgent()
        executor = ExecutionCore()
        validator = ValidationCore()

        analysis = asyncio.run(analyzer.process(LEGACY_SAMPLE))
        suggestions = asyncio.run(suggester.process(analysis, LEGACY_SAMPLE))
        critiques = asyncio.run(critic.process(suggestions))
        plan = asyncio.run(planner.process(suggestions, critiques))

        modernized = executor.apply_changes(LEGACY_SAMPLE, plan["selected_plans"])
        validation = validator.validate(LEGACY_SAMPLE, modernized)

        self.assertIn("print(\"starting migration\")", modernized)
        self.assertIn("range(len(values))", modernized)
        self.assertIn("i in values", modernized)
        self.assertIn("input(\"done? \")", modernized)
        self.assertTrue(validation["success"])

    def test_validation_rejects_leftover_legacy_constructs(self):
        validator = ValidationCore()
        result = validator.validate(
            "for i in xrange(3):\n    print i\n",
            "for i in xrange(3):\n    print(i)\n",
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["stage"], "LINT")
        self.assertIn("xrange", result["error"])

    def test_validation_detects_incomplete_trailing_block(self):
        validator = ValidationCore()
        result = validator.detect_incomplete_input("for i in xrange(3):\n")

        self.assertFalse(result["success"])
        self.assertEqual(result["stage"], "INPUT")
        self.assertIn("incomplete", result["error"])

    def test_pipeline_handles_very_old_legacy_patterns(self):
        analyzer = AnalyzerAgent()
        suggester = SuggestionAgent()
        critic = CriticAgent()
        planner = PlannerAgent()
        executor = ExecutionCore()
        validator = ValidationCore()

        analysis = asyncio.run(analyzer.process(VERY_OLD_SAMPLE))
        self.assertTrue(analysis["success"])
        self.assertEqual(analysis["probable_source_version"], "Python 1.x / early legacy Python")
        issue_ids = {issue["id"] for issue in analysis["legacy_issues"]}
        self.assertIn("backtick_repr", issue_ids)
        self.assertIn("apply_builtin", issue_ids)

        suggestions = asyncio.run(suggester.process(analysis, VERY_OLD_SAMPLE))
        critiques = asyncio.run(critic.process(suggestions))
        plan = asyncio.run(planner.process(suggestions, critiques))

        modernized = executor.apply_changes(VERY_OLD_SAMPLE, plan["selected_plans"])
        validation = validator.validate(VERY_OLD_SAMPLE, modernized)

        self.assertIn("print(repr(value))", modernized)
        self.assertIn("str(*args)", modernized)
        self.assertTrue(validation["success"])


if __name__ == "__main__":
    unittest.main()
