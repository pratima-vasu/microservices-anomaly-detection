"""Compatibility wrapper; canonical preprocessing lives in data_preprocessing."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data_preprocessing.feature_engineering import *  # noqa: F401,F403
