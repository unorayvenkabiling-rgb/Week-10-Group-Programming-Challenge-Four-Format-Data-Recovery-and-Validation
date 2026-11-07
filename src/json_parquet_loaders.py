import pandas as pd
import json

from .readers import _file_config, _normalize_columns


def load_parquet_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """
    Read and map Parquet records while preserving values for validation.
    """
    _file_config(manifest, "country_records.parquet")
    df = pd.read_parquet(filepath)
    return _normalize_columns(
        df, manifest, "country_records.parquet", "Parquet"
    )

def load_json_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """
    Read nested JSON records, map them, and preserve values for validation.
    """
    file_config = _file_config(manifest, "country_records.json")
    try:
        with open(filepath, "r", encoding=file_config.get("encoding", "utf-8")) as file:
            raw_data = json.load(file)
    except json.JSONDecodeError:
        raise ValueError(f"File {filepath} contains unparseable JSON data.")

    record_path = file_config.get("record_path", "records")
    if not isinstance(raw_data, dict):
        raise ValueError(f"File {filepath} must contain a JSON object.")
    records = raw_data.get(record_path, [])
    if not isinstance(records, list):
        raise ValueError(f"JSON field {record_path!r} in {filepath} must be a list.")
    df = pd.json_normalize(records)
    return _normalize_columns(df, manifest, "country_records.json", "JSON")
