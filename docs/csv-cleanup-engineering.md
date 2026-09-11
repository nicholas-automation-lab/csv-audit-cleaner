# A CSV cleaner should explain every missing row

*AI-authored by OpenAI Codex for Nicholas Alejos, September 11, 2026. I inspected the source and ran the examples locally with Python 3.12.14. This article describes a synthetic demonstration, not client work or production experience.*

Seven input rows became three output rows when I ran [CSV Audit Cleaner](https://github.com/nicholas-automation-lab/csv-audit-cleaner). That sounds alarming until you look at the other four: two failed validation, one was blank, and one duplicated an accepted row after normalization. The useful result was not just the smaller CSV. It was an explanation for the difference.

I think that explanation belongs in the design of a cleanup script. A successful parse tells us that software understood some text. It does not establish that the software made the right decision about an identifier, missing quantity, or ambiguous decimal separator. This small Python tool makes those decisions explicit and records their consequences. Its implementation also exposes a few boundaries that are easy to miss when a script appears to work on a sample.

The project uses the standard library. To reproduce the main example from its directory, run:

```sh
python -m unittest -v
python clean_csv.py sample.csv sample-result --numeric-columns amount quantity --group-mark , --deduplicate
```

Choose an output directory that does not already exist. The first command passed all six tests in my local run. The second completed with exit status **1**, deliberately signaling rejected rows. It produced both `cleaned.csv` and `audit.json`; status 1 here does not mean that nothing was written.

The sample input is small enough to inspect completely:

```csv
record_id,amount,quantity
0001,"1,250.00",2
0001,"1,250.000",2.0
0002, 34.50 ,3
0003,unknown,1
,,
0004,0,0
0005,12.10,
```

Only `amount` and `quantity` are declared numeric. That choice preserves `0001` as an identifier while converting `1,250.00` to `1250`. Treating every numeric-looking field alike would erase the distinction between a value used in arithmetic and a code whose leading zeroes matter. Here, text columns retain their parsed field values. The output file is still newly serialized CSV: quoting, line endings, and any input byte-order mark are not promised to survive unchanged.

The numeric parser first validates the spelling of a value against declared decimal and grouping marks. It then removes valid grouping marks and converts the decimal mark to a period. That order matters. Simply deleting every comma would turn malformed `12,34.50` into a plausible-looking `1234.50` and conceal the original problem.

I ran the following cases through `normalize_number`:

| Input | Decimal mark | Group mark | Observed result |
| --- | --- | --- | --- |
| `1,234` | `.` | None | Rejected |
| `1,234` | `.` | `,` | `1234` |
| `1,234` | `,` | `.` | `1.234` |
| `12,34.50` | `.` | `,` | Rejected |
| `1.234,50` | `,` | `.` | `1234.5` |

The middle two rows are the important pair. The same input string can represent different values under different valid conventions. The parser cannot resolve that disagreement from the string alone. In this implementation, a convention applies to all selected numeric columns in a run. A file that mixes conventions needs investigation or an explicit transformation before this tool is appropriate. Calling a guess “locale detection” would not remove that responsibility.

After validation, the implementation constructs `Decimal` directly from the canonical string. It does not pass through `float`. This local comparison shows why that distinction is relevant:

```python
from decimal import Decimal

print(format(float("0.1"), ".20f"))  # 0.10000000000000000555
print(format(Decimal("0.1"), "f"))   # 0.1
```

The extra digits expose binary approximation; they are not information from the input. Python's [floating-point tutorial](https://docs.python.org/3/tutorial/floatingpoint.html) explains this representation issue. An exact textual cleanup should not introduce that conversion when no arithmetic requires it.

There is a second trap: choosing `Decimal` does not make every operation preserve every digit. Python documents that string construction retains the supplied digits, while arithmetic uses the active context. The [`normalize()` operation](https://docs.python.org/3/library/decimal.html#decimal.Decimal.normalize) also applies rounding. At precision 28, I reproduced this result:

```python
from decimal import Decimal, localcontext
from clean_csv import normalize_number

value = "123456789012345678901234567890.123400"
with localcontext() as context:
    context.prec = 28
    print(format(Decimal(value).normalize(), "f"))
    # 123456789012345678901234567900
    print(normalize_number(value))
    # 123456789012345678901234567890.1234
```

The cleaner instead formats the constructed decimal with `"f"`, then removes trailing zeroes only from the fractional portion. It also turns negative zero into `0`. That preserves the numeric value in the tested cases, but intentionally discards scale. If `12.00` means “measured to two decimal places” in a dataset, changing it to `12` loses useful information even though the numbers compare equal. This tool's policy must therefore be agreed before applying it to such data. It performs normalization, not monetary rounding or measurement validation.

Row handling is similarly deliberate. A missing value in a selected numeric column rejects the entire nonblank row. The parser does not substitute zero, retain a partly cleaned record, or invent a quantity. In the sample, `0005` has a valid amount and an empty quantity, so it is rejected. The audit retains the original row and identifies `quantity` as the failing column. `unknown` rejects `0003` for an invalid numeric spelling. A row consisting entirely of whitespace or empty fields is counted separately as blank.

The existing tests also cover unsupported numeric spellings such as scientific notation, `NaN`, and underscores, along with wrong field counts and malformed CSV. These are boundaries of this parser's accepted input language. For example, rejecting `1e3` does not imply that scientific notation is inherently bad data; it means a caller must not assume this script supports it.

Duplicate handling happens after successful normalization and only when requested. It compares the complete normalized row. In the sample, these records converge:

```text
0001,"1,250.00",2      -> 0001,1250,2
0001,"1,250.000",2.0   -> 0001,1250,2
```

The first is retained; the second receives a duplicate event containing its original and normalized fields. This is not a rule that an identifier must be unique. Two rows with the same identifier and different amounts would have different comparison keys. Nor does it establish that repeated identical transactions are erroneous. For a ledger where repetition is meaningful, leave deduplication disabled unless the business rule says otherwise.

The sample's output was:

```csv
record_id,amount,quantity
0001,1250,2
0002,34.5,3
0004,0,0
```

The audit reported seven input rows, three kept, two rejected, one blank, and one duplicate. Those row categories reconcile:

```python
assert counts["input_rows"] == sum(
    counts[key] for key in
    ("kept_rows", "rejected_rows", "blank_rows", "duplicate_rows")
)
```

I verified this equality in the fresh sample run and inspected the seven audit events. The header is excluded from these counts. The audit's `record` numbering includes the header, so the first data record is numbered 2; `ending_line` separately records where the CSV reader finished that record. This distinction matters when a quoted text field spans multiple physical lines, a case included in the existing tests.

The report also counted two changed cells. That counter covers changes in **retained** rows: the first amount and the whitespace-padded `34.50`. It does not include normalization inside a discarded duplicate or a rejected row. Without that definition, a reader could mistake the counter for the total number of transformations attempted. An audit field needs a clear meaning as much as it needs a value.

I checked that the source bytes were unchanged and that the report's SHA-256 values matched the source and output bytes. These checks connect the report to particular files; they do not prove that the cleanup rules were correct. The program completes parsing before creating the destination, refuses an existing destination, and the tests exercise those protections. However, the two output files are written sequentially. An operating-system write failure could leave an incomplete new directory. Existence alone is insufficient evidence of a completed run.

There are other practical limits. The implementation loads the input, accepted rows, and audit into memory; this exercise measured no large-file capacity or throughput. It handles UTF-8 CSV, including a UTF-8 byte-order mark, and always writes comma-separated output even when the input delimiter differs. It preserves text that a spreadsheet might interpret as a formula. The audit also contains original rejected values and should receive the same care as the source data. Six passing tests and one synthetic walkthrough establish observed behavior, not production readiness for every export.

My design preference after this inspection is to keep the output and its explanation inseparable. Before importing the result, a caller can review the declared rules, rejected records, duplicate policy, reconciled counts, and file hashes. The three retained rows are easy to produce. Being able to account for the other four is what makes this small cleanup result reviewable.
