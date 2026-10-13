# SplitCheck: usage, CI integration and limitations

SplitCheck checks two CSV datasets for **normalised exact-text overlap**
and, optionally, **shared source groups**. The code is a small, standard
library Python command-line tool; it is not a semantic-duplicate detector
or a proof of independent machine-learning evaluation.

## CSV input contract

Both training and test CSV files need:

| Column | Default name | Rule |
| --- | --- | --- |
| Row identifier | `id` | Non-empty and unique **within each file** |
| Message text | `text` | Compared after case folding and basic punctuation/whitespace normalisation |
| Group | Optional `group` | Use `--group-column group` to test shared non-empty group values |

The file must contain at least one row and a header. It is read using
`utf-8-sig`, which also accepts a UTF-8 byte-order mark. Change column
names with `--id-column`, `--text-column` and `--group-column`.

The audit processes rows incrementally rather than retaining both complete CSVs.
It still stores the training text index, validation IDs and report findings;
see [Algorithm and measurement](ALGORITHM.md) for the memory boundary and benchmark.

Group values are compared as provided; there is **no normalisation of group
labels**. For realistic leakage checks, apply a consistent grouping scheme
upstream (for example the same campaign ID format in both files).
The script ignores empty group values rather than rejecting them; consider
requiring non-empty groups in your data preparation pipeline.

## Run a check

```bash
python splitcheck.py examples/train.csv examples/test.csv --group-column group
python -m pytest
```

The committed example intentionally fails: the test data repeats a
training message and its campaign group.

An alternate schema:

```bash
python splitcheck.py data/train.csv data/test.csv \
  --id-column message_id --text-column body --group-column campaign
```

This assumes you have supplied your own two input CSVs with those columns.
The command emits JSON with this shape:

```json
{
  "train_rows": 2,
  "test_rows": 2,
  "exact_text_overlaps": [
    {"train_id": "t2", "test_id": "e2"}
  ],
  "shared_groups": ["campaign-a"],
  "passed": false
}
```

The example output above corresponds to the checked-in example files.
The JSON keys can be consumed by another CI step or used for human review.

## Exit codes and CI

| Exit code | Meaning |
| --- | --- |
| `0` | Audit completed and no checked overlap detected |
| `1` | Audit completed but found exact-text or group overlaps |
| Nonzero due to Python exception | Missing files/columns, duplicate IDs, empty files or another execution error |

Do not interpret an exception as an ordinary overlap finding. The script
does not turn exceptions into a structured JSON report.

Example GitHub Actions step *after checking out your repository and
setting up Python*:

```yaml
- name: Check train-test leakage
  run: python splitcheck.py data/train.csv data/test.csv --group-column campaign
```

The command fails a step when the audit returns `1`. Ensure the
`splitcheck.py` script is present at that path in the consuming
repository. **Do not** rely on this gate alone for model validity.

## What "exact" means here

`normalise()` performs Unicode case folding, then keeps ASCII letter
and digit sequences matched by `[a-z0-9]+`, joined with single spaces.

Consequences:

- `"Hello, WORLD!"` and `"hello world"` compare equal.
- Identical wording with punctuation/case changes is caught.
- Paraphrases, translations, changed words, spelling mistakes and
  semantic near-duplicates are generally **not** caught.
- Some non-ASCII text can normalise poorly because the token pattern
  accepts ASCII alphanumerics only.
- Group equality does not detect related campaign IDs or indirect
  relationships.

`exact_text_overlaps` reports the matching training row ID and each
matching test row ID. It is not a count of independent data sources.
The dictionary used by the implementation retains one training ID per
normalised text value, so multiple training duplicates are **not**
fully enumerated. The check does not test duplicates within training or
within test, except for repeated row IDs in each file.

## Choosing a credible separation boundary

For phishing messages, prefer campaign/sender/time-window separation
over a random message-level split. For customer tickets, prefer
customer or organisation as appropriate. For healthcare records,
separate patients and account for repeated visits. For research papers
or documents, consider source and near-duplicate clustering.

This tool only detects **cross-split** exact text and selected group
overlap. Add task-specific checks for time leakage, target leakage,
semantic duplicates and evaluation-set reuse, and record their results
in your experiment protocol.

