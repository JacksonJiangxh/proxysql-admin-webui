#!/usr/bin/env python3
"""L0: Python syntax compilation check — catch syntax errors immediately."""
import py_compile
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "backend")


def main():
    errors = []
    for dirpath, dirnames, filenames in os.walk(BACKEND_DIR):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "data", ".pytest_cache", "generated")]
        for f in filenames:
            if f.endswith(".py"):
                fp = os.path.join(dirpath, f)
                try:
                    py_compile.compile(fp, doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append(f"{fp}: {e}")

    if errors:
        print(f"❌ {len(errors)} syntax errors:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("  All Python files pass syntax check")
        sys.exit(0)


if __name__ == "__main__":
    main()
