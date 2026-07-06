import ast
import re
from typing import Any, Dict, List

from agents.base_agent import BaseAgent
from core.database import get_migration_rules


LEGACY_RULES = [
    {
        "id": "backtick_repr",
        "pattern": re.compile(r"`[^`\n]+`"),
        "source_hint": "Python 1.x/2.x",
        "message": "Backtick repr syntax detected.",
        "replacement": "Replace `expr` with repr(expr).",
        "risk": "MEDIUM",
    },
    {
        "id": "apply_builtin",
        "pattern": re.compile(r"\bapply\s*\("),
        "source_hint": "Python 1.x/2.x",
        "message": "Legacy apply(...) builtin detected.",
        "replacement": "Rewrite apply(fn, args[, kwargs]) as fn(*args[, **kwargs]).",
        "risk": "MEDIUM",
    },
    {
        "id": "print_statement",
        "pattern": re.compile(r"^\s*print\s+[^(\n].*$", re.MULTILINE),
        "source_hint": "Python 2.x",
        "message": "Legacy print statement detected.",
        "replacement": "Wrap values with print(...).",
        "risk": "LOW",
    },
    {
        "id": "xrange_usage",
        "pattern": re.compile(r"\bxrange\s*\("),
        "source_hint": "Python 2.x",
        "message": "xrange is not available in modern Python.",
        "replacement": "Replace xrange(...) with range(...).",
        "risk": "LOW",
    },
    {
        "id": "raw_input_usage",
        "pattern": re.compile(r"\braw_input\s*\("),
        "source_hint": "Python 2.x",
        "message": "raw_input was renamed in Python 3.",
        "replacement": "Replace raw_input(...) with input(...).",
        "risk": "LOW",
    },
    {
        "id": "except_comma",
        "pattern": re.compile(r"^\s*except\s+[^:\n]+,\s*[A-Za-z_]\w*\s*:", re.MULTILINE),
        "source_hint": "Python 2.x",
        "message": "Old exception binding syntax detected.",
        "replacement": "Convert except X, e: to except X as e:.",
        "risk": "LOW",
    },
    {
        "id": "not_equal_operator",
        "pattern": re.compile(r"<>"),
        "source_hint": "Python 2.x",
        "message": "Legacy not-equal operator detected.",
        "replacement": "Replace <> with !=.",
        "risk": "LOW",
    },
    {
        "id": "iteritems_usage",
        "pattern": re.compile(r"\.iteritems\s*\("),
        "source_hint": "Python 2.x",
        "message": "iteritems returns a Python 2 iterator API.",
        "replacement": "Replace iteritems() with items().",
        "risk": "LOW",
    },
    {
        "id": "iterkeys_usage",
        "pattern": re.compile(r"\.iterkeys\s*\("),
        "source_hint": "Python 2.x",
        "message": "iterkeys returns a Python 2 iterator API.",
        "replacement": "Replace iterkeys() with keys().",
        "risk": "LOW",
    },
    {
        "id": "itervalues_usage",
        "pattern": re.compile(r"\.itervalues\s*\("),
        "source_hint": "Python 2.x",
        "message": "itervalues returns a Python 2 iterator API.",
        "replacement": "Replace itervalues() with values().",
        "risk": "LOW",
    },
    {
        "id": "has_key_usage",
        "pattern": re.compile(r"\.has_key\s*\("),
        "source_hint": "Python 2.x",
        "message": "dict.has_key was removed.",
        "replacement": "Rewrite d.has_key(x) as x in d.",
        "risk": "MEDIUM",
    },
    {
        "id": "unicode_type",
        "pattern": re.compile(r"\bunicode\b"),
        "source_hint": "Python 2.x",
        "message": "unicode type detected.",
        "replacement": "Replace unicode with str where compatible.",
        "risk": "MEDIUM",
    },
    {
        "id": "basestring_type",
        "pattern": re.compile(r"\bbasestring\b"),
        "source_hint": "Python 2.x",
        "message": "basestring type detected.",
        "replacement": "Replace basestring with str.",
        "risk": "MEDIUM",
    },
    {
        "id": "long_type",
        "pattern": re.compile(r"\blong\b"),
        "source_hint": "Python 2.x",
        "message": "long type detected.",
        "replacement": "Replace long with int.",
        "risk": "LOW",
    },
    {
        "id": "exec_statement",
        "pattern": re.compile(r"^\s*exec\s+[^(\n].*$", re.MULTILINE),
        "source_hint": "Python 1.x/2.x",
        "message": "Legacy exec statement detected.",
        "replacement": "Convert exec statement syntax to exec(...).",
        "risk": "HIGH",
    },
]


HIGH_RISK_PATTERNS = [
    {
        "id": "division_semantics",
        "pattern": re.compile(r"(?<!/)/(?!/)"),
        "message": "Division semantics may change between Python 2 and Python 3.",
        "risk": "HIGH",
    },
    {
        "id": "bytes_text_boundary",
        "pattern": re.compile(r"\b(str|unicode|bytes)\b"),
        "message": "Text/bytes handling may require manual review.",
        "risk": "MEDIUM",
    },
]


class AnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Analyzer")

    async def process(self, code: str) -> Dict[str, Any]:
        issues = self._find_legacy_issues(code)
        risks = self._find_semantic_risks(code)
        probable_version = self._infer_version(issues)
        parse_result = self._parse_python3(code)

        complexity = parse_result.get("complexity", 0)
        parseable = parse_result["parseable"]
        parse_error = parse_result.get("error")

        risk_score = "LOW"
        mode = "SAFE"
        risk_messages: List[str] = [risk["message"] for risk in risks]

        if issues:
            risk_score = "MEDIUM"
            mode = "RESTRICTED"

        if any(risk["risk"] == "HIGH" for risk in risks):
            risk_score = "HIGH"
            mode = "RESTRICTED"

        if parse_error and not issues:
            return {
                "success": False,
                "error": parse_error,
                "parseable": False,
            }

        if re.search(r"\b(eval|exec)\s*\(", code):
            risk_score = "CRITICAL"
            mode = "BLOCKED"
            risk_messages.append("Detected unsafe dynamic execution.")

        return {
            "success": True,
            "loc": len(code.splitlines()),
            "complexity": complexity,
            "risk_score": risk_score,
            "mode": mode,
            "parseable": parseable,
            "parse_error": parse_error,
            "probable_source_version": probable_version,
            "legacy_issues": issues,
            "semantic_risks": risks,
            "risks": risk_messages,
            "ast_dump": parse_result.get("ast_dump"),
        }

    def _parse_python3(self, code: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {"parseable": False, "error": str(exc)}

        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.Try)):
                complexity += 1

        return {
            "parseable": True,
            "complexity": complexity,
            "ast_dump": ast.dump(tree),
        }

    def _find_legacy_issues(self, code: str) -> List[Dict[str, Any]]:
        lines = code.splitlines()
        issues: List[Dict[str, Any]] = []

        db_rules = []
        try:
            db_rules = get_migration_rules()
        except Exception:
            pass

        rules_to_use = []
        if db_rules:
            for rule in db_rules:
                flags = 0
                if rule["id"] in ("print_statement", "except_comma", "exec_statement"):
                    flags = re.MULTILINE
                try:
                    rules_to_use.append({
                        "id": rule["id"],
                        "pattern": re.compile(rule["pattern"], flags),
                        "source_hint": rule["source_hint"],
                        "message": rule["message"],
                        "replacement": rule["replacement"],
                        "risk": rule["risk"]
                    })
                except Exception:
                    pass

        if not rules_to_use:
            rules_to_use = LEGACY_RULES

        for rule in rules_to_use:
            for match in rule["pattern"].finditer(code):
                line_number = code[: match.start()].count("\n") + 1
                preview = lines[line_number - 1].strip() if line_number - 1 < len(lines) else ""
                issues.append(
                    {
                        "id": rule["id"],
                        "line": line_number,
                        "message": rule["message"],
                        "replacement": rule["replacement"],
                        "risk": rule["risk"],
                        "source_hint": rule["source_hint"],
                        "preview": preview,
                    }
                )
        return issues

    def _find_semantic_risks(self, code: str) -> List[Dict[str, Any]]:
        risks: List[Dict[str, Any]] = []
        for rule in HIGH_RISK_PATTERNS:
            if rule["pattern"].search(code):
                risks.append(
                    {
                        "id": rule["id"],
                        "message": rule["message"],
                        "risk": rule["risk"],
                    }
                )
        return risks

    def _infer_version(self, issues: List[Dict[str, Any]]) -> str:
        if not issues:
            return "Python 3.x"

        if any(issue["source_hint"] == "Python 1.x/2.x" for issue in issues):
            return "Python 1.x / early legacy Python"

        if any(issue["source_hint"] == "Python 2.x" for issue in issues):
            return "Python 2.x / early legacy Python"

        return "Legacy Python"
