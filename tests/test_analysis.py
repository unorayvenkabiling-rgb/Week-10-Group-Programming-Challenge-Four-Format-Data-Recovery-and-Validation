import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis import (
    compute_asia_selection,
    compute_independent_asian_total,
    compute_numpy_population_matrix,
    compute_philippines_summary,
)
from src.validation import validate_and_quarantine


class TestMember4Analysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Load the clean project data and a small ranking fixture."""
        project_root = Path(__file__).resolve().parents[1]
        manifest_path = project_root / "data" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        csv_config = next(
            item
            for item in manifest["files"]
            if item["file"] == "country_records.csv"
        )
        raw_df = pd.read_csv(
            project_root / "data" / csv_config["file"],
            sep=csv_config["separator"],
            encoding=csv_config["encoding"],
            skiprows=2,
        )
        raw_df = raw_df.rename(
            columns=csv_config["source_to_canonical"]
        )[manifest["canonical_order"]]
        cls.real_df, cls.quarantine_df = validate_and_quarantine(
            raw_df, manifest
        )

    def test_asia_selection_matches_controls_and_reporting_year(self) -> None:
        """Check ranking, units, row counts, and configurable reporting year."""
        for year in (2007, 1997):
            with self.subTest(year=year):
                subset = compute_asia_selection(self.real_df, year=year)
                self.assertEqual(len(subset), 33)
                self.assertTrue(subset["continent"].str.casefold().eq("asia").all())
                self.assertTrue(subset["year"].eq(year).all())
                expected_ranks = subset["lifeExp"].rank(
                    ascending=False, method="min"
                ).astype(int)
                pd.testing.assert_series_equal(
                    subset["lifeExp_rank"], expected_ranks, check_names=False
                )
                expected_order = subset.sort_values(
                    ["lifeExp_rank", "country"]
                ).reset_index(drop=True)
                pd.testing.assert_frame_equal(subset, expected_order)
                np.testing.assert_allclose(
                    subset["pop_millions"],
                    subset["pop"] / 1_000_000,
                    rtol=0,
                    atol=1e-12,
                )

        self.assertEqual(
            compute_independent_asian_total(self.real_df, year=2007),
            3_811_953_827,
        )

    def test_asia_selection_uses_min_rank_for_ties(self) -> None:
        """Ensure tied life expectancies receive the minimum rank."""
        tied_df = pd.DataFrame(
            {
                "country": ["A", "B", "C"],
                "continent": ["Asia"] * 3,
                "year": [2007] * 3,
                "lifeExp": [80.0, 80.0, 70.0],
                "pop": [100, 200, 300],
            }
        )
        result = compute_asia_selection(tied_df)
        self.assertEqual(
            result.set_index("country")["lifeExp_rank"].to_dict(),
            {"A": 1, "B": 1, "C": 3},
        )

    def test_philippines_summary_matches_full_history(self) -> None:
        """Check Philippine observations and changes from the first year."""
        result = compute_philippines_summary(self.real_df)
        self.assertEqual(len(result), 12)
        self.assertTrue(result["year"].is_monotonic_increasing)
        self.assertEqual(int(result.iloc[0]["year"]), 1952)
        self.assertEqual(float(result.iloc[0]["lifeExp_change"]), 0.0)
        np.testing.assert_allclose(
            result["lifeExp_change"],
            result["lifeExp"] - result.iloc[0]["lifeExp"],
            rtol=0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            result["pop_millions"],
            result["pop"] / 1_000_000,
            rtol=0,
            atol=1e-12,
        )
        self.assertEqual(
            int(result.loc[result["year"] == 2007, "pop"].iloc[0]),
            91_077_287,
        )

    def test_numpy_population_matrix_and_independent_calculations(self) -> None:
        """Check the full matrix, index calculation, loop, and aggregation."""
        result = compute_numpy_population_matrix(self.real_df)
        expected_raw = (
            self.real_df.loc[
                self.real_df["country"].isin(result["countries"])
                & self.real_df["year"].isin(result["years"])
            ]
            .pivot(index="country", columns="year", values="pop")
            .reindex(index=result["countries"], columns=result["years"])
            .to_numpy(dtype=float)
        )
        expected_index = np.empty_like(expected_raw)
        for row_index in range(expected_raw.shape[0]):
            for column_index in range(expected_raw.shape[1]):
                expected_index[row_index, column_index] = (
                    expected_raw[row_index, column_index]
                    / expected_raw[row_index, 0]
                    * 100
                )

        self.assertEqual(result["shape_before"], (3, 6))
        self.assertEqual(result["shape_after"], (3, 6))
        np.testing.assert_array_equal(result["raw_matrix"], expected_raw)
        np.testing.assert_allclose(
            result["broadcasted_matrix"],
            expected_index,
            rtol=0,
            atol=1e-8,
        )
        np.testing.assert_array_equal(
            result["broadcasted_matrix"][:, 0],
            np.array([100.0, 100.0, 100.0]),
        )

        selected = expected_raw[:, -1] > 70_000_000
        expected_countries = np.array(result["countries"])[selected].tolist()
        self.assertEqual(result["filtered_countries_2007"], expected_countries)
        self.assertEqual(expected_countries, ["Philippines", "Indonesia"])
        self.assertEqual(
            result["mean_pop_large_countries_2007"],
            float(np.mean(expected_raw[selected, -1])),
        )

    def test_numpy_population_matrix_rejects_empty_boolean_selection(self) -> None:
        """Fail explicitly when the selected population group is empty."""
        rows = [
            {"country": country, "year": year, "pop": 10_000_000}
            for country in ("Philippines", "Indonesia", "Thailand")
            for year in (1982, 1987, 1992, 1997, 2002, 2007)
        ]
        with self.assertRaisesRegex(ValueError, "No 2007 populations"):
            compute_numpy_population_matrix(pd.DataFrame(rows))


if __name__ == "__main__":
    unittest.main()
