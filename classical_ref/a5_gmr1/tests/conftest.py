"""
Ensures the project root (``a5_gmr1/``) is on ``sys.path`` so that test
modules can use the same flat imports (``from registers import LFSR``,
etc.) as the rest of the codebase, no matter which directory ``pytest``
is invoked from.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
