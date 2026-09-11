# CSV Audit Cleaner

## One-file CSV cleanup — US$99

Numeric columns importing incorrectly? Get a cleaned CSV plus a record of changed cells, rejected rows and reconciled row counts. Your original file stays intact.

The fixed scope covers one UTF-8 CSV up to 10 MB and 10,000 rows, up to five numeric columns, one agreed decimal/group separator convention, and optional removal of exact duplicate rows. Includes one correction round against the agreed requirements. Excel workbooks, live system imports and business-record corrections are outside this scope.

**Start with a free fit check:** email [Nicholas Alejos](mailto:nicholasalejos7@gmail.com?subject=CSV%20cleanup%20fit%20check) with 5–10 synthetic or fully redacted rows, your desired result, and the total file size/row count. Send no passwords, private customer data or banking details. Price, delivery date and payment method are confirmed before work starts; sending a sample creates no purchase obligation.

Work uses AI assistance. The code below is free under the MIT license; the paid service is applying agreed rules, checking results and delivering your files. This is a synthetic demonstration, not a past client project.

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

Written and tested by OpenAI Codex for this work account.
