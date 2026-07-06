import ast
import re
from typing import Dict, Any, List


LEGACY_REMAINDER_PATTERNS = {
    "backtick_repr": re.compile(r"`[^`\n]+`"),
    "apply_builtin": re.compile(r"\bapply\s*\("),
    "xrange": re.compile(r"\bxrange\s*\("),
    "raw_input": re.compile(r"\braw_input\s*\("),
    "iteritems": re.compile(r"\.iteritems\s*\("),
    "iterkeys": re.compile(r"\.iterkeys\s*\("),
    "itervalues": re.compile(r"\.itervalues\s*\("),
    "has_key": re.compile(r"\.has_key\s*\("),
    "not_equal": re.compile(r"<>"),
    "except_comma": re.compile(r"except\s+([^:\n]+),\s*([A-Za-z_]\w*)\s*:"),
    "exec_statement": re.compile(r"^\s*exec\s+[^(\n].*$", re.MULTILINE),
}


class ValidationCore:
    def detect_incomplete_input(self, code: str) -> Dict[str, Any]:
        lines = code.splitlines()
        for index in range(len(lines) - 1, -1, -1):
            stripped = lines[index].strip()
            if stripped and not stripped.startswith("#"):
                if stripped.endswith(":"):
                    return {
                        "success": False,
                        "stage": "INPUT",
                        "error": f"Input appears incomplete: line {index + 1} ends with ':' but has no block body.",
                        "warnings": [],
                        "line": index + 1,
                    }
                if stripped.endswith("\\"):
                    return {
                        "success": False,
                        "stage": "INPUT",
                        "error": f"Input appears incomplete: line {index + 1} ends with a line continuation.",
                        "warnings": [],
                        "line": index + 1,
                    }
                break

        return {"success": True, "stage": "INPUT", "warnings": []}

    def validate(self, original_code: str, new_code: str) -> Dict[str, Any]:
        warnings: List[str] = []

        try:
            ast.parse(new_code)
        except SyntaxError as exc:
            return {
                "success": False,
                "stage": "SYNTAX",
                "error": f"Syntax Error: {exc.msg} at line {exc.lineno}",
                "warnings": warnings,
            }

        lint_result = self._check_lint(new_code)
        warnings.extend(lint_result.get("warnings", []))
        if not lint_result["success"]:
            return {
                "success": False,
                "stage": "LINT",
                "error": lint_result["error"],
                "warnings": warnings,
            }

        behavior_result = self._verify_behavior(original_code, new_code)
        warnings.extend(behavior_result.get("warnings", []))
        if not behavior_result["success"]:
            return {
                "success": False,
                "stage": "BEHAVIOR",
                "error": behavior_result["error"],
                "warnings": warnings,
            }

        return {
            "success": True,
            "stage": "COMPLETE",
            "message": "Modernization validation passed.",
            "warnings": warnings,
        }

    def _check_lint(self, code: str) -> Dict[str, Any]:
        warnings: List[str] = []

        db_rules = []
        try:
            from core.database import get_migration_rules
            db_rules = get_migration_rules()
        except Exception:
            pass

        patterns_to_check = {}
        if db_rules:
            for rule in db_rules:
                flags = 0
                if rule["id"] in ("print_statement", "except_comma", "exec_statement"):
                    flags = re.MULTILINE
                try:
                    patterns_to_check[rule["id"]] = re.compile(rule["pattern"], flags)
                except Exception:
                    pass

        if not patterns_to_check:
            patterns_to_check = LEGACY_REMAINDER_PATTERNS

        leftovers = [name for name, pattern in patterns_to_check.items() if pattern.search(code)]
        if leftovers:
            return {
                "success": False,
                "error": f"Legacy constructs still remain after migration: {', '.join(leftovers)}",
                "warnings": warnings,
            }

        if re.search(r"(?<!/)/(?!/)", code):
            warnings.append("Division operators remain; review Python 2 to 3 semantics manually.")

        return {"success": True, "warnings": warnings}

    def _verify_behavior(self, original: str, new: str) -> Dict[str, Any]:
        warnings: List[str] = []
        original_functions = self._get_function_names(original)
        new_functions = self._get_function_names(new)

        missing = original_functions - new_functions
        if missing:
            return {
                "success": False,
                "error": f"Original functions disappeared during migration: {sorted(missing)}",
                "warnings": warnings,
            }

        if "unicode" in original or "basestring" in original:
            warnings.append("String type migration applied; bytes/text compatibility should be reviewed.")

        return {"success": True, "warnings": warnings}

    def _get_function_names(self, code: str) -> set:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return set()
        return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
