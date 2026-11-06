import os
import unittest
import pandas as pd
from src.validation import validate_and_quarantine, ValidationError

class TestMember3Validation(unittest.TestCase):

    def setUp(self):
        self.manifest = {
            "canonical_order": ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"],
            "key": ["country", "year"],
            "allowed_continents": ["Africa", "Americas", "Asia", "Europe", "Oceania"],
            "allowed_years": [1952, 1957, 1962, 1967, 1972, 1977, 1982, 1987, 1992, 1997, 2002, 2007]
        }

    def test_conflicting_key_file_raises_error(self):
        # Path to conflicting_key.csv in data/ directory
        filepath = os.path.join("data", "conflicting_key.csv")
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            with self.assertRaises(ValidationError):
                validate_and_quarantine(df, self.manifest)

    def test_missing_column_file_raises_error(self):
        # Path to missing_column.csv in data/ directory
        filepath = os.path.join("data", "missing_column.csv")
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            with self.assertRaises(ValidationError):
                validate_and_quarantine(df, self.manifest)

    def test_valid_records(self):
        data = {
            "country": ["Philippines", "Japan"],
            "continent": ["Asia", "Asia"],
            "year": [2007, 2007],
            "lifeExp": [71.6, 82.6],
            "pop": [91077287, 127467972],
            "gdpPercap": [3190.1, 31656.0]
        }
        df = pd.DataFrame(data)
        valid_df, quarantine_df = validate_and_quarantine(df, self.manifest)
        self.assertEqual(len(valid_df), 2)
        self.assertEqual(len(quarantine_df), 0)

    def test_quarantine_invalid_records(self):
        data = {
            "country": ["Philippines", "BadCountry", "BadContinent"],
            "continent": ["Asia", "Asia", "Atlantis"],
            "year": [2007.5, 2007, 2007],
            "lifeExp": [71.6, 150.0, 70.0],
            "pop": [91077287, 1000, 1000],
            "gdpPercap": [3190.1, 5000.0, 5000.0]
        }
        df = pd.DataFrame(data)
        valid_df, quarantine_df = validate_and_quarantine(df, self.manifest)
        self.assertEqual(len(valid_df), 0)
        self.assertEqual(len(quarantine_df), 3)

if __name__ == "__main__":
    unittest.main()