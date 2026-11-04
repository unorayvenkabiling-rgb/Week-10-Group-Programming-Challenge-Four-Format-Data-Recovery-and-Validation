import pandas as pd
import json

def load_parquet_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """
    Reads the Parquet file and maps its string columns to the canonical names defined in the manifest.
    """
    # Extract the parquet column mapping from the manifest dictionary
    column_mapping = manifest["format_settings"]["parquet"]["column_mapping"]
    
    # Load the parquet file
    df = pd.read_parquet(filepath)
    
    # Rename columns to canonical format
    df = df.rename(columns=column_mapping)
    
    # Ensure the canonical column order
    canonical_order = manifest["schema"]["canonical_columns"]
    df = df[canonical_order]
    
    return df

def load_json_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """
    Reads the JSON file, extracts the nested records from the metadata object, 
    and maps columns to canonical names.
    """
    column_mapping = manifest["format_settings"]["json"]["column_mapping"]
    
    # Load the raw JSON
    with open(filepath, 'r') as file:
        raw_data = json.load(file)
        
    # Extract the nested records (the dataset contains a 'records' key for the actual data)
    records = raw_data.get("records", [])
    
    # Flatten into a DataFrame
    df = pd.json_normalize(records)
    
    # Rename and reorder columns
    df = df.rename(columns=column_mapping)
    canonical_order = manifest["schema"]["canonical_columns"]
    df = df[canonical_order]
    
    return df