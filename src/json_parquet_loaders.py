import pandas as pd
import json

def load_parquet_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """
    Reads the Parquet file and maps its string columns to the canonical names.
    Validates numeric values before casting.
    """
    # Extract mapping from the files dictionary as requested by Isaiah
    column_mapping = manifest.get("files", {}).get("country_records.parquet", {}).get("source_to_canonical", {})
    
    df = pd.read_parquet(filepath)
    df = df.rename(columns=column_mapping)
    
    # Strip whitespaces from object/string columns and attempt numeric casting
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()
            
    for num_col in ['year', 'pop', 'lifeExp', 'gdpPercap']:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors='ignore')
            
    canonical_order = manifest.get("canonical_order", [])
    
    # Validate canonical schema exists to prevent KeyError on indexing
    missing = [col for col in canonical_order if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required canonical columns: {missing}")
        
    return df[canonical_order]

def load_json_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """
    Reads the JSON file, extracts nested records, and maps columns to canonical names.
    """
    column_mapping = manifest.get("files", {}).get("country_records.json", {}).get("source_to_canonical", {})
    
    # Try-except block for resource cleanup and JSONDecodeError handling
    try:
        with open(filepath, 'r') as file:
            raw_data = json.load(file)
    except json.JSONDecodeError:
        raise ValueError(f"File {filepath} contains unparseable JSON data.")
        
    records = raw_data.get("records", [])
    df = pd.json_normalize(records)
    
    df = df.rename(columns=column_mapping)
    canonical_order = manifest.get("canonical_order", [])
    
    # Validate canonical schema exists
    missing = [col for col in canonical_order if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required canonical columns: {missing}")
        
    return df[canonical_order]