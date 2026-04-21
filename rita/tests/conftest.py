from __future__ import annotations

import sys
from pathlib import Path

EDGE_PATH = Path(__file__).resolve().parents[1] / "edge"
if str(EDGE_PATH) not in sys.path:
    sys.path.append(str(EDGE_PATH))
