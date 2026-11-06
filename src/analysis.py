import numpy as np
import pandas as pd


def compute_asia_selection(df: pd.DataFrame, year: int = 2007) -> pd.DataFrame:
    """Select and rank Asian records for a reporting year."""
    continent = df["continent"].fillna("").astype(str).str.strip().str.casefold()
    mask = continent.eq("asia") & df["year"].eq(year)
    subset = df.loc[mask].copy()

    if subset.empty:
        raise ValueError(f"No records found for continent 'Asia' in year {year}.")

    subset["pop_millions"] = subset["pop"] / 1_000_000
    subset["lifeExp_rank"] = subset["lifeExp"].rank(
        ascending=False, method="min"
    ).astype(int)
    return subset.sort_values(
        by=["lifeExp_rank", "country"], ascending=[True, True]
    ).reset_index(drop=True)


def compute_philippines_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return Philippine observations with population and life-expectancy changes."""
    country = df["country"].fillna("").astype(str).str.strip().str.casefold()
    ph_df = df.loc[country.eq("philippines")].copy()

    if ph_df.empty:
        raise ValueError("No records found for 'Philippines'.")

    ph_df = ph_df.sort_values(by="year").reset_index(drop=True)
    ph_df["pop_millions"] = ph_df["pop"] / 1_000_000
    baseline_life_exp = ph_df.iloc[0]["lifeExp"]
    ph_df["lifeExp_change"] = ph_df["lifeExp"] - baseline_life_exp
    return ph_df


def compute_numpy_population_matrix(df: pd.DataFrame) -> dict[str, object]:
    """Build and verify the required NumPy population index matrix."""
    countries = ["Philippines", "Indonesia", "Thailand"]
    years = [1982, 1987, 1992, 1997, 2002, 2007]

    mask = df["country"].isin(countries) & df["year"].isin(years)
    filtered = df.loc[mask]
    pivot_df = filtered.pivot(
        index="country", columns="year", values="pop"
    ).reindex(index=countries, columns=years)
    if pivot_df.isna().any().any():
        raise ValueError("Missing values detected in NumPy matrix subset.")

    raw_matrix = pivot_df.to_numpy(dtype=float)
    if not np.isfinite(raw_matrix).all() or (raw_matrix[:, 0] <= 0).any():
        raise ValueError("Population matrix must contain finite values and positive baselines.")
    shape_before = raw_matrix.shape

    baseline_1982 = raw_matrix[:, 0:1]
    broadcasted_matrix = (raw_matrix / baseline_1982) * 100
    shape_after = broadcasted_matrix.shape

    loop_verified_matrix = np.empty_like(raw_matrix)
    for row_index in range(raw_matrix.shape[0]):
        baseline = raw_matrix[row_index, 0]
        for column_index in range(raw_matrix.shape[1]):
            loop_verified_matrix[row_index, column_index] = (
                raw_matrix[row_index, column_index] / baseline
            ) * 100

    if not np.allclose(
        broadcasted_matrix, loop_verified_matrix, rtol=0, atol=1e-8
    ):
        raise ArithmeticError("Broadcast result differs from the independent loop calculation.")

    year_2007_index = years.index(2007)
    selected_mask = raw_matrix[:, year_2007_index] > 70_000_000
    filtered_countries = np.array(countries)[selected_mask]
    selected_populations = raw_matrix[selected_mask, year_2007_index]
    if selected_populations.size == 0:
        raise ValueError("No 2007 populations exceed 70 million.")

    return {
        "countries": countries,
        "years": years,
        "raw_matrix": raw_matrix,
        "broadcasted_matrix": broadcasted_matrix,
        "shape_before": shape_before,
        "shape_after": shape_after,
        "filtered_countries_2007": filtered_countries.tolist(),
        "mean_pop_large_countries_2007": float(np.mean(selected_populations)),
    }


def compute_independent_asian_total(df: pd.DataFrame, year: int = 2007) -> int:
    """Compute an Asian population total using NumPy arrays."""
    mask = df["continent"].eq("Asia") & df["year"].eq(year)
    populations = df.loc[mask, "pop"].to_numpy(dtype=np.int64)
    return int(np.sum(populations))