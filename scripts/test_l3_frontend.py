#!/usr/bin/env python3
"""
L3: Frontend Build Verification — TypeScript type check + Vite production build.
Ensures the frontend can compile and bundle without errors.
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "frontend")

passed = 0
failed = 0
failures: list[str] = []


def run(name: str, cmd: list[str], cwd: str, timeout: int = 120) -> bool:
    """Run command, return True on success."""
    global passed, failed, failures
    print(f"\n── {name} ──")
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            lines = (result.stdout + result.stderr).strip().split("\n")
            # Show first 30 error lines
            for line in lines[:30]:
                print(f"  {line}")
            if len(lines) > 30:
                print(f"  ... and {len(lines) - 30} more lines")
            failed += 1
            failures.append(f"{name}: exit code {result.returncode}")
            print(f"  ❌ {name}: FAILED")
            return False
        else:
            passed += 1
            print(f"  ✅ {name}: passed")
            return True
    except subprocess.TimeoutExpired:
        failed += 1
        failures.append(f"{name}: timed out after {timeout}s")
        print(f"  ❌ {name}: timed out")
        return False
    except FileNotFoundError as e:
        failed += 1
        failures.append(f"{name}: {e}")
        print(f"  ❌ {name}: command not found — is Node.js installed?")
        return False


def main():
    global passed, failed

    print("=" * 60)
    print("L3: Frontend Build Verification")
    print(f"Frontend: {FRONTEND_DIR}")
    print("=" * 60)

    # ── L3a: TypeScript Type Check ──
    run("L3a: TypeScript Check (tsc --noEmit)",
        ["npx", "tsc", "--noEmit"],
        cwd=FRONTEND_DIR, timeout=60)

    # ── L3b: Vite Build ──
    run("L3b: Vite Production Build",
        ["npx", "vite", "build", "--logLevel", "warn"],
        cwd=FRONTEND_DIR, timeout=120)

    # ── L3c: Verify build output ──
    dist_dir = os.path.join(FRONTEND_DIR, "dist")
    index_html = os.path.join(dist_dir, "index.html")
    assets_dir = os.path.join(dist_dir, "assets")

    print(f"\n── L3c: Build Output Verification ──")
    if os.path.isfile(index_html):
        passed += 1
        print(f"  ✅ dist/index.html exists")
    else:
        failed += 1
        failures.append("dist/index.html not found")
        print(f"  ❌ dist/index.html not found")

    if os.path.isdir(assets_dir):
        asset_count = len(os.listdir(assets_dir))
        passed += 1
        print(f"  ✅ dist/assets/ exists ({asset_count} files)")
    else:
        failed += 1
        failures.append("dist/assets/ not found")
        print(f"  ❌ dist/assets/ not found")

    # ── Summary ──
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"L3 Results: {passed}/{total} passed")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  ❌ {f}")
        sys.exit(1)
    else:
        print("✅ L3 frontend build passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
