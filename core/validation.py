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
        leftovers = [name for name, pattern in LEGACY_REMAINDER_PATTERNS.items() if pattern.search(code)]
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
