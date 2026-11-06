import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import main as pipeline
from src.readers import load_csv_records


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestPipelineCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.output_dir = self.root / "outputs"
        self.config_path = self.root / "config.json"
        self.config = {
            "data_folder": str(PROJECT_ROOT / "data"),
            "manifest_file": "manifest.json",
            "csv_file": "country_records.csv",
            "excel_file": "country_records.xlsx",
            "json_file": "country_records.json",
            "parquet_file": "country_records.parquet",
            "default_year": 2007,
            "output_folder": str(self.output_dir),
        }
        self.write_config()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_config(self) -> None:
        self.config_path.write_text(
            json.dumps(self.config), encoding="utf-8"
        )

    def test_cli_generates_validated_outputs_for_configured_year(self) -> None:
        """Run the documented CLI and verify the published reports and files."""
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "main.py"),
                "--config",
                str(self.config_path),
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("1704 canonical rows", completed.stdout)

        expected_files = {
            "canonical.csv",
            "canonical.xlsx",
            "canonical.json",
            "canonical.parquet",
            "asia_selected_year.csv",
            "country_history.csv",
            "population_index.csv",
            "quarantine.csv",
            "duplicate_log.csv",
            "validation.csv",
            "audit_log.csv",
        }
        self.assertEqual(
            {path.name for path in self.output_dir.iterdir()},
            expected_files,
        )
        validation = pd.read_csv(self.output_dir / "validation.csv")
        self.assertTrue(validation["pass"].all())
        self.assertEqual(len(pd.read_csv(self.output_dir / "quarantine.csv")), 24)
        self.assertEqual(len(pd.read_csv(self.output_dir / "duplicate_log.csv")), 8)
        quarantine = pd.read_csv(self.output_dir / "quarantine.csv")
        self.assertTrue(quarantine["source_record"].between(1, 1712).all())
        self.assertEqual(quarantine["source_record"].nunique(), 24)
        self.assertEqual(
            len(pd.read_csv(self.output_dir / "canonical.csv")), 1704
        )
        self.assertEqual(
            len(pd.read_csv(self.output_dir / "asia_selected_year.csv")), 33
        )
        audit = pd.read_csv(self.output_dir / "audit_log.csv")
        self.assertEqual(
            list(audit.columns),
            [
                "step",
                "source_file",
                "operation",
                "rule",
                "rows_before",
                "rows_after",
            ],
        )

    def test_configured_1997_analysis_does_not_edit_processing_code(self) -> None:
        """Changing only the reporting year regenerates the selected-year output."""
        self.config["default_year"] = 1997
        self.write_config()
        result = pipeline.run_pipeline(self.config_path)
        self.assertEqual(result, 0)
        asia = pd.read_csv(self.output_dir / "asia_selected_year.csv")
        self.assertTrue(asia["year"].eq(1997).all())
        self.assertEqual(len(asia), 33)

    def test_conflicting_input_fails_without_replacing_prior_outputs(self) -> None:
        """Keep old published files and retain a failed report on a key conflict."""
        self.output_dir.mkdir()
        sentinel = self.output_dir / "previous_success.txt"
        sentinel.write_text("keep prior successful outputs\n", encoding="utf-8")

        valid_df = load_csv_records(
            PROJECT_ROOT / "data" / "country_records.csv",
            json.loads(
                (PROJECT_ROOT / "data" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        first = valid_df.iloc[[0]].copy()
        conflict = first.copy()
        conflict.loc[conflict.index[0], "pop"] += 1
        conflicting_df = pd.concat([first, conflict], ignore_index=True)

        with patch.dict(
            pipeline.READERS,
            {"csv": lambda _path, _manifest: conflicting_df},
        ):
            result = pipeline.run_pipeline(self.config_path)

        self.assertEqual(result, 1)
        self.assertEqual(
            sentinel.read_text(encoding="utf-8"),
            "keep prior successful outputs\n",
        )
        self.assertFalse((self.output_dir / "canonical.csv").exists())
        staging_root = self.output_dir.parent / ".outputs.staging"
        failed_reports = list(staging_root.glob("run-*/validation_failed.csv"))
        self.assertEqual(len(failed_reports), 1)
        failure_report = pd.read_csv(failed_reports[0])
        processing_failure = failure_report.loc[
            failure_report["check"] == "processing", "actual"
        ].iloc[0]
        self.assertIn("Conflicting keys detected", processing_failure)

    def test_missing_manifest_retains_failure_report(self) -> None:
        """A failure before input processing still retains a validation report."""
        self.config["manifest_file"] = "missing-manifest.json"
        self.write_config()

        result = pipeline.run_pipeline(self.config_path)

        self.assertEqual(result, 1)
        staging_root = self.output_dir.parent / ".outputs.staging"
        failed_reports = list(staging_root.glob("run-*/validation_failed.csv"))
        self.assertEqual(len(failed_reports), 1)
        failure_report = pd.read_csv(failed_reports[0])
        processing_failure = failure_report.loc[
            failure_report["check"] == "processing", "actual"
        ].iloc[0]
        self.assertIn("FileNotFoundError", processing_failure)


if __name__ == "__main__":
    unittest.main()
