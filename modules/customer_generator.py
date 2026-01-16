"""
Customer Generator Module
Generates synthetic customer data or loads existing data.
"""

import logging
import os
import pandas as pd
import numpy as np
import pgeocode
import config
from modules import validator

logger = logging.getLogger(__name__)


def load_or_generate_customers(df_cities: pd.DataFrame, force_regenerate: bool = False) -> pd.DataFrame:
    """
    Load existing customer data if available, otherwise generate new data.
    
    Args:
        df_cities: DataFrame with city data
        force_regenerate: If True, always generate new data
        
    Returns:
        DataFrame with customer data (plz5, city_name, customer_count)
    """
    logger.info("="*60)
    logger.info("CUSTOMER DATA PREPARATION")
    logger.info("="*60)
    
    customer_path = config.PATHS['customers']
    
    # Check if existing file should be used
    if not force_regenerate and os.path.exists(customer_path):
        logger.info(f"Loading existing customer data from: {customer_path}")
        try:
            df_customers = pd.read_csv(customer_path, dtype={'plz5': str})
            logger.info(f"  ✓ Loaded {len(df_customers)} customer records")
            logger.info(f"  ✓ Total customers: {df_customers['customer_count'].sum():,}")
            
            # Validate structure
            required_cols = ['plz5', 'customer_count']
            validator.check_file_structure(df_customers, required_cols, "Customer data")
            
            # Handle duplicate PLZ codes (Validation #10)
            df_customers = _handle_duplicate_plz(df_customers)
            
            # Run quality checks
            validator.check_customer_distribution(df_customers)
            
            return df_customers
            
        except Exception as e:
            logger.warning(f"Failed to load existing customer data: {e}")
            logger.info("Generating new customer data instead...")
    
    # Generate new customer data
    logger.info("Generating new synthetic customer data...")
    df_customers = generate_customer_data(df_cities)
    
    # Save for future use
    df_customers.to_csv(customer_path, index=False, encoding='utf-8')
    logger.info(f"  ✓ Customer data saved to: {customer_path}")
    
    # Run quality checks
    validator.check_customer_distribution(df_customers)
    
    return df_customers


def generate_customer_data(df_cities: pd.DataFrame) -> pd.DataFrame:
    """
    Generate synthetic customer data using validated ZIP codes.
    
    Args:
        df_cities: DataFrame with city data
        
    Returns:
        DataFrame with columns: plz5, city_name, customer_count
    """
    logger.info("Starting customer generation with validated ZIP codes...")
    
    # Get valid German postal codes
    valid_plzs = _get_valid_german_plzs()
    valid_plz_set = set(valid_plzs)
    
    total_customers = config.CUSTOMER_GENERATION['total_customers']
    distribution = config.CUSTOMER_GENERATION['distribution']
    
    customer_list = []
    
    # Sort cities by population
    df_cities = df_cities.sort_values(by='population_total', ascending=False)
    top10 = df_cities.head(10)
    top11_200 = df_cities.iloc[10:200]
    
    # A. Segment: Top 10 Metropolises (40%)
    logger.info(f"  Generating customers for top 10 cities ({distribution['top10']:.0%})...")
    quota_top10 = int(total_customers * distribution['top10'])
    total_pop_top10 = top10['population_total'].sum()
    
    for row in top10.itertuples():
        city_customers = int((row.population_total / total_pop_top10) * quota_top10)
        for _ in range(city_customers):
            # Larger radius for metropolises
            plz = _get_real_nearby_plz(row.plz, 80, valid_plz_set)
            customer_list.append([plz, row.city_name])
    
    # B. Segment: Cities 11-200 (56%)
    logger.info(f"  Generating customers for cities 11-200 ({distribution['top200']:.0%})...")
    quota_rest = int(total_customers * distribution['top200'])
    total_pop_rest = top11_200['population_total'].sum()
    
    for row in top11_200.itertuples():
        city_customers = int((row.population_total / total_pop_rest) * quota_rest)
        for _ in range(city_customers):
            # Smaller radius for standard cities
            plz = _get_real_nearby_plz(row.plz, 20, valid_plz_set)
            customer_list.append([plz, row.city_name])
    
    # C. Segment: Rural Areas (4%)
    quota_rural = total_customers - len(customer_list)
    logger.info(f"  Generating customers for rural areas ({distribution['rural']:.0%})...")
    
    for _ in range(quota_rural):
        random_valid_plz = np.random.choice(valid_plzs)
        customer_list.append([random_valid_plz, "Rural Area / Others"])
    
    # Aggregate: Count customers per PLZ and city
    df = pd.DataFrame(customer_list, columns=['plz5', 'city_name'])
    df_final = df.groupby(['plz5', 'city_name']).size().reset_index(name='customer_count')
    
    logger.info(f"  ✓ Generated {len(df_final)} unique PLZ records")
    logger.info(f"  ✓ Total customers: {df_final['customer_count'].sum():,}")
    
    return df_final


def _get_valid_german_plzs() -> list:
    """
    Load all German postal codes that have geographic coordinates.
    """
    logger.info("  Loading reference database for valid German ZIP codes...")
    nomi = pgeocode.Nominatim('de')
    
    # Filter to keep only PLZs with valid coordinates
    all_data = nomi._data
    valid_data = all_data.dropna(subset=['latitude', 'longitude'])
    
    logger.info(f"  Database loaded: {len(valid_data)} valid geographic ZIP codes")
    return valid_data['postal_code'].unique().tolist()


def _get_real_nearby_plz(base_plz: str, radius_variance: int, valid_plz_set: set) -> str:
    """
    Find an existing ZIP code near the base ZIP code.
    
    Args:
        base_plz: Base postal code
        radius_variance: Search radius (in numeric PLZ units)
        valid_plz_set: Set of valid postal codes
        
    Returns:
        Valid nearby postal code
    """
    try:
        base_val = int(base_plz)
        # Search within numerical range for a ZIP that exists
        for _ in range(20):  # Max 20 attempts
            offset = np.random.randint(-radius_variance, radius_variance + 1)
            test_plz = str(base_val + offset).zfill(5)
            if test_plz in valid_plz_set:
                return test_plz
        # Fallback if no nearby valid ZIP found
        return str(base_plz).zfill(5)
    except:
        return str(base_plz).zfill(5)


def _handle_duplicate_plz(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle duplicate PLZ codes by summing customer counts (Validation #10).
    """
    duplicates = df[df.duplicated(subset=['plz5'], keep=False)]
    
    if len(duplicates) > 0:
        unique_plz_count = duplicates['plz5'].nunique()
        logger.warning(f"  ⚠ Found {len(duplicates)} duplicate PLZ entries ({unique_plz_count} unique PLZ codes)")
        logger.info("  Summing customer counts for duplicate PLZ codes...")
        
        # Group by PLZ and sum customer counts
        df_aggregated = df.groupby('plz5').agg({
            'customer_count': 'sum',
            'city_name': 'first'  # Keep first city name
        }).reset_index()
        
        logger.info(f"  ✓ Aggregated to {len(df_aggregated)} unique PLZ records")
        return df_aggregated
    
    return df
