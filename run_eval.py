#!/usr/bin/env python3
"""Convenience entry point for the Atavism Evaluation Harness.

Allows running the evaluation CLI directly via:
    python run_eval.py --help
    python run_eval.py eval --task all --dry-run
    python run_eval.py validate benchmark/tasks/T01_retry_semantics
    python run_eval.py models
    python run_eval.py report
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to sys.path so atavism package is immediately importable
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from atavism.cli import main

if __name__ == "__main__":
    sys.exit(main())

