from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EXPORTS: dict[str, str] = {
    "csv": "canonical.csv",
    "xlsx": "canonical.xlsx",
    "json": "canonical.json",
    "parquet": "canonical.parquet",
}
CANONICAL_COLUMNS = [
    "country",
    "continent",
    "year",
    "lifeExp",
    "pop",
    "gdpPercap",
]
FLOAT_TOLERANCE = 1e-8


class ExportComparisonError(ValueError):
    """Raised when an exported canonical table fails its round-trip checks."""

    def __init__(self, report: pd.DataFrame) -> None:
        self.report = report
        failures = report.loc[~report["pass"], ["file", "check", "actual"]]
        super().__init__(
            "Canonical export round-trip verification failed:\n"
            + failures.to_string(index=False)
        )


def export_canonical_formats(
    canonical_df: pd.DataFrame, output_dir: str | Path
) -> dict[str, Path]:
    """Export the six canonical columns to all required file formats."""
    if list(canonical_df.columns) != CANONICAL_COLUMNS:
        raise ValueError(
            f"Canonical export columns must be ordered as {CANONICAL_COLUMNS}."
        )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    exports = {
        name: output_path / filename for name, filename in EXPORTS.items()
    }

    canonical_df.to_csv(exports["csv"], index=False)
    canonical_df.to_excel(
        exports["xlsx"], sheet_name="observations", index=False
    )
    canonical_df.to_json(
        exports["json"],
        orient="records",
        force_ascii=False,
        double_precision=15,
    )
    canonical_df.to_parquet(exports["parquet"], index=False)
    return exports


def _read_export(path: Path, format_name: str) -> pd.DataFrame:
    """Read one canonical export without applying inferred schema casts."""
    if format_name == "csv":
        return pd.read_csv(path, dtype="string")
    if format_name == "xlsx":
        return pd.read_excel(path, sheet_name="observations")
    if format_name == "json":
        return pd.read_json(path, orient="records")
    if format_name == "parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported canonical export format: {format_name}")


def _normalize_frame(
    frame: pd.DataFrame, manifest: dict[str, Any]
) -> pd.DataFrame:
    """Apply manifest column order and strict canonical types.

    CSV is read as strings, so its declared numeric fields require explicit
    conversion. Excel and JSON infer numeric values on load; Parquet preserves
    stored types. All formats are normalized here for a consistent comparison.
    """
    columns = manifest["canonical_order"]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing canonical columns: {missing}")
    if list(frame.columns) != columns:
        raise ValueError(
            f"Canonical columns must be in order {columns}; received {list(frame.columns)}."
        )

    schema = manifest["canonical_schema"]
    normalized = frame.loc[:, columns].copy()
    for column in columns:
        dtype = schema[column]
        values = normalized[column]
        if dtype == "string":
            normalized[column] = values.astype("string")
        elif dtype in ("int64", "int"):
            numeric = pd.to_numeric(values, errors="raise")
            nonmissing = numeric.dropna().to_numpy(dtype=float)
            if not np.isfinite(nonmissing).all() or not np.equal(
                np.mod(nonmissing, 1), 0
            ).all():
                raise ValueError(
                    f"Column {column!r} contains non-finite or fractional integers."
                )
            if numeric.isna().any():
                normalized[column] = numeric.astype("Int64")
            else:
                normalized[column] = numeric.astype("int64")
        elif dtype in ("float64", "float"):
            numeric = pd.to_numeric(values, errors="raise").astype("float64")
            nonmissing = numeric.dropna().to_numpy(dtype=float)
            if not np.isfinite(nonmissing).all():
                raise ValueError(f"Column {column!r} contains non-finite floats.")
            normalized[column] = numeric
        else:
            raise ValueError(
                f"Unsupported canonical type {dtype!r} for column {column!r}."
            )
    return normalized


def compare_canonical_export(
    expected: pd.DataFrame,
    actual: pd.DataFrame,
    manifest: dict[str, Any],
    filename: str,
) -> pd.DataFrame:
    """Compare canonical exports by key with schema-specific exactness."""
    rows: list[dict[str, object]] = []

    def add(check: str, passed: bool, expected_value: object, actual_value: object,
            tolerance: object = 0) -> None:
        rows.append(
            {
                "file": filename,
                "check": check,
                "expected": expected_value,
                "actual": actual_value,
                "tolerance": tolerance,
                "pass": bool(passed),
            }
        )

    try:
        expected_normalized = _normalize_frame(expected, manifest)
        actual_normalized = _normalize_frame(actual, manifest)
    except (TypeError, ValueError, KeyError) as exc:
        add("schema_and_types", False, "manifest canonical schema", str(exc))
        return pd.DataFrame(rows)

    columns = manifest["canonical_order"]
    add(
        "row_count",
        len(expected_normalized) == len(actual_normalized),
        len(expected_normalized),
        len(actual_normalized),
    )
    add(
        "columns",
        list(expected.columns) == list(actual.columns) == columns,
        columns,
        list(actual.columns),
    )

    key_columns = manifest["key"]
    if any(column not in columns for column in key_columns):
        add("key_schema", False, "keys in canonical schema", key_columns)
        return pd.DataFrame(rows)

    expected_keys = expected_normalized[key_columns]
    actual_keys = actual_normalized[key_columns]
    expected_unique = not expected_keys.duplicated().any()
    actual_unique = not actual_keys.duplicated().any()
    add("unique_keys", expected_unique and actual_unique, True, actual_unique)

    try:
        expected_index = pd.MultiIndex.from_frame(expected_keys)
        actual_index = pd.MultiIndex.from_frame(actual_keys)
        same_keys = (
            expected_unique
            and actual_unique
            and len(expected_index) == len(actual_index)
            and expected_index.difference(actual_index).empty
            and actual_index.difference(expected_index).empty
        )
    except (TypeError, ValueError) as exc:
        add("key_set", False, "same key set", str(exc))
        return pd.DataFrame(rows)
    add("key_set", same_keys, len(expected_index), len(actual_index))
    if not same_keys:
        return pd.DataFrame(rows)

    actual_positions = {
        key: position for position, key in enumerate(actual_index.tolist())
    }
    aligned_positions = [
        actual_positions[key] for key in expected_index.tolist()
    ]
    aligned = actual_normalized.iloc[aligned_positions].reset_index(drop=True)
    expected_normalized = expected_normalized.reset_index(drop=True)

    key_set = set(key_columns)
    schema = manifest["canonical_schema"]
    for column in columns:
        if column in key_set:
            continue
        expected_values = expected_normalized[column]
        actual_values = aligned[column]
        same_missingness = expected_values.isna().equals(actual_values.isna())
        dtype = schema[column]
        tolerance = FLOAT_TOLERANCE if dtype in ("float64", "float") else 0
        if dtype == "string":
            equal_values = expected_values.fillna("").equals(
                actual_values.fillna("")
            )
        elif dtype in ("int64", "int"):
            equal_values = expected_values.fillna(0).equals(
                actual_values.fillna(0)
            )
        else:
            left = expected_values.to_numpy(dtype=float, na_value=np.nan)
            right = actual_values.to_numpy(dtype=float, na_value=np.nan)
            compared = ~np.isnan(left)
            equal_values = bool(
                np.isclose(
                    left[compared],
                    right[compared],
                    rtol=0,
                    atol=FLOAT_TOLERANCE,
                ).all()
            )
        add(
            f"values:{column}",
            same_missingness and bool(equal_values),
            "exact" if tolerance == 0 else "absolute tolerance",
            "match" if same_missingness and equal_values else "mismatch",
            tolerance,
        )
    return pd.DataFrame(rows)


def verify_canonical_round_trips(
    canonical_df: pd.DataFrame,
    output_dir: str | Path,
    manifest: dict[str, Any],
) -> pd.DataFrame:
    """Reload and compare every canonical export, raising on any mismatch."""
    output_path = Path(output_dir)
    reports = []
    for format_name, filename in EXPORTS.items():
        path = output_path / filename
        if not path.is_file():
            report = pd.DataFrame(
                [
                    {
                        "file": filename,
                        "check": "file_exists",
                        "expected": True,
                        "actual": False,
                        "tolerance": 0,
                        "pass": False,
                    }
                ]
            )
        else:
            try:
                reloaded = _read_export(path, format_name)
            except (OSError, ValueError, ImportError) as exc:
                report = pd.DataFrame(
                    [
                        {
                            "file": filename,
                            "check": "reload",
                            "expected": "readable export",
                            "actual": str(exc),
                            "tolerance": 0,
                            "pass": False,
                        }
                    ]
                )
            else:
                report = compare_canonical_export(
                    canonical_df, reloaded, manifest, filename
                )
        reports.append(report)

    combined = pd.concat(reports, ignore_index=True)
    if not combined["pass"].all():
        raise ExportComparisonError(combined)
    return combined
