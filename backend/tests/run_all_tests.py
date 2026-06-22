#!/usr/bin/env python3
"""Run all tests for the ProxySQL Admin WebUI backend."""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

if __name__ == "__main__":
    test_dir = os.path.dirname(os.path.abspath(__file__))
    exit_code = pytest.main([test_dir, "-v", "--tb=short"])
    sys.exit(exit_code)
