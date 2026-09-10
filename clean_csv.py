"""Normalize numeric CSV data with explicit locale rules and a row audit.

Python 3.10+; standard library only. Original files are never modified.
"""

import argparse
import csv
import hashlib
import io
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


def normalize_number(value, decimal_mark=".", group_mark=None):
    """Return an exact decimal string; reject rather than guess malformed data."""
    value = value.strip()
    if not value:
        raise ValueError("missing numeric value")
    if len(value) > 1000:
        raise ValueError("numeric value exceeds 1000 characters")
    if decimal_mark not in (".", ","):
        raise ValueError("decimal mark must be '.' or ','")
    if group_mark not in (None, ".", ",", " ") or group_mark == decimal_mark:
        raise ValueError("invalid group mark")
    fraction = re.escape(decimal_mark) + r"[0-9]+"
    integer = r"[0-9]+"
    if group_mark:
        grouped = r"[0-9]{1,3}(?:" + re.escape(group_mark) + r"[0-9]{3})+"
        integer = "(?:" + integer + "|" + grouped + ")"
    pattern = r"[+-]?(?:" + integer + "(?:" + fraction + ")?|" + fraction + ")"
    if not re.fullmatch(pattern, value):
        raise ValueError("invalid number for the declared locale")
    canonical = value.replace(group_mark, "") if group_mark else value
    canonical = canonical.replace(decimal_mark, ".")
    try:
        number = Decimal(canonical)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    # No float conversion or Decimal.normalize(), which may round to context precision.
    result = format(number, "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return "0" if number == 0 else result


def clean(source, destination, *, numeric_columns, decimal_mark=".",
          group_mark=None, delimiter=",", deduplicate=False):
    """Write a new output directory containing cleaned.csv and audit.json.

    Numeric columns are explicit; other columns remain byte-for-character values
    after CSV parsing. A rejected row is retained in audit.json with its reason.
    """
    source = Path(source)
    destination = Path(destination)
    # Validate options even when input has no data rows.
    normalize_number("0", decimal_mark, group_mark)
    if len(delimiter) != 1 or delimiter in ('"', "\r", "\n"):
        raise ValueError("delimiter must be one character other than quote or newline")
    columns = list(numeric_columns)
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("specify distinct numeric column names")
    if destination.exists():
        raise ValueError("output directory already exists; choose a new directory")
    raw = source.read_bytes()
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""),
                        delimiter=delimiter, strict=True)
    header = next(reader, None)
    if not header or any(not name.strip() for name in header):
        raise ValueError("input needs nonempty column headers")
    if len(header) != len(set(header)):
        raise ValueError("duplicate column headers")
    unknown = set(columns) - set(header)
    if unknown:
        raise ValueError("unknown numeric columns: " + ", ".join(sorted(unknown)))
    indices = [header.index(name) for name in columns]
    counts = dict(input_rows=0, kept_rows=0, rejected_rows=0, blank_rows=0,
                  duplicate_rows=0, changed_cells=0)
    events = []
    accepted = []
    seen = set()
    # Complete parsing before creating any output, so malformed CSV cannot leave
    # a successful-looking partial report.
    for record, row in enumerate(reader, start=2):
        counts["input_rows"] += 1
        base = {"record": record, "ending_line": reader.line_num}
        if not row or all(not cell.strip() for cell in row):
            counts["blank_rows"] += 1
            events.append({**base, "action": "blank", "original": row})
            continue
        if len(row) != len(header):
            counts["rejected_rows"] += 1
            events.append({**base, "action": "rejected", "original": row,
                           "reason": f"expected {len(header)} fields, got {len(row)}"})
            continue
        normalized = row.copy()
        changes = []
        errors = []
        for index in indices:
            try:
                normalized[index] = normalize_number(row[index], decimal_mark, group_mark)
            except ValueError as exc:
                errors.append({"column": header[index], "reason": str(exc)})
            if normalized[index] != row[index]:
                changes.append({"column": header[index], "from": row[index],
                                "to": normalized[index]})
        if errors:
            counts["rejected_rows"] += 1
            events.append({**base, "action": "rejected", "original": row, "errors": errors})
            continue
        key = tuple(normalized)
        if deduplicate and key in seen:
            counts["duplicate_rows"] += 1
            events.append({**base, "action": "duplicate", "original": row,
                           "normalized": normalized})
            continue
        seen.add(key)
        accepted.append(normalized)
        counts["kept_rows"] += 1
        counts["changed_cells"] += len(changes)
        events.append({**base, "action": "kept", "output_record": len(accepted) + 1,
                       "changes": changes})
    audit = {
        "schema_version": 1,
        "source_name": source.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "rules": {"numeric_columns": columns, "decimal_mark": decimal_mark,
                  "group_mark": group_mark, "delimiter": delimiter,
                  "deduplicate": deduplicate},
        "counts": counts, "events": events,
    }
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(accepted)
    output_bytes = output.getvalue().encode("utf-8")
    audit["output_sha256"] = hashlib.sha256(output_bytes).hexdigest()
    # exist_ok=False also protects against two processes selecting the same path.
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "cleaned.csv").write_bytes(output_bytes)
    (destination / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--numeric-columns", nargs="+", required=True)
    parser.add_argument("--decimal-mark", choices=[".", ","], default=".")
    parser.add_argument("--group-mark", choices=[".", ",", " "])
    parser.add_argument("--delimiter", default=",")
    parser.add_argument("--deduplicate", action="store_true")
    args = parser.parse_args()
    try:
        counts = clean(args.input, args.output_directory,
                       numeric_columns=args.numeric_columns,
                       decimal_mark=args.decimal_mark, group_mark=args.group_mark,
                       delimiter=args.delimiter, deduplicate=args.deduplicate)
    except (ValueError, OSError, UnicodeError, csv.Error) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(counts, indent=2))
    return 1 if counts["rejected_rows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
