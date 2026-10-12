#!/usr/bin/env python3
"""Compatibility entry point: Genesis substitutions are superseded by PCE imports."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('qa_bc_pce_boss_bodies.py')),run_name='__main__')
