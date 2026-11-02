from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data_preprocessing.validate_dataset import validate_dataset

if __name__ == "__main__":
    csv = Path(__file__).resolve().parent / "normal_dataset.csv"
    ok, errors, report = validate_dataset(csv)
    print("===== NORMAL DATASET VALIDATION =====")
    print(report)
    if errors:
        print("VALIDATION FAILED")
        for error in errors: print("-", error)
        raise SystemExit(1)
    print("VALIDATION PASSED")
