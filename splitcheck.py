"""Find simple data leakage between two CSV splits."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def normalise(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def read_rows(path: Path, id_column: str, text_column: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"{path.name} has no rows")
    missing = {id_column, text_column} - set(rows[0])
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    ids = [row[id_column].strip() for row in rows]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{path.name} IDs must be non-empty and unique")
    return rows


def audit(train: Path, test: Path, id_column="id", text_column="text", group_column=None) -> dict:
    train_rows = read_rows(train, id_column, text_column)
    test_rows = read_rows(test, id_column, text_column)
    train_text = {normalise(row[text_column]): row[id_column] for row in train_rows}
    overlaps = [
        {"train_id": train_text[key], "test_id": row[id_column]}
        for row in test_rows if (key := normalise(row[text_column])) in train_text
    ]
    groups = []
    if group_column:
        if group_column not in train_rows[0] or group_column not in test_rows[0]:
            raise ValueError(f"Both files need group column: {group_column}")
        train_groups = {row[group_column] for row in train_rows if row[group_column]}
        groups = sorted(train_groups & {row[group_column] for row in test_rows if row[group_column]})
    return {"train_rows": len(train_rows), "test_rows": len(test_rows),
            "exact_text_overlaps": overlaps, "shared_groups": groups,
            "passed": not overlaps and not groups}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train", type=Path)
    parser.add_argument("test", type=Path)
    parser.add_argument("--id-column", default="id")
    parser.add_argument("--text-column", default="text")
    parser.add_argument("--group-column")
    args = parser.parse_args()
    result = audit(args.train, args.test, args.id_column, args.text_column, args.group_column)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
