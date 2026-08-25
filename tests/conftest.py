"""Pytest configuration for the OSGenome2 test suite.

Adds the project root to sys.path so tests can import the top-level
modules (GenomeImporter, app) regardless of where pytest is invoked from.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
