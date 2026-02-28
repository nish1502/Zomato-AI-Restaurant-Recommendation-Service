"""
Test package initializer.

Ensures the project root is on sys.path so `app` can be imported when
running tests via the local virtual environment.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

