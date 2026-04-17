from __future__ import annotations

import sys
from pathlib import Path


E2E_ROOT = Path(__file__).resolve().parent
REPO_ROOT = E2E_ROOT.parents[1]

for candidate in (str(REPO_ROOT), str(E2E_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)
