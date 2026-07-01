"""
Test all apply() edge cases, malformed syntax, and anything that could
produce "Invalid star expression" errors.
"""
import sys, ast

sys.path.insert(0, ".")
from core.execution import ExecutionCore

engine = ExecutionCore()

# ── Test Cases ──────────────────────────────────────────────────────
cases = [
    # --- apply() variants ---
    ("apply: basic tuple arg",
     "x = apply(max, ([1,2,3],))"),

    ("apply: list arg",
     "x = apply(func, [1, 2, 3])"),

    ("apply: tuple of tuples",
     "x = apply(func, ((1,2), (3,4)))"),

    ("apply: with kwargs dict",
     "x = apply(func, [1, 2], {'key': 'val'})"),

    ("apply: nested call in args",
     "x = apply(func, (get_args(a, b, c),))"),

    ("apply: dotted function name",
     "x = apply(self.method, [1, 2, 3])"),

    ("apply: deeply nested commas",
     "x = apply(func, ([{'a': [1,2,3]}, {'b': [4,5,6]}],))"),

    ("apply: single element tuple",
     "x = apply(func, (arg,))"),

    ("apply: empty list arg",
     "x = apply(func, [])"),

    ("apply: multiple applies on one line",
     "x, y = apply(f, [1,2]), apply(g, [3,4])"),

    ("apply: multiline context",
     """def foo():
    result = apply(max, ([1,2,3],))
    return result"""),

    # --- print statement edge cases ---
    ("print: basic",
     "print 'hello world'"),

    ("print: multiple args with commas",
     "print 'a', 'b', 'c'"),

    ("print: trailing comma",
     "print 'hello',"),

    ("print: already function call",
     "print('hello')"),

    # --- except syntax ---
    ("except: old comma syntax",
     "try:\n    pass\nexcept Exception, e:\n    print e"),

    # --- xrange ---
    ("xrange: in for loop",
     "for i in xrange(10):\n    print i"),

    # --- has_key ---
    ("has_key: basic",
     "if d.has_key('x'):\n    print 'found'"),

    # --- not equal ---
    ("not-equal: diamond operator",
     "if x <> 5:\n    print 'diff'"),

    # --- backtick repr ---
    ("backtick: repr syntax",
     "x = `some_var`"),

    # --- combined stress test (the exact input that was failing) ---
    ("STRESS: full legacy class",
     """class LegacyService(object):
    def __init__(self):
        self.cache = {}

    def task_1(self, data):
        print 'Processing', data
        if self.cache.has_key('result'):
            print `self.cache['result']`
        total = 0
        try:
            for i in xrange(10):
                if i <> 5:
                    total += i
            x = apply(max, ([1,2,3],))
        except Exception, e:
            print e
        return total"""),
]

# ── Run Tests ───────────────────────────────────────────────────────
passed = 0
failed = 0
total = len(cases)

# Build a plan that applies ALL transforms in sequence
all_ops = [
    {"id": "upgrade_print_statement"},
    {"id": "upgrade_backtick_repr"},
    {"id": "upgrade_apply_builtin"},
    {"id": "upgrade_xrange"},
    {"id": "upgrade_raw_input"},
    {"id": "upgrade_except_syntax"},
    {"id": "upgrade_not_equal"},
    {"id": "upgrade_has_key"},
]

print("=" * 70)
print("HELIX AI — apply() & SYNTAX EDGE CASE TESTS")
print("=" * 70)

for name, code in cases:
    try:
        result = engine.apply_changes(code, [{"suggestion": op} for op in all_ops])

        # Now validate: can Python 3 parse it?
        ast.parse(result)

        # Check for invalid star expressions explicitly
        if "**," in result and "**{" not in result:
            raise SyntaxError(f"Suspicious double-star pattern in output")

        print(f"\n✅ PASS: {name}")
        print(f"   Input:  {code.splitlines()[0][:60]}...")
        print(f"   Output: {result.splitlines()[0][:60]}...")
        passed += 1

    except SyntaxError as e:
        print(f"\n❌ FAIL: {name}")
        print(f"   Input:  {code.splitlines()[0][:60]}...")
        print(f"   Error:  {e}")
        print(f"   Output: {result.splitlines()[0][:70]}...")
        failed += 1

    except Exception as e:
        print(f"\n❌ FAIL: {name}")
        print(f"   Input:  {code.splitlines()[0][:60]}...")
        print(f"   Error:  {type(e).__name__}: {e}")
        failed += 1

print("\n" + "=" * 70)
print(f"RESULTS: {passed}/{total} passed, {failed}/{total} failed")
print("=" * 70)

if failed > 0:
    sys.exit(1)
else:
    print("\n🎉 ALL TESTS PASSED — no 'Invalid star expression' errors!")
    sys.exit(0)
