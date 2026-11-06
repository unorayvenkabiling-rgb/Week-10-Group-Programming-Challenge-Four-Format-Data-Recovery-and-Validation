import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src import pipeline
from src.readers import load_csv_records
from src.validation import validate_and_quarantine


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestRequiredFailureCategories(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data_dir = PROJECT_ROOT / "data"
        cls.manifest = json.loads(
            (cls.data_dir / "manifest.json").read_text(encoding="utf-8")
        )
        cls.raw_csv = load_csv_records(
            cls.data_dir / "country_records.csv", cls.manifest
        )
        cls.valid_row = cls.raw_csv.iloc[[0]].copy().reset_index(drop=True)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.output_dir = self.root / "outputs"
        self.manifest_path = self.root / "manifest.json"
        self.config_path = self.root / "config.json"
        self.config = {
            "data_folder": str(self.data_dir),
            "manifest_file": str(self.manifest_path),
            "csv_file": "country_records.csv",
            "excel_file": "country_records.xlsx",
            "json_file": "country_records.json",
            "parquet_file": "country_records.parquet",
            "reporting_year": 2007,
            "output_folder": str(self.output_dir),
        }
        self.write_manifest(self.manifest)
        self.write_config()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_manifest(self, manifest: dict) -> None:
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def write_config(self) -> None:
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def assert_pipeline_failure_is_retained(self) -> pd.DataFrame:
        """Check a file-level failure exits nonzero and retains its report."""
        self.assertEqual(pipeline.run_pipeline(self.config_path), 1)
        self.assertFalse(self.output_dir.exists())
        report_files = list(
            (self.root / ".outputs.staging").glob("run-*/validation_failed.csv")
        )
        self.assertEqual(len(report_files), 1)
        report = pd.read_csv(report_files[0])
        self.assertEqual(
            list(report.columns),
            ["check", "expected", "actual", "tolerance", "pass"],
        )
        self.assertFalse(report.loc[report["check"] == "processing", "pass"].iloc[0])
        return report

    def test_missing_input_file_stops_pipeline(self) -> None:
        self.config["csv_file"] = "missing-input.csv"
        self.write_config()

        report = self.assert_pipeline_failure_is_retained()

        self.assertIn("FileNotFoundError", report.iloc[-1]["actual"])

    def test_unsupported_format_stops_pipeline(self) -> None:
        manifest = json.loads(json.dumps(self.manifest))
        manifest["files"][0]["file"] = "unsupported.txt"
        manifest["files"][0]["format"] = "txt"
        self.assertTrue((self.data_dir / "unsupported.txt").is_file())
        self.write_manifest(manifest)

        report = self.assert_pipeline_failure_is_retained()

        self.assertIn("Unsupported or invalid manifest input", report.iloc[-1]["actual"])

    def test_missing_required_column_stops_pipeline(self) -> None:
        manifest = json.loads(json.dumps(self.manifest))
        manifest["files"][0]["source_to_canonical"]["CountryName"] = "not_country"
        self.write_manifest(manifest)

        report = self.assert_pipeline_failure_is_retained()

        self.assertIn("Missing required canonical columns", report.iloc[-1]["actual"])

    def test_missing_key_value_is_quarantined(self) -> None:
        invalid = self.valid_row.copy()
        invalid.loc[0, "country"] = "   "

        clean, quarantine = validate_and_quarantine(invalid, self.manifest)

        self.assertTrue(clean.empty)
        self.assertEqual(len(quarantine), 1)
        self.assertIn("country must be nonempty", quarantine.iloc[0]["quarantine_reason"])

    def test_unparseable_number_is_quarantined(self) -> None:
        invalid = self.valid_row.copy()
        invalid["lifeExp"] = invalid["lifeExp"].astype(object)
        invalid.loc[0, "lifeExp"] = "not-a-number"

        clean, quarantine = validate_and_quarantine(invalid, self.manifest)

        self.assertTrue(clean.empty)
        self.assertEqual(len(quarantine), 1)
        self.assertIn("lifeExp must be finite", quarantine.iloc[0]["quarantine_reason"])

    def test_fractional_year_and_population_are_quarantined(self) -> None:
        fractional_year = self.valid_row.copy()
        fractional_year["year"] = fractional_year["year"].astype(object)
        fractional_year.loc[0, "year"] = 2007.5
        fractional_population = self.valid_row.copy()
        fractional_population["pop"] = fractional_population["pop"].astype(object)
        fractional_population.loc[0, "pop"] = 100.5

        clean, quarantine = validate_and_quarantine(
            pd.concat([fractional_year, fractional_population], ignore_index=True),
            self.manifest,
        )

        self.assertTrue(clean.empty)
        self.assertEqual(len(quarantine), 2)
        reasons = quarantine["quarantine_reason"].tolist()
        self.assertTrue(any("year must be finite, integral" in reason for reason in reasons))
        self.assertTrue(any("pop must be finite, integral" in reason for reason in reasons))

    def test_non_finite_and_out_of_range_values_are_quarantined(self) -> None:
        non_finite = self.valid_row.copy()
        non_finite.loc[0, "lifeExp"] = float("inf")
        out_of_range = self.valid_row.copy()
        out_of_range.loc[0, "lifeExp"] = 121

        clean, quarantine = validate_and_quarantine(
            pd.concat([non_finite, out_of_range], ignore_index=True),
            self.manifest,
        )

        self.assertTrue(clean.empty)
        self.assertEqual(len(quarantine), 2)
        self.assertTrue(
            quarantine["quarantine_reason"]
            .str.contains("lifeExp must be finite and greater than 0 and at most 120")
            .all()
        )

    def test_exact_duplicate_copy_is_removed_and_logged(self) -> None:
        duplicated = pd.concat([self.valid_row, self.valid_row], ignore_index=True)

        clean, quarantine = validate_and_quarantine(duplicated, self.manifest)
        duplicate_log = pipeline._duplicate_log(
            duplicated, self.manifest, "synthetic.csv"
        )

        self.assertEqual(len(clean), 1)
        self.assertTrue(quarantine.empty)
        self.assertEqual(len(duplicate_log), 1)
        self.assertEqual(duplicate_log.iloc[0]["source_record"], 2)
        self.assertEqual(duplicate_log.iloc[0]["duplicate_of_source_record"], 1)


if __name__ == "__main__":
    unittest.main()
