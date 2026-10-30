import pandas as pd
import json
import os

with open("config.json", "r") as f:
    config = json.load(f)

def read_csv_file():
    file_path = f"{config['data_folder']}/{config['csv_file']}"
    try:
        df_csv = pd.read_csv(file_path, sep=";", encoding="cp1252", skiprows=2)
        print("CSV file loaded successfully!")
        return df_csv
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return None

def read_excel_file():
    file_path = f"{config['data_folder']}/{config['excel_file']}"
    try:
        df_excel = pd.read_excel(file_path, sheet_name="observations")
        print("Excel file loaded successfully!")
        return df_excel
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return None

def check_files_exist():
    folder = config['data_folder']
    required_files = [config['csv_file'], config['excel_file']]
    
    for filename in required_files:
        full_path = os.path.join(folder, filename)
        if os.path.exists(full_path):
            print(f"Found: {filename}")
        else:
            print(f"Missing file: {filename}")

if __name__ == "__main__":
    check_files_exist()
    read_csv_file()
    read_excel_file()
