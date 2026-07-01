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
        def _find_apply_args(text, start):
            """Parse balanced parentheses to extract apply() arguments correctly."""
            depth = 0
            i = start
            while i < len(text):
                if text[i] in '([{':
                    depth += 1
                elif text[i] in ')]}':
                    depth -= 1
                    if depth == 0:
                        return i
                i += 1
            return -1

        def _split_top_level_args(inner):
            """Split arguments at top-level commas only (not inside nested brackets)."""
            args = []
            depth = 0
            current = []
            for ch in inner:
                if ch in '([{':
                    depth += 1
                    current.append(ch)
                elif ch in ')]}':
                    depth -= 1
                    current.append(ch)
                elif ch == ',' and depth == 0:
                    args.append(''.join(current).strip())
                    current = []
                else:
                    current.append(ch)
            if current:
                args.append(''.join(current).strip())
            return args

        result = code
        apply_pattern = re.compile(r'\bapply\s*\(')
        offset = 0
        for match in apply_pattern.finditer(code):
            match_start = match.start() + offset
            paren_start = match.end() - 1 + offset  # position of '('
            paren_end = _find_apply_args(result, paren_start)
            if paren_end == -1:
                continue

            inner = result[paren_start + 1:paren_end]
            parts = _split_top_level_args(inner)

            if len(parts) < 2:
                continue

            fn_name = parts[0].strip()
            args_expr = parts[1].strip()
            # Remove outer tuple wrapper if present: ([1,2,3],) -> [1,2,3]
            if args_expr.startswith('(') and args_expr.endswith(',)'):
                args_expr = args_expr[1:-2].strip()
            elif args_expr.startswith('(') and args_expr.endswith(')'):
                inner_check = args_expr[1:-1].strip()
                if inner_check.endswith(','):
                    args_expr = inner_check[:-1].strip()

            if len(parts) == 3:
                kwargs_expr = parts[2].strip()
                replacement = f"{fn_name}(*{args_expr}, **{kwargs_expr})"
            else:
                replacement = f"{fn_name}(*{args_expr})"

            old_len = paren_end + 1 - match_start
            result = result[:match_start] + replacement + result[paren_end + 1:]
            offset += len(replacement) - old_len

        return result

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
