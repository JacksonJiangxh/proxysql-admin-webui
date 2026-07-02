#!/usr/bin/env python3
"""L1: Import check — recursively import all backend modules to catch
ImportError, NameError, missing dependencies, circular imports."""

import sys
import os
import importlib
import traceback

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

# Required env vars before imports
os.environ.setdefault("FERNET_KEY", "02F01gw2gjGLev9LC_hGdPYx4cyU4qEAyWWAA4Pa85g=")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/test_l1_import.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-min-32-chars!!")
os.environ.setdefault("PROXYWEB_ADMIN_USER", "admin")
os.environ.setdefault("PROXYWEB_ADMIN_PASSWORD", "admin123")


def discover_modules(app_dir: str, base_path: str) -> list[str]:
    """Walk app/ directory and return dotted module names."""
    modules = []
    for dirpath, dirnames, filenames in os.walk(app_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith("__") and d not in ("data",)]
        for f in filenames:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(dirpath, f), base_path)
                mod = rel[:-3].replace("/", ".")
                modules.append(mod)
    return sorted(modules)


def main():
    app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "app")
    base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
    modules = discover_modules(app_dir, base_path)

    errors: list[str] = []
    ok = 0

    for mod in modules:
        try:
            importlib.import_module(mod)
            ok += 1
        except Exception as e:
            err_msg = f"{mod}: {type(e).__name__}: {e}"
            errors.append(err_msg)
            if len(errors) <= 10:
                traceback.print_exc()
                print("---")

    print(f"\n=== L1 Import Check: {len(modules)} modules, {ok} OK, {len(errors)} errors ===")
    for e in errors:
        print(f"  ❌ {e}")

    if errors:
        sys.exit(1)
    else:
        print("✅ All modules import successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
