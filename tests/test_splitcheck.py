import csv
from pathlib import Path
import pytest
from splitcheck import audit, normalise


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader(); writer.writerows(rows)


def test_normalise_ignores_case_and_punctuation():
    assert normalise("Hello, WORLD!") == "hello world"


def test_audit_finds_text_and_group_overlap(tmp_path: Path):
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    write(train, [{"id": "a", "text": "Same message!", "group": "campaign-1"}])
    write(test, [{"id": "b", "text": "same message", "group": "campaign-1"}])
    result = audit(train, test, group_column="group")
    assert result["passed"] is False
    assert result["exact_text_overlaps"] == [{"train_id": "a", "test_id": "b"}]
    assert result["shared_groups"] == ["campaign-1"]


def test_duplicate_ids_are_rejected(tmp_path: Path):
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    write(train, [{"id": "a", "text": "one"}, {"id": "a", "text": "two"}])
    write(test, [{"id": "b", "text": "three"}])
    with pytest.raises(ValueError, match="unique"):
        audit(train, test)
