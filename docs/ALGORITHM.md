# Streaming leakage audit: algorithm and measurement

## Data structures

The audit reads the training CSV once, normalises each text, and stores its row
ID in a dictionary keyed by normalised text. Assigning an existing key preserves
the previous behaviour: the last matching training ID is used in the report.
An optional set records non-empty training groups.

The test CSV is then read once. Dictionary membership identifies text overlap;
set membership identifies shared groups. Matches are appended in test-file
order, while a set deduplicates shared groups before sorting them for the report.
Unused CSV columns are discarded as iteration advances.

The row iterator validates unique, non-empty IDs with a per-file set. It checks
the entire input, including rows after the first overlap. A late validation error
aborts the audit; the CLI does not print a partial JSON report.

`read_rows()` remains available and returns a list for existing callers. The
`audit()` hot path uses the incremental iterator instead.

## Complexity and limits

For `n` training rows and `m` test rows, dictionary and set operations take
expected O(n + m) time, plus text normalisation and sorting `g` shared groups in
O(g log g). Hash-table operations are expected-time, not a worst-case guarantee.

Memory is not constant: the training text index, training group set, per-file
ID-validation set and output overlaps must still fit in RAM. Its size depends on
unique text lengths, IDs, groups and number of matches. The change removes the
additional retention of both complete CSV row lists and their unused columns.
It is most useful for wide files with large payload fields that are not audited.

## Reproduce the comparison

From the repository root with Python 3.11 or newer:

```bash
python benchmarks/streaming_audit.py --rows 5000 --columns 8 --payload-size 256
python -m pytest
```

The benchmark generates two synthetic CSVs in a temporary directory, then
compares an equivalent materialised reference against the streaming audit.
It checks report equality before printing timings and peak Python allocations.
File generation is excluded from the measurement, and temporary files are cleaned
up afterwards. No production dataset or network access is used.

`tracemalloc` measures tracked Python allocations, not total process RSS. Timings
include its overhead and depend on Python, hardware and filesystem caching;
this is a reproducible microbenchmark, not a production throughput guarantee.
Use `--columns 0` to compare narrow files, or increase `--rows` to study ID/index
growth. Keep memory claims tied to the exact reported workload.

### Observed local allocation comparison

A single local run on Python 3.14.5, Windows, on 13 October 2026 used 5,000
rows per split and 256 characters per unused field:

| Unused columns | Materialised peak bytes | Streaming peak bytes | Reduction |
| --- | --- | --- | --- |
| 8 | 28,316,228 | 1,088,533 | 96.2% |
| 0 | 3,775,481 | 1,075,891 | 71.5% |

Both reports matched the reference exactly. This is a synthetic allocation
comparison, not a claim about real datasets, production throughput or process RSS.
The reference uses the same row validation but retains both full row lists.

## Correctness checks

Regression tests cover the streaming path, report equality with a materialised
reference across seeded random inputs, last-training-ID selection, output order,
empty groups, custom columns, UTF-8 BOM, missing columns, header-only files,
late duplicate IDs and incremental iterator validation. Existing example and CLI
semantics remain unchanged; this does not add semantic-duplicate detection.
