import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.export_roundtrip import (
    EXPORTS,
    ExportComparisonError,
    compare_canonical_export,
    export_canonical_formats,
    verify_canonical_round_trips,
)
from src.readers import load_csv_records
from src.validation import validate_and_quarantine


class TestCanonicalExportRoundTrips(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Load the manifest and recover a clean canonical reference table."""
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.manifest = json.loads(
            (cls.project_root / "data" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        raw_df = load_csv_records(
            cls.project_root / "data" / "country_records.csv",
            cls.manifest,
        )
        cls.canonical_df, cls.quarantine_df = validate_and_quarantine(
            raw_df, cls.manifest
        )

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name) / "outputs"
        export_canonical_formats(self.canonical_df, self.output_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_exports_all_formats_and_verifies_round_trips(self) -> None:
        """Export and reload CSV, Excel, JSON, and Parquet without an index."""
        self.assertEqual(
            set(path.name for path in self.output_dir.iterdir()),
            set(EXPORTS.values()),
        )
        report = verify_canonical_round_trips(
            self.canonical_df, self.output_dir, self.manifest
        )
        self.assertTrue(report["pass"].all())
        self.assertEqual(set(report["file"]), set(EXPORTS.values()))
        self.assertEqual(len(self.canonical_df), 1704)
        for path in self.output_dir.iterdir():
            if path.suffix == ".csv":
                reloaded = pd.read_csv(path)
            elif path.suffix == ".xlsx":
                reloaded = pd.read_excel(path, sheet_name="observations")
            elif path.suffix == ".json":
                reloaded = pd.read_json(path, orient="records")
            else:
                reloaded = pd.read_parquet(path)
            self.assertEqual(list(reloaded.columns), self.manifest["canonical_order"])

    def test_round_trip_comparison_is_key_based_not_row_order_based(self) -> None:
        """Accept equivalent exports when their records have been reordered."""
        csv_path = self.output_dir / EXPORTS["csv"]
        reordered = pd.read_csv(csv_path).sample(
            frac=1, random_state=21
        ).reset_index(drop=True)
        reordered.to_csv(csv_path, index=False)

        report = verify_canonical_round_trips(
            self.canonical_df, self.output_dir, self.manifest
        )
        self.assertTrue(report["pass"].all())

    def test_corrupted_export_fails_with_a_report(self) -> None:
        """Reject a changed canonical value and expose the failing check."""
        csv_path = self.output_dir / EXPORTS["csv"]
        corrupted = pd.read_csv(csv_path)
        corrupted.loc[0, "lifeExp"] += 1
        corrupted.to_csv(csv_path, index=False)

        with self.assertRaises(ExportComparisonError) as context:
            verify_canonical_round_trips(
                self.canonical_df, self.output_dir, self.manifest
            )
        failures = context.exception.report
        self.assertFalse(failures["pass"].all())
        self.assertIn("values:lifeExp", failures.loc[~failures["pass"], "check"].tolist())

    def test_float_comparison_uses_absolute_tolerance_only(self) -> None:
        """Accept a float delta within 1e-8 and reject one beyond it."""
        expected = self.canonical_df.iloc[:1].copy()
        within_tolerance = expected.copy()
        within_tolerance.loc[within_tolerance.index[0], "lifeExp"] += 5e-9
        passed = compare_canonical_export(
            expected, within_tolerance, self.manifest, "within.csv"
        )
        self.assertTrue(passed["pass"].all())

        outside_tolerance = expected.copy()
        outside_tolerance.loc[outside_tolerance.index[0], "lifeExp"] += 2e-8
        failed = compare_canonical_export(
            expected, outside_tolerance, self.manifest, "outside.csv"
        )
        value_check = failed.loc[failed["check"] == "values:lifeExp"].iloc[0]
        self.assertFalse(value_check["pass"])
        self.assertEqual(value_check["tolerance"], 1e-8)

    def test_integer_values_and_missingness_are_compared_exactly(self) -> None:
        """Reject changed integer fields and newly missing values."""
        expected = self.canonical_df.iloc[:1].copy()
        changed_integer = expected.copy()
        changed_integer.loc[changed_integer.index[0], "pop"] += 1
        integer_report = compare_canonical_export(
            expected, changed_integer, self.manifest, "integer.csv"
        )
        population_check = integer_report.loc[
            integer_report["check"] == "values:pop"
        ].iloc[0]
        self.assertFalse(population_check["pass"])
        self.assertEqual(population_check["tolerance"], 0)

        missing_float = expected.copy()
        missing_float.loc[missing_float.index[0], "lifeExp"] = np.nan
        missing_report = compare_canonical_export(
            expected, missing_float, self.manifest, "missing.csv"
        )
        life_check = missing_report.loc[
            missing_report["check"] == "values:lifeExp"
        ].iloc[0]
        self.assertFalse(life_check["pass"])


if __name__ == "__main__":
    unittest.main()
