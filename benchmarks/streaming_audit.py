"""Compare streaming and materialised audits on synthetic wide CSV files.

Run from the repository root: python benchmarks/streaming_audit.py
This measures Python allocations, not process RSS. Dataset creation is excluded.
"""
import argparse
import csv
import gc
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from splitcheck import audit, normalise, read_rows


def materialised_audit(train, test):
    train_rows = read_rows(train, "id", "text")
    test_rows = read_rows(test, "id", "text")
    index = {normalise(row["text"]): row["id"] for row in train_rows}
    overlaps = [
        {"train_id": index[key], "test_id": row["id"]}
        for row in test_rows
        if (key := normalise(row["text"])) in index
    ]
    return {
        "train_rows": len(train_rows), "test_rows": len(test_rows),
        "exact_text_overlaps": overlaps, "shared_groups": [],
        "passed": not overlaps,
    }


def measure(function, train, test):
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        result = function(train, test)
        elapsed = time.perf_counter() - started
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return result, {"seconds": elapsed, "peak_python_bytes": peak}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=5000, help="rows per split")
    parser.add_argument("--columns", type=int, default=8, help="unused payload columns")
    parser.add_argument("--payload-size", type=int, default=256)
    args = parser.parse_args()
    if args.rows < 1 or args.columns < 0 or args.payload_size < 0:
        parser.error("rows must be positive; columns and payload-size must be nonnegative")
    with tempfile.TemporaryDirectory() as directory:
        train, test = Path(directory) / "train.csv", Path(directory) / "test.csv"
        fields = ["id", "text"] + [f"unused_{i}" for i in range(args.columns)]
        for path, prefix in [(train, "train"), (test, "test")]:
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(fields)
                for i in range(args.rows):
                    writer.writerow(
                        [f"{prefix}-{i}", f"{prefix} message {i % 100}"]
                        + ["x" * args.payload_size] * args.columns
                    )
        original, baseline = measure(materialised_audit, train, test)
        current, streaming = measure(audit, train, test)
        if original != current:
            raise AssertionError("streaming report differs from the reference")
        print(json.dumps({
            "python": sys.version.split()[0],
            "rows_per_split": args.rows,
            "unused_columns": args.columns,
            "bytes_per_payload_field": args.payload_size,
            "materialised": baseline,
            "streaming": streaming,
            "peak_allocation_reduction_percent": (
                100 * (1 - streaming["peak_python_bytes"] / baseline["peak_python_bytes"])
            ),
            "reports_equal": True,
        }, indent=2))


if __name__ == "__main__":
    main()
