# SplitCheck

A small command-line check for a common machine-learning mistake: putting the
same text or the same source group in both training and evaluation data.

```powershell
python splitcheck.py examples/train.csv examples/test.csv --group-column group
python -m pytest
```

The example exits with status 1 because it contains one repeated message and
one shared campaign. A clean split exits with status 0, which makes the script
usable in CI.

The comparison lowercases text, removes punctuation and collapses whitespace.
It does not detect paraphrases, translations or copied content with substantial
edits. In a real project, choose groups that match the deployment risk (such as
sender, campaign, patient or organisation), and add dataset-specific checks.

Main idea to explain: a random row split can look accurate while testing on
near-copies of training data. Group separation makes the evaluation harder but
more relevant.
