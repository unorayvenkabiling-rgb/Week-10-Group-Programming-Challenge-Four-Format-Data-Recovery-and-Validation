import unittest
import json
from src.json_parquet_loaders import load_parquet_records, load_json_records

class TestMember2Loaders(unittest.TestCase):
    
    def setUp(self):
        # Load the manifest once for the tests
        with open("data/manifest.json", "r") as f:
            self.manifest = json.load(f)
            
        self.canonical_columns = self.manifest["schema"]["canonical_columns"]

    def test_missing_file(self):
        """Test that a missing file raises the correct FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            load_parquet_records("data/does_not_exist.parquet", self.manifest)
            
    def test_parquet_normalization(self):
        """Test that the Parquet loader returns exactly the 6 canonical columns."""
        df = load_parquet_records("data/country_records.parquet", self.manifest)
        self.assertEqual(list(df.columns), self.canonical_columns)

    def test_json_normalization(self):
        """Test that the JSON loader returns exactly the 6 canonical columns."""
        df = load_json_records("data/country_records.json", self.manifest)
        self.assertEqual(list(df.columns), self.canonical_columns)

if __name__ == "__main__":
    unittest.main()