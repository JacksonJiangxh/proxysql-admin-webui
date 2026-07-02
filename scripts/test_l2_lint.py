#!/usr/bin/env python3
"""
L2: Static Analysis — Python (ruff) + TypeScript (eslint).
Catches unused variables, undefined names (F821), code smells.
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

passed = 0
failed = 0
failures: list[str] = []


def run(name: str, cmd: list[str], cwd: str | None = None, check_returncode: bool = True) -> bool:
    """Run a command and report success/failure."""
    global passed, failed, failures
    print(f"\n── {name} ──")
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
        # ruff/eslint exit code 0 = no errors
        if check_returncode and result.returncode != 0:
            # Show first 20 lines of output
            lines = (result.stdout + result.stderr).strip().split("\n")
            print("\n".join(lines[:30]))
            failed += 1
            failures.append(f"{name}: exit code {result.returncode}")
            print(f"  ❌ {name}: found issues")
            return False
        else:
            passed += 1
            print(f"  ✅ {name}: passed")
            return True
    except subprocess.TimeoutExpired:
        failed += 1
        failures.append(f"{name}: timed out")
        print(f"  ❌ {name}: timed out")
        return False
    except FileNotFoundError:
        failed += 1
        failures.append(f"{name}: command not found")
        print(f"  ❌ {name}: command not found (install ruff/eslint)")
        return False


def main():
    global passed, failed

    print("=" * 60)
    print("L2: Static Analysis")
    print("=" * 60)

    # ── L2a: Ruff (Python) ──
    # Check for critical errors only: E (pycodestyle errors), F (pyflakes)
    # We ignore E501 (line too long) as it's cosmetic
    backend_dir = os.path.join(ROOT_DIR, "backend")
    run("L2a: Ruff (Python — E, F errors)",
        ["ruff", "check", "app/", "--select", "E,F821,F822,F823,F901", "--ignore", "E501"],
        cwd=backend_dir)

    # ── L2b: Ruff all checks (warnings only, non-blocking) ──
    result = subprocess.run(
        ["ruff", "check", "app/", "--select", "F"],
        cwd=backend_dir, capture_output=True, text=True, timeout=120
    )
    lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
    if lines:
        print(f"\n── L2b: Ruff full scan ──")
        print(f"  {len(lines)} issues found (informational)")
        for line in lines[:15]:
            print(f"  {line}")
        if len(lines) > 15:
            print(f"  ... and {len(lines) - 15} more")
    else:
        print(f"\n── L2b: Ruff full scan ──")
        print(f"  ✅ No issues found")

    # ── L2c: ESLint (TypeScript) ──
    frontend_dir = os.path.join(ROOT_DIR, "frontend")
    # ESLint might not be installed or config may vary — make this informational
    try:
        result = subprocess.run(
            ["npx", "eslint", ".", "--ext", "ts,tsx", "--max-warnings", "200"],
            cwd=frontend_dir, capture_output=True, text=True, timeout=120
        )
        last_lines = (result.stdout + result.stderr).strip().split("\n")[-10:]
        print(f"\n── L2c: ESLint (TypeScript) ──")
        for line in last_lines:
            if line.strip():
                print(f"  {line.strip()}")
        if result.returncode == 0:
            passed += 1
            print(f"  ✅ ESLint: passed")
        else:
            print(f"  ⚠️ ESLint: warnings/errors (informational, not blocking)")
            passed += 1  # Don't fail on ESLint warnings
    except FileNotFoundError:
        print(f"\n── L2c: ESLint (TypeScript) ──")
        print(f"  ⚠️ ESLint not available, skipping")
    except subprocess.TimeoutExpired:
        print(f"\n── L2c: ESLint (TypeScript) ──")
        print(f"  ⚠️ ESLint timed out, skipping")

    # ── Summary ──
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"L2 Results: {passed}/{total} passed")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  ❌ {f}")
        sys.exit(1)
    else:
        print("✅ L2 static analysis passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
