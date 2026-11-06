import pandas as pd

def load_csv_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """Reads the CSV file, skips comments, drops extra metadata, and maps columns."""
    df = pd.read_csv(filepath, sep=";", encoding="cp1252", skiprows=2)
    
    column_mapping = manifest.get("files", {}).get("country_records.csv", {}).get("source_to_canonical", {})
    df = df.rename(columns=column_mapping)
    
    canonical_order = manifest.get("canonical_order", [])
    missing = [col for col in canonical_order if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required canonical columns in CSV: {missing}")
        
    return df[canonical_order]

def load_excel_records(filepath: str, manifest: dict) -> pd.DataFrame:
    """Reads the Excel observations sheet and maps columns to canonical names."""
    df = pd.read_excel(filepath, sheet_name="observations")
    
    column_mapping = manifest.get("files", {}).get("country_records.xlsx", {}).get("source_to_canonical", {})
    df = df.rename(columns=column_mapping)
    
    canonical_order = manifest.get("canonical_order", [])
    missing = [col for col in canonical_order if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required canonical columns in Excel: {missing}")
        
    return df[canonical_order]
