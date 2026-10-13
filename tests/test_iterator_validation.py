import csv

import pytest

from splitcheck import _iter_rows, audit


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_rows_are_validated_as_the_iterator_advances(tmp_path):
    path = tmp_path / "data.csv"
    write_rows(path, [{"id": "a", "text": "one"}, {"id": "a", "text": "two"}])
    rows = _iter_rows(path, "id", "text")
    assert next(rows) == {"id": "a", "text": "one"}
    with pytest.raises(ValueError, match="unique"):
        next(rows)


@pytest.mark.parametrize("missing", ["id", "text"])
def test_missing_required_column(tmp_path, missing):
    path = tmp_path / "data.csv"
    row = {"id": "a", "text": "one"}
    del row[missing]
    write_rows(path, [row])
    with pytest.raises(ValueError, match="missing columns"):
        audit(path, path)


def test_whitespace_only_id(tmp_path):
    path = tmp_path / "data.csv"
    write_rows(path, [{"id": " ", "text": "one"}])
    with pytest.raises(ValueError, match="non-empty"):
        audit(path, path)
