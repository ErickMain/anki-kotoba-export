"""Puts the addon's aqt-free `kotoba` package on sys.path directly (as a
top-level package) so tests can import it without pulling in
kotoba_export/__init__.py, which imports aqt and can't run outside Anki.
"""
import sys
from pathlib import Path

ADDON_DIR = Path(__file__).resolve().parent.parent / "kotoba_export"
sys.path.insert(0, str(ADDON_DIR))
