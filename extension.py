#!/usr/bin/env python3
"""API 0.4 entrypoint; stdout belongs exclusively to the octet SDK."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
from octet_ableton.extension import build_extension

if __name__ == "__main__":
    build_extension().run()
