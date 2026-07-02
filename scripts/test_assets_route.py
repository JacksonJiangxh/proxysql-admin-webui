#!/usr/bin/env python3
"""Test if /assets route is properly mounted and serving files."""

import sys
sys.path.insert(0, '/workspace/backend')

from pathlib import Path

# Test 1: Check if the paths are correct
__file__ = '/workspace/backend/app/main.py'
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
_ASSETS_DIR = _FRONTEND_DIST / "assets"

print("=" * 60)
print("Path Configuration Test")
print("=" * 60)
print(f"__file__ = {__file__}")
print(f"_FRONTEND_DIST = {_FRONTEND_DIST}")
print(f"  exists: {_FRONTEND_DIST.exists()}")
print(f"  is_dir: {_FRONTEND_DIST.is_dir()}")
print(f"_ASSETS_DIR = {_ASSETS_DIR}")
print(f"  exists: {_ASSETS_DIR.exists()}")
print(f"  is_dir: {_ASSETS_DIR.is_dir()}")

# Test 2: Check specific files
print("\n" + "=" * 60)
print("File Existence Test")
print("=" * 60)

files_to_check = [
    "index.html",
    "vite.svg",
    "assets/index-BaNuNU1Z.js",
    "assets/vendor-react-BUc2gA27.js",
    "assets/index-BRbvLNyG.css",
]

for file_path in files_to_check:
    full_path = _FRONTEND_DIST / file_path
    exists = full_path.exists()
    is_file = full_path.is_file()
    print(f"{file_path}: exists={exists}, is_file={is_file}")

# Test 3: List actual JS files
print("\n" + "=" * 60)
print("Actual JS files in /assets")
print("=" * 60)

if _ASSETS_DIR.exists():
    js_files = sorted([f for f in _ASSETS_DIR.iterdir() if f.suffix == '.js'])
    print(f"Found {len(js_files)} JS files:")
    for f in js_files[:5]:
        print(f"  {f.name}")
    if len(js_files) > 5:
        print(f"  ... and {len(js_files) - 5} more")

# Test 4: Test the full request path simulation
print("\n" + "=" * 60)
print("Request Path Simulation")
print("=" * 60)

request_paths = [
    "/",
    "/vite.svg",
    "/assets/index-BaNuNU1Z.js",
    "/api/v1/health",
    "/dashboard",
]

for req_path in request_paths:
    if req_path.startswith("/assets/"):
        # Simulate StaticFiles lookup
        asset_file = req_path.replace("/assets/", "")
        full_path = _ASSETS_DIR / asset_file
        result = f"StaticFiles: {full_path} -> exists={full_path.exists()}"
    elif req_path == "/":
        result = f"SPA fallback: index.html -> exists={(_FRONTEND_DIST / 'index.html').exists()}"
    elif req_path == "/vite.svg":
        full_path = _FRONTEND_DIST / "vite.svg"
        result = f"SPA fallback (direct file): {full_path} -> exists={full_path.exists()}"
    elif req_path.startswith("/api/") or req_path.startswith("/ws/"):
        result = "API/WebSocket route (handled by router)"
    else:
        result = f"SPA fallback: {_FRONTEND_DIST / req_path.lstrip('/')} -> exists={( _FRONTEND_DIST / req_path.lstrip('/')).exists()}"
    
    print(f"{req_path}: {result}")

print("\n" + "=" * 60)
print("Conclusion")
print("=" * 60)

if _ASSETS_DIR.exists() and (_ASSETS_DIR / "index-BaNuNU1Z.js").exists():
    print("✓ All paths are correct. The issue might be in the FastAPI routing.")
    print("✓ Check if StaticFiles is correctly mounted.")
else:
    print("✗ Directory or file paths are incorrect!")
    print("✗ Please verify the _FRONTEND_DIST and _ASSETS_DIR paths.")
