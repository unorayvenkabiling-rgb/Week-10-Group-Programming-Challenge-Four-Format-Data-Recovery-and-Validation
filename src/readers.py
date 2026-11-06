from pathlib import Path

import pandas as pd


def _file_config(manifest: dict, filename: str) -> dict:
    """Return one file's settings from either supported manifest shape."""
    files = manifest.get("files", [])
    if isinstance(files, dict):
        config = files.get(filename, {})
    else:
        config = next(
            (
                item
                for item in files
                if isinstance(item, dict) and item.get("file") == filename
            ),
            {},
        )
    if not isinstance(config, dict):
        raise ValueError(f"Invalid manifest settings for {filename}.")
    return config


def _normalize_columns(
    df: pd.DataFrame, manifest: dict, filename: str, format_name: str
) -> pd.DataFrame:
    """Map and return the required canonical columns for an input file."""
    file_config = _file_config(manifest, filename)
    column_mapping = file_config.get("source_to_canonical", {})
    df = df.rename(columns=column_mapping)

    canonical_order = manifest.get("canonical_order", [])
    missing = [col for col in canonical_order if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required canonical columns in {format_name}: {missing}")

    result = df[canonical_order].copy()
    for column in result.columns:
        result[column] = result[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
    return result


def load_csv_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """Read, map, and normalize the configured CSV records."""
    filename = Path(filepath).name
    file_config = _file_config(manifest, filename)
    df = pd.read_csv(
        filepath,
        sep=file_config.get("separator", ";"),
        encoding=file_config.get("encoding", "cp1252"),
        skiprows=file_config.get("skiprows", 2),
    )
    return _normalize_columns(df, manifest, filename, "CSV")

def load_excel_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """Read, map, and normalize the configured Excel observation sheet."""
    file_config = _file_config(manifest, "country_records.xlsx")
    df = pd.read_excel(
        filepath,
        sheet_name=file_config.get("sheet_name", "observations"),
        engine=file_config.get("engine"),
    )
    return _normalize_columns(df, manifest, "country_records.xlsx", "Excel")
