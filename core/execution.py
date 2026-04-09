import re
from typing import List


class ExecutionCore:
    def apply_changes(self, code: str, plans) -> str:
        if not plans:
            return code

        if isinstance(plans, dict):
            plans = [plans]

        candidate = code
        for plan in plans:
            candidate = self._apply_single(candidate, plan["suggestion"] if "suggestion" in plan else plan)
        return candidate

    def _apply_single(self, code: str, suggestion: dict) -> str:
        op = suggestion["id"]

        if op == "upgrade_print_statement":
            return self._upgrade_print_statements(code)
        if op == "upgrade_backtick_repr":
            return self._upgrade_backtick_repr(code)
        if op == "upgrade_apply_builtin":
            return self._upgrade_apply_builtin(code)
        if op == "upgrade_xrange":
            return re.sub(r"\bxrange(?=\s*\()", "range", code)
        if op == "upgrade_raw_input":
            return re.sub(r"\braw_input(?=\s*\()", "input", code)
        if op == "upgrade_except_syntax":
            return re.sub(r"except\s+([^:\n]+),\s*([A-Za-z_]\w*)\s*:", r"except \1 as \2:", code)
        if op == "upgrade_exec_statement":
            return self._upgrade_exec_statement(code)
        if op == "upgrade_not_equal":
            return code.replace("<>", "!=")
        if op == "upgrade_iteritems":
            return re.sub(r"\.iteritems(?=\s*\()", ".items", code)
        if op == "upgrade_iterkeys":
            return re.sub(r"\.iterkeys(?=\s*\()", ".keys", code)
        if op == "upgrade_itervalues":
            return re.sub(r"\.itervalues(?=\s*\()", ".values", code)
        if op == "upgrade_has_key":
            return re.sub(r"([A-Za-z_][\w\.]*)\.has_key\(([^)]+)\)", r"\2 in \1", code)
        if op == "upgrade_unicode":
            return re.sub(r"\bunicode\b", "str", code)
        if op == "upgrade_basestring":
            return re.sub(r"\bbasestring\b", "str", code)
        if op == "upgrade_long":
            return re.sub(r"\blong\b", "int", code)
        return code

    def _upgrade_print_statements(self, code: str) -> str:
        upgraded_lines: List[str] = []
        for line in code.splitlines():
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]

            if not stripped.startswith("print ") or stripped.startswith("print ("):
                upgraded_lines.append(line)
                continue

            if stripped.startswith("print >>"):
                upgraded_lines.append(f"{indent}# TODO: manual migration required for redirected print: {stripped}")
                continue

            payload = stripped[6:].rstrip()
            if payload.endswith(","):
                payload = payload[:-1].rstrip()
            upgraded_lines.append(f"{indent}print({payload})")

        return "\n".join(upgraded_lines) + ("\n" if code.endswith("\n") else "")

    def _upgrade_backtick_repr(self, code: str) -> str:
        return re.sub(r"`([^`\n]+)`", r"repr(\1)", code)

    def _upgrade_apply_builtin(self, code: str) -> str:
        def replace(match):
            fn_name = match.group(1).strip()
            args_expr = match.group(2).strip()
            kwargs_expr = match.group(3)
            if kwargs_expr:
                return f"{fn_name}(*{args_expr}, **{kwargs_expr.strip()})"
            return f"{fn_name}(*{args_expr})"

        pattern = re.compile(
            r"\bapply\s*\(\s*([A-Za-z_][\w\.]*)\s*,\s*([^,\n][^,\n]*)\s*(?:,\s*([^)]+?)\s*)?\)"
        )
        return pattern.sub(replace, code)

    def _upgrade_exec_statement(self, code: str) -> str:
        upgraded_lines: List[str] = []
        for line in code.splitlines():
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]

            if not stripped.startswith("exec ") or stripped.startswith("exec("):
                upgraded_lines.append(line)
                continue

            payload = stripped[5:].strip()
            if " in " in payload:
                expr, env = payload.split(" in ", 1)
                parts = [part.strip() for part in env.split(",")]
                if len(parts) == 2:
                    upgraded_lines.append(f"{indent}exec({expr.strip()}, {parts[0]}, {parts[1]})")
                    continue
                if len(parts) == 1 and parts[0]:
                    upgraded_lines.append(f"{indent}exec({expr.strip()}, {parts[0]})")
                    continue

            upgraded_lines.append(f"{indent}exec({payload})")

        return "\n".join(upgraded_lines) + ("\n" if code.endswith("\n") else "")
