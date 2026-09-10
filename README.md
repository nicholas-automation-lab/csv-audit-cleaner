# CSV Audit Cleaner

A small, runnable example of an auditable data-cleanup workflow. It converts explicitly selected numeric columns to exact decimal text, preserves identifier and text columns, and records what happened to every input row.

Written and tested by OpenAI Codex for this work account. This is a demonstration using synthetic data, not a past client project or a claim of professional credentials.

## Try it

Python 3.10 or newer, with no packages to install:

```sh
python -m unittest -v
python clean_csv.py sample.csv sample-result --numeric-columns amount quantity --group-mark , --deduplicate
```

The sample contains intentional errors. The command writes the report and exits **1** to flag rejected rows. Expected totals: 7 input rows, 3 kept, 2 rejected, 1 blank, 1 duplicate; 2 changed cells in retained rows. Review `sample-result/audit.json` before using the cleaned data.

`sample-result/cleaned.csv`:

```csv
record_id,amount,quantity
0001,1250,2
0002,34.5,3
0004,0,0
```

## What it does

- Leaves the source file intact and refuses an existing output directory.
- Requires numeric columns and decimal/group separators to be declared. It rejects ambiguous or malformed values rather than guessing.
- Preserves exact decimal values without binary floating-point conversion. Trailing decimal zeroes are removed; original numeric formatting is recorded when changed.
- Keeps identifiers such as `0001` unchanged when they are not selected as numeric columns.
- Removes all-empty rows. Duplicate removal is optional and compares complete normalized rows, not just one key.
- Retains rejected rows and reasons in the JSON audit, plus input/output SHA-256 hashes and row counts.
- Returns 0 for a clean run, 1 for a completed run with rejected rows, and 2 for a configuration, parsing, or filesystem error.

For a semicolon-separated file with European numeric formatting:

```sh
python clean_csv.py input.csv result --numeric-columns amount --delimiter ";" --decimal-mark , --group-mark .
```

## Limits

This sample handles UTF-8 CSV files, not Excel workbooks. It loads the file and audit into memory. It does not infer locale, recover malformed quoting, fill missing values, parse scientific notation, interpret dates, or correct business records. It preserves text, including any spreadsheet-formula text; open untrusted CSVs using an appropriate text import workflow. Choose duplicate and missing-value policies for the actual dataset before using it. The audit contains original rejected values and should be handled with the same privacy as the input.

Output is written to a new directory. An operating-system write failure may leave that new directory incomplete; a complete run needs both files and the reported exit status.

## Custom automation service — proposed fixed price: US$250

A starting scope for a paid engagement is one repeatable CSV cleanup or conversion workflow with up to three agreed source layouts, a command-line runner, an audit report, focused tests and a handoff README. The exact scope, file sizes, acceptance examples, price and delivery date must be agreed after reviewing a redacted sample. One correction round for agreed requirements is included in the proposed scope.

Work uses disclosed AI assistance. This demonstration is freely usable under the MIT license; the paid service is customization and delivery against agreed requirements. No client acceptance, contract, revenue, turnaround guarantee or payment method is implied by this listing.

To discuss a project, open an issue with a **synthetic or fully redacted example**, the desired result and the number/size of files. Do not post private data, passwords, financial details or production access. Sensitive intake and payment would be arranged through an agreed private channel before paid work begins.
