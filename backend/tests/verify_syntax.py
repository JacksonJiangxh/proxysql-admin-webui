#!/usr/bin/env python3
"""Verify Python syntax of all project files without importing them."""
import py_compile
import os
import sys


def verify_directory(root_dir):
    errors = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip __pycache__, data, generated (might not exist yet)
        dirnames[:] = [d for d in dirnames if d not in ('__pycache__', 'data')]
        for filename in filenames:
            if filename.endswith('.py'):
                filepath = os.path.join(dirpath, filename)
                try:
                    py_compile.compile(filepath, doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append(f"{filepath}: {e}")
    return errors


if __name__ == "__main__":
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    errors = verify_directory(backend_dir)

    if errors:
        print(f"Found {len(errors)} syntax errors:")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)
    else:
        print("All Python files pass syntax check!")
        sys.exit(0)
