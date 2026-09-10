import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from clean_csv import clean, normalize_number


class NumericCleaningTests(unittest.TestCase):
    def test_exact_large_decimal_without_rounding(self):
        self.assertEqual(normalize_number("123456789012345678901234567890.123400"),
                         "123456789012345678901234567890.1234")

    def test_locale_is_explicit_and_strict(self):
        self.assertEqual(normalize_number("1.234,50", ",", "."), "1234.5")
        self.assertEqual(normalize_number("-0.000"), "0")
        self.assertEqual(normalize_number("  +.500 "), "0.5")
        for value in ["1,234", "12x", "1e3", "NaN", "Infinity", "", "1_000"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_number(value)
        with self.assertRaises(ValueError):
            normalize_number("12,34.50", ".", ",")

    def test_pipeline_reconciliation_audit_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            original = b'code,amount\n001, 12.50 \n001,12.500\n002,bad\n,\n003,0\n004,\n005,1,extra\n'
            source.write_bytes(original)
            output = root / "result"
            counts = clean(source, output, numeric_columns=["amount"], deduplicate=True)
            self.assertEqual(counts, {"input_rows": 7, "kept_rows": 2,
                "rejected_rows": 3, "blank_rows": 1, "duplicate_rows": 1, "changed_cells": 1})
            self.assertEqual(counts["input_rows"], sum(counts[key] for key in
                ["kept_rows", "rejected_rows", "blank_rows", "duplicate_rows"]))
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual((output / "cleaned.csv").read_text(), 'code,amount\n001,12.5\n003,0\n')
            audit = json.loads((output / "audit.json").read_text())
            self.assertEqual(len(audit["events"]), 7)
            self.assertEqual(audit["source_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(audit["output_sha256"], hashlib.sha256((output / "cleaned.csv").read_bytes()).hexdigest())

    def test_no_overwrite_and_no_output_on_structural_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.csv", root / "result"
            for data in ['n,n\n1,2\n', 'n\n"unterminated', 'n\n']:
                source.write_text(data)
                with self.subTest(data=data), self.assertRaises((ValueError, csv.Error)):
                    clean(source, output, numeric_columns=["missing"] if data == 'n\n' else ["n"])
                self.assertFalse(output.exists())
            source.write_text('n\n1\n')
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(ValueError):
                clean(source, output, numeric_columns=["n"])
            self.assertEqual(marker.read_text(), "keep")

    def test_cli_exit_codes_and_locale_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            source.write_text('\ufeffid;amount\n001;1.234,50\n002;0,00\n', encoding="utf-8")
            command = [sys.executable, str(Path(__file__).with_name("clean_csv.py")),
                str(source), str(root / "ok"), "--numeric-columns", "amount",
                "--delimiter", ";", "--decimal-mark", ",", "--group-mark", "."]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "ok" / "cleaned.csv").read_text(), 'id,amount\n001,1234.5\n002,0\n')
            source.write_text('id;amount\n001;bad\n')
            command[3] = str(root / "rejected")
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            command[3] = str(root / "rejected")
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)

    def test_multiline_text_and_opt_in_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            source.write_bytes(b'label,n\n"hello\nworld",1\n"hello\nworld",1\n')
            counts = clean(source, root / "out", numeric_columns=["n"])
            self.assertEqual(counts["kept_rows"], 2)
            with (root / "out" / "cleaned.csv").open(newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[1], ["hello\nworld", "1"])


if __name__ == "__main__":
    unittest.main()
