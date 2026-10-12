#!/usr/bin/env python3
"""Verify original PCE boss 3: packed pixels, hardware poses and R9 reprise."""
import runpy
import sys
from pathlib import Path
sys.argv=[sys.argv[0], '--boss', '3']
runpy.run_path(str(Path(__file__).with_name('qa_bc_pce_boss_bodies.py')),run_name='__main__')
