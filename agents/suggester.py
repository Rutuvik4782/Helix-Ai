from typing import Any, Dict, List

from agents.base_agent import BaseAgent


ISSUE_TO_SUGGESTION = {
    "backtick_repr": {
        "id": "upgrade_backtick_repr",
        "type": "SEMANTIC_UPGRADE",
        "target": "backtick repr",
        "suggestion": "repr_call",
        "reasoning": "Backticks were an old repr shorthand and should become repr(...).",
        "confidence": 0.9,
        "priority": 12,
    },
    "apply_builtin": {
        "id": "upgrade_apply_builtin",
        "type": "SEMANTIC_UPGRADE",
        "target": "apply builtin",
        "suggestion": "star_call",
        "reasoning": "apply(fn, args[, kwargs]) is now expressed as fn(*args[, **kwargs]).",
        "confidence": 0.9,
        "priority": 18,
    },
    "print_statement": {
        "id": "upgrade_print_statement",
        "type": "SYNTAX_UPGRADE",
        "target": "print statement",
        "suggestion": "print_function",
        "reasoning": "Convert legacy print statements to Python 3 print(...) calls.",
        "confidence": 0.98,
        "priority": 10,
    },
    "xrange_usage": {
        "id": "upgrade_xrange",
        "type": "API_UPGRADE",
        "target": "xrange",
        "suggestion": "range",
        "reasoning": "xrange was removed; range provides the modern equivalent.",
        "confidence": 0.99,
        "priority": 20,
    },
    "raw_input_usage": {
        "id": "upgrade_raw_input",
        "type": "API_UPGRADE",
        "target": "raw_input",
        "suggestion": "input",
        "reasoning": "raw_input was renamed to input in Python 3.",
        "confidence": 0.99,
        "priority": 20,
    },
    "except_comma": {
        "id": "upgrade_except_syntax",
        "type": "SYNTAX_UPGRADE",
        "target": "except syntax",
        "suggestion": "except_as",
        "reasoning": "Modern Python binds exceptions with `as`.",
        "confidence": 0.97,
        "priority": 15,
    },
    "not_equal_operator": {
        "id": "upgrade_not_equal",
        "type": "SYNTAX_UPGRADE",
        "target": "<>",
        "suggestion": "!=",
        "reasoning": "The <> operator is obsolete.",
        "confidence": 1.0,
        "priority": 10,
    },
    "iteritems_usage": {
        "id": "upgrade_iteritems",
        "type": "API_UPGRADE",
        "target": "iteritems",
        "suggestion": "items",
        "reasoning": "Use items() for modern dictionary iteration.",
        "confidence": 0.98,
        "priority": 25,
    },
    "iterkeys_usage": {
        "id": "upgrade_iterkeys",
        "type": "API_UPGRADE",
        "target": "iterkeys",
        "suggestion": "keys",
        "reasoning": "Use keys() for modern dictionary iteration.",
        "confidence": 0.98,
        "priority": 25,
    },
    "itervalues_usage": {
        "id": "upgrade_itervalues",
        "type": "API_UPGRADE",
        "target": "itervalues",
        "suggestion": "values",
        "reasoning": "Use values() for modern dictionary iteration.",
        "confidence": 0.98,
        "priority": 25,
    },
    "has_key_usage": {
        "id": "upgrade_has_key",
        "type": "SEMANTIC_UPGRADE",
        "target": "has_key",
        "suggestion": "in_operator",
        "reasoning": "Replace deprecated has_key checks with membership tests.",
        "confidence": 0.92,
        "priority": 30,
    },
    "unicode_type": {
        "id": "upgrade_unicode",
        "type": "TYPE_UPGRADE",
        "target": "unicode",
        "suggestion": "str",
        "reasoning": "Python 3 uses str for text values.",
        "confidence": 0.88,
        "priority": 35,
    },
    "basestring_type": {
        "id": "upgrade_basestring",
        "type": "TYPE_UPGRADE",
        "target": "basestring",
        "suggestion": "str",
        "reasoning": "basestring no longer exists in Python 3.",
        "confidence": 0.9,
        "priority": 35,
    },
    "long_type": {
        "id": "upgrade_long",
        "type": "TYPE_UPGRADE",
        "target": "long",
        "suggestion": "int",
        "reasoning": "int subsumes long in modern Python.",
        "confidence": 0.96,
        "priority": 35,
    },
    "exec_statement": {
        "id": "upgrade_exec_statement",
        "type": "SEMANTIC_UPGRADE",
        "target": "exec statement",
        "suggestion": "exec_function",
        "reasoning": "Modern Python uses exec(...) function-style syntax.",
        "confidence": 0.86,
        "priority": 22,
    },
    "octal_literals": {
        "id": "upgrade_octal_literals",
        "type": "SYNTAX_UPGRADE",
        "target": "octal literals",
        "suggestion": "octal_format",
        "reasoning": "Convert legacy octal syntax to Python 3 (0755 to 0o755).",
        "confidence": 0.98,
        "priority": 11,
    },
    "reduce_usage": {
        "id": "upgrade_reduce",
        "type": "API_UPGRADE",
        "target": "reduce builtin",
        "suggestion": "functools_reduce",
        "reasoning": "reduce() is no longer a builtin, import from functools.",
        "confidence": 0.99,
        "priority": 21,
    },
    "reload_usage": {
        "id": "upgrade_reload",
        "type": "API_UPGRADE",
        "target": "reload builtin",
        "suggestion": "importlib_reload",
        "reasoning": "reload() is no longer a builtin, import from importlib.",
        "confidence": 0.99,
        "priority": 21,
    },
    "urllib2_usage": {
        "id": "upgrade_urllib2",
        "type": "API_UPGRADE",
        "target": "urllib2 import",
        "suggestion": "urllib_request",
        "reasoning": "urllib2 module is removed in Python 3, replace with urllib.request.",
        "confidence": 0.95,
        "priority": 22,
    },
}


class SuggestionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Suggester")

    async def process(self, analysis_result: Dict[str, Any], code: str) -> List[Dict[str, Any]]:
        if not analysis_result.get("success"):
            return []

        suggestions: List[Dict[str, Any]] = []
        for issue in analysis_result.get("legacy_issues", []):
            base = ISSUE_TO_SUGGESTION.get(issue["id"])
            if not base:
                continue

            suggestion = dict(base)
            suggestion.update(
                {
                    "line": issue["line"],
                    "preview": issue["preview"],
                    "risk": issue["risk"],
                    "source_hint": issue["source_hint"],
                    "before": issue["preview"],
                    "after_hint": issue["replacement"],
                }
            )
            suggestions.append(suggestion)

        # Provide at least one actionable path for already-modern code.
        if not suggestions:
            suggestions.append(
                {
                    "id": "no_migration_needed",
                    "type": "NOOP",
                    "target": "codebase",
                    "suggestion": "already_modern",
                    "reasoning": "No high-confidence legacy Python patterns were detected.",
                    "confidence": 0.95,
                    "priority": 100,
                    "line": 1,
                    "preview": code.splitlines()[0] if code.splitlines() else "",
                    "risk": "LOW",
                    "source_hint": "Python 3.x",
                    "before": "",
                    "after_hint": "No migration changes required.",
                }
            )

        return suggestions
