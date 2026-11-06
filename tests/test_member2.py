import unittest
import json
import pandas as pd
from src.json_parquet_loaders import load_parquet_records, load_json_records

class TestMember2Loaders(unittest.TestCase):
    
    def setUp(self):
        with open("data/manifest.json", "r") as f:
            self.manifest = json.load(f)
            
        # Extracted directly from the root level to fix the KeyError in setUp
        self.canonical_columns = self.manifest.get("canonical_order", [])

    def test_missing_file(self):
        """Test that a missing file raises the correct FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            load_parquet_records("data/does_not_exist.parquet", self.manifest)
            
    def test_parquet_normalization_and_count(self):
        """Test Parquet loader returns exactly 1,712 rows and maps columns correctly."""
        df = load_parquet_records("data/country_records.parquet", self.manifest)
        self.assertEqual(len(df), 1712)
        self.assertEqual(list(df.columns), self.canonical_columns)

    def test_json_normalization_and_count(self):
        """Test JSON loader returns exactly 1,712 rows and maps columns correctly."""
        df = load_json_records("data/country_records.json", self.manifest)
        self.assertEqual(len(df), 1712)
        self.assertEqual(list(df.columns), self.canonical_columns)
        
    def test_missing_column_rejection(self):
        """Test that a file missing a required canonical column raises a KeyError."""
        # Mock manifest expecting a column that does not exist
        bad_manifest = {"canonical_order": ["country", "continent", "year", "FAKE_COLUMN"]}
        
        with self.assertRaises(KeyError):
             load_parquet_records("data/country_records.parquet", bad_manifest)

    def test_unparseable_json_rejection(self):
        """Test that unparseable or corrupt JSON inputs raise a ValueError."""
        # Tests the JSONDecodeError try-except block using the task's failure fixture
        with self.assertRaises(ValueError):
             load_json_records("data/unsupported.txt", self.manifest)

if __name__ == "__main__":
    unittest.main()