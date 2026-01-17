"""
PURPOSE:
- Load municipality data from Excel.
- Clean 'city_name': Extract descriptive suffixes into 'city_type'.
- Handle numeric conversions (Integer for population/ID, Float for area/density).
- Preserve 'plz' as STRING.
- Export as database-ready UTF-8 CSV.
- Log process to file and display the log content at the end.

OUTPUT: 
- A cleaned CSV file saved alongside the original Excel file.
"""

import pandas as pd
import os
import logging

# == CONFIGURATION ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # returns directory of this python file
PARENT_DIR = os.path.dirname(SCRIPT_DIR) # used on a directory it returns the parent directory

CONFIG = {
    'input_file': os.path.join(PARENT_DIR, 'sources', 'german_cities.xlsx'),
    'log_file': os.path.join(SCRIPT_DIR, 'optimization_process.log'),
    'output_file': os.path.join(PARENT_DIR, 'results', 'german_cities.csv')
}
CONVERSION_DICT = { 
    'int_cols' : ['id_key', 'population_total', 'population_male', 'population_female'],
    'float_cols' : ['city_area_squared_km', 'population_per_squared_km']
}

# == LOGGING ================================================================
logging.basicConfig(
    level=logging.INFO,
    # %(filename)s automatically detects the name of the current script
    format='%(asctime)s - [%(filename)s] - %(levelname)s - %(message)s',
    handlers=[
        # mode='a' (append) adds new lines at the bottom instead of overwriting
        logging.FileHandler(CONFIG['log_file'], mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def log_separator():
    """Creates visual separation in the log at every script start."""
    logging.info("="*60)
    logging.info(f"START: Executing {os.path.basename(__file__)}")
    logging.info("="*60)
    
def display_log_content(log_path):
    """
    Reads the log file and displays its content on the screen.
    """
    print("\n" + "="*60)
    print(f"FINAL LOG SUMMARY (from {log_path}):")
    print("="*60)
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            print(f.read())
    except Exception as e:
        print(f"Could not read log file: {e}")
    print("="*60 + "\n")
# =============================================================================

def load_xls_data(file) -> pd.DataFrame:
    """ 
    Helper function: Loads the data from an Excel file.
    """
    try:
        df = pd.read_excel(file, engine='openpyxl')
        logging.info(f"Data loaded: {len(df)} rows found.")
        return df
    except Exception as e:
        logging.error(f"Error during loading: {e}")
        return None

def convert_numeric_ger_to_eng(value, target_type):
    """
    Helper fuction: Converts numeric values from German string format to standard floats/ints.
    """
    if pd.isna(value) or value == '':
        return 0 if target_type == int else 0.0
    
    if isinstance(value, str):
        value = value.replace('.', '').replace(',', '.')
        
    try:
        num = float(value)
        return int(round(num)) if target_type == int else float(num)
    except (ValueError, TypeError):
        return 0

def clean_city_data(df_cities) -> pd.DataFrame:
    """
    Main function: Cleans the DataFrame for city names, types, and numeric columns.
    """
    logging.info("Starting cleaning city data.")
    
    split_data = df_cities['city_name'].str.split(',', n=1, expand=True)
    df_cities['city_name'] = split_data[0].str.strip()
    df_cities['city_type'] = split_data[1].str.strip() if 1 in split_data.columns else None

    for category, cols in CONVERSION_DICT.items():
        target_type = int if category == 'int_cols' else float
        for col in cols:
            if col in df_cities.columns:
                df_cities[col] = df_cities[col].apply(lambda x: convert_numeric_ger_to_eng(x, target_type))
             
    if 'plz' in df_cities.columns:
        df_cities['plz'] = df_cities['plz'].astype(str).str.replace('.0', '', regex=False).str.zfill(5)

    # Reorder columns: place city_type right after city_name for better readability
    cols = list(df_cities.columns)
    if 'city_type' in cols:
        cols.insert(cols.index('city_name') + 1, cols.pop(cols.index('city_type')))
    df_cities = df_cities[cols]

    logging.info("Cleaning finished.")
    return df_cities

def save_df_as_csv(df, file) -> None:
    """ 
    Exports the DataFrame to a database-ready CSV.
    """
    logging.info("Saving cleaned data to CSV...")
    df.to_csv(file, index=False, sep=',', decimal='.', encoding='utf-8')
    logging.info(f"File saved to: {file}")

def start_cleaning():
    """
    Main routine for reading and cleaning DeStatis German City data.
    """
    # Start Logging
    log_separator()
    logging.info("Starting Process...")
    
    # Read German city data from Excel
    raw_df = load_xls_data(CONFIG['input_file'])
    
    # Clean and save
    if raw_df is not None:
        cleaned_df = clean_city_data(raw_df)
        save_df_as_csv(cleaned_df, CONFIG['output_file'])
    
    # Stop logging
    logging.info("Process finished successfully.")

if __name__ == "__main__":
    
    start_cleaning()
    
    # For demonstration purposes show log content
    # display_log_content(CONFIG['log_file'])