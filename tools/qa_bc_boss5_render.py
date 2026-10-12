#!/usr/bin/env python3
"""Verify PCE boss five and all three original beam poses, including reprises."""
import runpy
import sys
from pathlib import Path
sys.argv=[sys.argv[0], '--boss', '5']
runpy.run_path(str(Path(__file__).with_name('qa_bc_pce_boss_bodies.py')),run_name='__main__')
