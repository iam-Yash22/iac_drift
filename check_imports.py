"""
Import auditor for iac_driftwatch.

Walks every module under app/ and attempts to import it directly,
catching any import-time error (ModuleNotFoundError, AttributeError,
SyntaxError, etc.) without needing the server running and without
depending on what app/api/v1/router.py currently wires in.

Run from the project root (same folder as main.py), with your venv
active - the same way you'd run uvicorn:

    python check_imports.py
"""
import importlib
import pkgutil
import sys

import app

modules = sorted(
    name for _, name, _ in pkgutil.walk_packages(app.__path__, prefix="app.")
)

errors = []
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        errors.append((name, exc))

print(f"Checked {len(modules)} modules under app/\n")

if not errors:
    print("All modules imported cleanly.")
    sys.exit(0)

print(f"{len(errors)} module(s) failed to import:\n")
for name, exc in errors:
    print(f"  {name}")
    print(f"    {type(exc).__name__}: {exc}\n")

sys.exit(1)