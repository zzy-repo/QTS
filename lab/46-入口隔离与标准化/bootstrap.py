from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LAB_ROOT = ROOT.parent
REPO_ROOT = ROOT.parents[1]

for path in (REPO_ROOT, LAB_ROOT, ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

