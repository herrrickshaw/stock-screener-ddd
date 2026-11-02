"""Shared pytest setup: put the repo root on sys.path so `import src...` resolves."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
