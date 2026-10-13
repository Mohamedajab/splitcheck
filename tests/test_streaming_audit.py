import csv
import random
import json
import subprocess
import sys

import pytest

import splitcheck


def write_rows(path, rows, fieldnames=None, encoding="utf-8"):
    with path.open("w", newline="", encoding=encoding) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def materialised_reference(train_rows, test_rows, group_column=None):
    index = {splitcheck.normalise(row["text"]): row["id"] for row in train_rows}
    overlaps = [
        {"train_id": index[key], "test_id": row["id"]}
        for row in test_rows
        if (key := splitcheck.normalise(row["text"])) in index
    ]
    groups = []
    if group_column:
        groups = sorted(
            {row[group_column] for row in train_rows if row[group_column]}
            & {row[group_column] for row in test_rows if row[group_column]}
        )
    return {
        "train_rows": len(train_rows), "test_rows": len(test_rows),
        "exact_text_overlaps": overlaps, "shared_groups": groups,
        "passed": not overlaps and not groups,
    }


def test_audit_does_not_materialise_rows(tmp_path, monkeypatch):
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    write_rows(train, [{"id": "t", "text": "Hello!"}])
    write_rows(test, [{"id": "e", "text": "hello"}])

    def reject_materialisation(*args):
        raise AssertionError("audit must not retain complete CSV row lists")

    monkeypatch.setattr(splitcheck, "read_rows", reject_materialisation)
    assert splitcheck.audit(train, test)["exact_text_overlaps"] == [
        {"train_id": "t", "test_id": "e"}
    ]


@pytest.mark.parametrize("group_column", [None, "group"])
@pytest.mark.parametrize("seed", range(10))
def test_matches_materialised_reference(tmp_path, group_column, seed):
    rng = random.Random(seed)
    texts = ["Hello!", "hello", "other text", "OTHER TEXT!", "", "123"]
    train_rows = [
        {"id": f"t{i}", "text": rng.choice(texts),
         "group": rng.choice(["", "a", "b", "c"]), "unused": "payload" * 100}
        for i in range(rng.randint(1, 40))
    ]
    test_rows = [
        {"id": f"e{i}", "text": rng.choice(texts),
         "group": rng.choice(["", "b", "c", "d"]), "unused": "payload" * 100}
        for i in range(rng.randint(1, 40))
    ]
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    write_rows(train, train_rows)
    write_rows(test, test_rows)
    assert splitcheck.audit(train, test, group_column=group_column) == (
        materialised_reference(train_rows, test_rows, group_column)
    )


def test_custom_columns_and_bom(tmp_path):
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    write_rows(train, [{"key": " t ", "body": "same", "source": "x"}], encoding="utf-8-sig")
    write_rows(test, [{"key": "e", "body": "SAME!", "source": "x"}])
    result = splitcheck.audit(train, test, "key", "body", "source")
    assert result["exact_text_overlaps"] == [{"train_id": " t ", "test_id": "e"}]
    assert result["shared_groups"] == ["x"]


@pytest.mark.parametrize("bad_split", ["train", "test"])
def test_late_duplicate_ids_abort_the_audit(tmp_path, bad_split):
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    rows = [{"id": "first", "text": "same"}, {"id": "second", "text": "other"}]
    write_rows(train, rows)
    write_rows(test, rows)
    write_rows(tmp_path / f"{bad_split}.csv", rows + [{"id": " first ", "text": "last"}])
    with pytest.raises(ValueError, match="non-empty and unique"):
        splitcheck.audit(train, test)


@pytest.mark.parametrize("bad_split", ["train", "test"])
def test_header_only_file_is_rejected(tmp_path, bad_split):
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    write_rows(train, [{"id": "t", "text": "one"}])
    write_rows(test, [{"id": "e", "text": "two"}])
    write_rows(tmp_path / f"{bad_split}.csv", [], ["id", "text"])
    with pytest.raises(ValueError, match="has no rows"):
        splitcheck.audit(train, test)


def test_missing_group_column_is_rejected(tmp_path):
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    write_rows(train, [{"id": "t", "text": "one", "group": "a"}])
    write_rows(test, [{"id": "e", "text": "two"}])
    with pytest.raises(ValueError, match="Both files need group column"):
        splitcheck.audit(train, test, group_column="group")


def test_read_rows_still_returns_a_list(tmp_path):
    path = tmp_path / "data.csv"
    rows = [{"id": "1", "text": "one"}, {"id": "2", "text": "two"}]
    write_rows(path, rows)
    assert splitcheck.read_rows(path, "id", "text") == rows


@pytest.mark.parametrize("overlap", [False, True])
def test_cli_report_and_exit_code_are_preserved(tmp_path, overlap):
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    train_rows = [{"id": "t", "text": "hello", "group": "a"}]
    test_rows = [{"id": "e", "text": "HELLO!" if overlap else "other", "group": "b"}]
    write_rows(train, train_rows)
    write_rows(test, test_rows)
    result = subprocess.run(
        [sys.executable, splitcheck.__file__, str(train), str(test), "--group-column", "group"],
        capture_output=True, text=True,
    )
    assert result.returncode == int(overlap)
    assert result.stderr == ""
    assert json.loads(result.stdout) == materialised_reference(train_rows, test_rows, "group")
