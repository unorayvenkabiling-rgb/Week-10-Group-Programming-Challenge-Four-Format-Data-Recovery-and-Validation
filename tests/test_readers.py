import json
import unittest
from pathlib import Path

from src.readers import load_csv_records, load_excel_records


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestFormatReaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest_path = PROJECT_ROOT / "data" / "manifest.json"
        with manifest_path.open(encoding="utf-8") as file:
            cls.manifest = json.load(file)
        cls.canonical_columns = cls.manifest["canonical_order"]

    def test_csv_reader_normalizes_manifest_columns(self) -> None:
        filepath = PROJECT_ROOT / "data" / "country_records.csv"
        records = load_csv_records(str(filepath), self.manifest)

        self.assertEqual(len(records), 1712)
        self.assertEqual(list(records.columns), self.canonical_columns)

    def test_excel_reader_normalizes_manifest_columns(self) -> None:
        filepath = PROJECT_ROOT / "data" / "country_records.xlsx"
        records = load_excel_records(str(filepath), self.manifest)

        self.assertEqual(len(records), 1712)
        self.assertEqual(list(records.columns), self.canonical_columns)

    def test_csv_reader_rejects_missing_canonical_column(self) -> None:
        filepath = PROJECT_ROOT / "data" / "country_records.csv"
        manifest = {
            **self.manifest,
            "canonical_order": [*self.canonical_columns, "MISSING_COLUMN"],
        }

        with self.assertRaisesRegex(KeyError, "MISSING_COLUMN"):
            load_csv_records(str(filepath), manifest)

    def test_excel_reader_rejects_missing_canonical_column(self) -> None:
        filepath = PROJECT_ROOT / "data" / "country_records.xlsx"
        manifest = {
            **self.manifest,
            "canonical_order": [*self.canonical_columns, "MISSING_COLUMN"],
        }

        with self.assertRaisesRegex(KeyError, "MISSING_COLUMN"):
            load_excel_records(str(filepath), manifest)


if __name__ == "__main__":
    unittest.main()
