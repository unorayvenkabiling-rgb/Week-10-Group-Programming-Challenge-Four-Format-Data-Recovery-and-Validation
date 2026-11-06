import math
import pandas as pd
import numpy as np

class ValidationError(Exception):
    """Custom exception raised when critical errors occur (missing schema columns, conflicting keys)."""
    pass


def validate_row(row: pd.Series, manifest: dict) -> list[str]:
    """Validates a single record against manifest rules."""
    reasons = []
    allowed_continents = set(manifest.get("allowed_continents", []))
    allowed_years = set(manifest.get("allowed_years", []))

    # 1. Country validation
    country = str(row.get("country", "")).strip() if pd.notna(row.get("country")) else ""
    if not country:
        reasons.append("country must be nonempty after trimming")

    # 2. Continent validation
    continent = str(row.get("continent", "")).strip() if pd.notna(row.get("continent")) else ""
    if not continent or continent not in allowed_continents:
        reasons.append("continent must be nonempty and in the allowed set")

    # 3. Year validation
    val_year = row.get("year")
    try:
        f_year = float(val_year)
        if math.isnan(f_year) or math.isinf(f_year) or not f_year.is_integer() or int(f_year) not in allowed_years:
            reasons.append("year must be finite, integral and in allowed_years")
    except (ValueError, TypeError):
        reasons.append("year must be finite, integral and in allowed_years")

    # 4. lifeExp validation
    val_life = row.get("lifeExp")
    try:
        f_life = float(val_life)
        if math.isnan(f_life) or math.isinf(f_life) or f_life <= 0 or f_life > 120:
            reasons.append("lifeExp must be finite and greater than 0 and at most 120")
    except (ValueError, TypeError):
        reasons.append("lifeExp must be finite and greater than 0 and at most 120")

    # 5. Pop validation
    val_pop = row.get("pop")
    try:
        f_pop = float(val_pop)
        if math.isnan(f_pop) or math.isinf(f_pop) or not f_pop.is_integer() or f_pop <= 0:
            reasons.append("pop must be finite, integral and greater than 0")
    except (ValueError, TypeError):
        reasons.append("pop must be finite, integral and greater than 0")

    # 6. gdpPercap validation
    val_gdp = row.get("gdpPercap")
    try:
        f_gdp = float(val_gdp)
        if math.isnan(f_gdp) or math.isinf(f_gdp) or f_gdp <= 0:
            reasons.append("gdpPercap must be finite and greater than 0")
    except (ValueError, TypeError):
        reasons.append("gdpPercap must be finite and greater than 0")

    return reasons


def validate_and_quarantine(df: pd.DataFrame, manifest: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validates normalized records.
    - Checks schema for missing columns.
    - Quarantines rows with invalid attributes.
    - Removes exact duplicates.
    - Raises ValidationError on conflicting primary keys.
    """
    canonical_cols = manifest["canonical_order"]
    key_cols = manifest["key"]

    # 1. Schema Check: Stop processing if required canonical columns are missing
    missing_cols = [col for col in canonical_cols if col not in df.columns]
    if missing_cols:
        raise ValidationError(f"Missing required canonical column(s): {missing_cols}")

    valid_records = []
    quarantine_records = []

    # 2. Row Validation
    for idx, row in df.iterrows():
        reasons = validate_row(row, manifest)
        row_dict = row.to_dict()
        if reasons:
            row_dict["quarantine_reason"] = "; ".join(reasons)
            quarantine_records.append(row_dict)
        else:
            row_dict["year"] = int(float(row_dict["year"]))
            row_dict["pop"] = int(float(row_dict["pop"]))
            row_dict["lifeExp"] = float(row_dict["lifeExp"])
            row_dict["gdpPercap"] = float(row_dict["gdpPercap"])
            valid_records.append(row_dict)

    quarantine_df = pd.DataFrame(quarantine_records)
    
    if not valid_records:
        return pd.DataFrame(columns=canonical_cols), quarantine_df

    valid_df = pd.DataFrame(valid_records)[canonical_cols]

    # 3. Deduplication: Remove exact duplicate rows
    exact_dups = valid_df.duplicated(keep="first")
    valid_dedup_df = valid_df[~exact_dups].copy()

    # 4. Conflicting Keys Check: Same key, different data
    key_dups = valid_dedup_df.duplicated(subset=key_cols, keep=False)
    if key_dups.any():
        conflicting = valid_dedup_df[key_dups]
        raise ValidationError(
            f"Conflicting keys detected! Primary keys {key_cols} must be unique.\n"
            f"Conflicting entries:\n{conflicting[key_cols + ['lifeExp', 'pop', 'gdpPercap']]}"
        )

    return valid_dedup_df.reset_index(drop=True), quarantine_df