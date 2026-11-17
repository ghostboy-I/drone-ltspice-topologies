"""Fallback test runner for machines without pytest (see ENVIRONMENT.md). The tests are plain pytest-style
functions, so `pytest tests/` is the preferred command once pytest is installed. This runner only discovers
tests/test_*.py::test_* and reports pass/fail; it is not a substitute for pytest's features."""
import importlib, os, sys, traceback

here = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(here, "tests"), os.path.join(here, "src")]
passed = failed = 0
for fn in sorted(os.listdir(os.path.join(here, "tests"))):
    if not (fn.startswith("test_") and fn.endswith(".py")):
        continue
    mod = importlib.import_module(fn[:-3])
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        try:
            getattr(mod, name)(); passed += 1; print(f"PASS {fn}::{name}")
        except Exception:
            failed += 1; print(f"FAIL {fn}::{name}"); traceback.print_exc()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
