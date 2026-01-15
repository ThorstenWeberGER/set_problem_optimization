# =========================================================================
# PURPOSE: Generates specified number of synthetic customers in Germany
#          based on real city population data and valid postal codes.
# =========================================================================


import os
import pandas as pd
import numpy as np
import logging
import pgeocode

# == CONFIGURATION ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # returns directory of this python file
PARENT_DIR = os.path.dirname(SCRIPT_DIR) # used on a directory it returns the parent directory

CONFIG = {
    'input_file': os.path.join(PARENT_DIR, 'results', 'german_cities_clean_utf8.csv'),
    'output_file': os.path.join(PARENT_DIR, 'results', 'customers.csv'),
    'total_customers': 90000,
    'distribution': {
        'top10': 0.40,
        'top200': 0.56,
        'rural': 0.04
    },
    'log_file': os.path.join(PARENT_DIR, 'optimization_process.log')
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
    """Creates a visual separation in the log at every script start."""
    try:
        filename = os.path.basename(__file__)
    except NameError:
        filename = "Interactive_Session"

    logging.info("="*60)
    logging.info(f"START: Execution of {filename}")
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

def get_valid_german_plzs():
    """
    Loads all German postal codes that actually have geographic coordinates.
    """
    logging.info("Loading reference database for valid German ZIP codes...")
    nomi = pgeocode.Nominatim('de')
    
    # IMPROVED: We filter the internal data to keep ONLY PLZs with valid coordinates
    all_data = nomi._data
    valid_data = all_data.dropna(subset=['latitude', 'longitude'])
    
    logging.info(f"Database loaded: {len(valid_data)} geographic ZIP codes available.")
    return valid_data['postal_code'].unique().tolist()

def generate_customer_data(df_cities, total_customers, distribution):
    """Generates synthetic customer data using validated ZIP codes."""
    logging.info("Starting AI-supported customer generation (Validated ZIPs).")
    
    valid_plzs = get_valid_german_plzs()
    valid_plz_set = set(valid_plzs) # Faster lookup using a set
    customer_list = []

    # Sort cities by population to identify Top 10 and Top 200
    df_cities = df_cities.sort_values(by='population_total', ascending=False)
    top10 = df_cities.head(10)
    top11_200 = df_cities.iloc[10:200]

    def get_real_nearby_plz(base_plz, radius_variance):
        """Finds an existing ZIP code near the base ZIP code."""
        try:
            base_val = int(base_plz)
            # Search within the numerical range for a ZIP that exists in the database
            for attempt in range(20): # Maximum 20 attempts
                offset = np.random.randint(-radius_variance, radius_variance + 1)
                test_plz = str(base_val + offset).zfill(5)
                if test_plz in valid_plz_set:
                    return test_plz
            return str(base_plz).zfill(5) # Fallback if no nearby valid ZIP is found
        except:
            return str(base_plz).zfill(5)

    # A. Segment: Top 10 Metropolises
    quota_top10 = int(total_customers * distribution['top10'])
    total_pop_top10 = top10['population_total'].sum()
    for row in top10.itertuples():
        city_customers = int((row.population_total / total_pop_top10) * quota_top10)
        for _ in range(city_customers):
            # Larger radius for metropolises (80)
            customer_list.append([get_real_nearby_plz(row.plz, 80), row.city_name])

    # B. Segment: Remaining Top 200 Cities
    quota_rest = int(total_customers * distribution['top200'])
    total_pop_rest = top11_200['population_total'].sum()
    for row in top11_200.itertuples():
        city_customers = int((row.population_total / total_pop_rest) * quota_rest)
        for _ in range(city_customers):
            # Smaller radius for standard cities (20)
            customer_list.append([get_real_nearby_plz(row.plz, 20), row.city_name])

    # C. Segment: Rural Areas (Random VALID ZIP codes)
    quota_rural = total_customers - len(customer_list)
    logging.info(f"Generating {quota_rural} customers in rural areas from valid ZIP codes...")
    for _ in range(quota_rural):
        random_valid_plz = np.random.choice(valid_plzs)
        customer_list.append([random_valid_plz, "Rural Area / Others"])

    # Final Aggregation: Count customers per ZIP and city
    df = pd.DataFrame(customer_list, columns=['plz5', 'city_name'])
    df_final = df.groupby(['plz5', 'city_name']).size().reset_index(name='customer_count')
    
    return df_final

# =============================================================================

def start_generate():
    # Start Logging
    log_separator()
    logging.info("Process started.")
    
    # 1. Load city data
    try:
        df_cities = pd.read_csv(CONFIG['input_file'], encoding='utf-8')
    except Exception as e:
        logging.error(f"City data file not found or could not be read: {e}")
        return

    # 2. Generate customer data
    df_customers = generate_customer_data(df_cities, CONFIG['total_customers'], CONFIG['distribution'])
    
    # 3. Save to CSV
    try:
        df_customers.to_csv(CONFIG['output_file'], index=False)
        logging.info(f"File successfully saved to: {CONFIG['output_file']}")
        logging.info(f"Total number of customers generated: {df_customers['customer_count'].sum()}")
        logging.info("Process completed successfully.")
    except Exception as e:
        logging.error(f"Failed to save the output file: {e}")

    # Display log summary for verification
    display_log_content(CONFIG['log_file'])


if __name__ == "__main__":
    start_generate()