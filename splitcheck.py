"""Find simple data leakage between two CSV splits."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Iterator
from itertools import chain
from pathlib import Path


def normalise(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _iter_rows(
    path: Path, id_column: str, text_column: str, group_column=None
) -> Iterator[dict[str, str]]:
    """Validate CSV rows incrementally without retaining unused columns."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        first = next(reader, None)
        if first is None:
            raise ValueError(f"{path.name} has no rows")
        missing = {id_column, text_column} - set(first)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
        if group_column and group_column not in first:
            raise ValueError(f"Both files need group column: {group_column}")
        seen_ids = set()
        for row in chain((first,), reader):
            row_id = row[id_column].strip()
            if not row_id or row_id in seen_ids:
                raise ValueError(f"{path.name} IDs must be non-empty and unique")
            seen_ids.add(row_id)
            yield row


def read_rows(path: Path, id_column: str, text_column: str) -> list[dict[str, str]]:
    """Return validated rows for callers that explicitly need materialisation."""
    return list(_iter_rows(path, id_column, text_column))


def audit(train: Path, test: Path, id_column="id", text_column="text", group_column=None) -> dict:
    train_text = {}
    train_groups = set()
    train_count = 0
    for row in _iter_rows(train, id_column, text_column, group_column):
        train_count += 1
        # Preserve the existing last-training-ID selection for duplicate texts.
        train_text[normalise(row[text_column])] = row[id_column]
        if group_column and row[group_column]:
            train_groups.add(row[group_column])

    overlaps = []
    shared_groups = set()
    test_count = 0
    for row in _iter_rows(test, id_column, text_column, group_column):
        test_count += 1
        key = normalise(row[text_column])
        if key in train_text:
            overlaps.append({"train_id": train_text[key], "test_id": row[id_column]})
        if group_column and row[group_column] in train_groups:
            shared_groups.add(row[group_column])

    groups = sorted(shared_groups)
    return {"train_rows": train_count, "test_rows": test_count,
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
