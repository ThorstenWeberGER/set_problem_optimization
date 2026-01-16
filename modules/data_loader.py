"""
Data Loader Module
Handles loading and cleaning city data, geocoding, and coordinate enrichment.
"""

import logging
import pandas as pd
import numpy as np
import pgeocode
import config
from modules import validator

logger = logging.getLogger(__name__)


def load_and_clean_cities() -> pd.DataFrame:
    """
    Load city data from Excel and clean it for optimization.
    Returns DataFrame with cleaned city data.
    """
    logger.info("="*60)
    logger.info("LOADING AND CLEANING CITY DATA")
    logger.info("="*60)
    
    # Load raw data
    logger.info(f"Reading Excel file: {config.PATHS['cities_excel']}")
    try:
        df = pd.read_excel(config.PATHS['cities_excel'], engine='openpyxl')
        logger.info(f"  ✓ Loaded {len(df)} city records")
    except Exception as e:
        logger.error(f"Failed to load city data: {e}")
        raise
    
    # Validate structure
    required_cols = ['city_name', 'plz', 'population_total']
    validator.check_file_structure(df, required_cols, "City data")
    
    # Clean city names and extract city type
    logger.info("Cleaning city names and extracting city types...")
    split_data = df['city_name'].str.split(',', n=1, expand=True)
    df['city_name'] = split_data[0].str.strip()
    df['city_type'] = split_data[1].str.strip() if 1 in split_data.columns else None
    
    # Convert numeric columns
    logger.info("Converting numeric columns...")
    for col in config.CONVERSION['int_cols']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: _convert_numeric_ger_to_eng(x, int))
    
    for col in config.CONVERSION['float_cols']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: _convert_numeric_ger_to_eng(x, float))
    
    # Clean PLZ codes (keep as string, pad to 5 digits)
    if 'plz' in df.columns:
        df['plz'] = df['plz'].astype(str).str.replace('.0', '', regex=False).str.zfill(5)
        logger.info(f"  ✓ Cleaned {len(df)} PLZ codes")
    
    # Identify top 200 cities by population
    threshold = df['population_total'].nlargest(200).min()
    df['is_top_200'] = df['population_total'] >= threshold
    logger.info(f"  ✓ Identified {df['is_top_200'].sum()} cities in top 200")
    
    # Reorder columns for readability
    cols = list(df.columns)
    if 'city_type' in cols:
        cols.insert(cols.index('city_name') + 1, cols.pop(cols.index('city_type')))
    df = df[cols]
    
    # Save cleaned data
    df.to_csv(config.PATHS['cities_cleaned'], index=False, encoding='utf-8')
    logger.info(f"  ✓ Saved cleaned data to: {config.PATHS['cities_cleaned']}")
    
    logger.info("City data cleaning completed successfully")
    return df


def add_coordinates(df: pd.DataFrame, plz_column: str) -> pd.DataFrame:
    """
    Enrich DataFrame with latitude/longitude coordinates from postal codes.
    Returns DataFrame with added coordinate columns and filters invalid entries.
    """
    logger.info(f"Enriching coordinates for column '{plz_column}'...")
    
    # Load reference data and get valid postal codes
    geo = pgeocode.Nominatim('de')
    valid_geo_data = geo._data.dropna(subset=['latitude', 'longitude'])
    valid_zip_set = set(valid_geo_data['postal_code'].unique())
    logger.info(f"  Reference database loaded: {len(valid_zip_set)} valid German postal codes")
    
    # Clean postal codes
    df[plz_column] = df[plz_column].str.replace('.0', '', regex=False).str.zfill(5)
    initial_count = len(df)
    
    # Filter to only valid postal codes
    df = df[df[plz_column].isin(valid_zip_set)].copy()
    removed_count = initial_count - len(df)
    
    if removed_count > 0:
        logger.warning(f"  ⚠ Removed {removed_count} records with invalid postal codes")
    
    # Query coordinates
    geo_info = geo.query_postal_code(df[plz_column].tolist())
    df['lat'] = geo_info['latitude'].values
    df['lon'] = geo_info['longitude'].values
    
    # Convert to radians for distance calculations
    df[['lat_rad', 'lon_rad']] = np.radians(df[['lat', 'lon']])
    
    logger.info(f"  ✓ Geocoding finished: {len(df)}/{initial_count} locations valid")
    
    # Run quality checks
    validator.check_geographic_quality(df, plz_column)
    
    return df.reset_index(drop=True)


def _convert_numeric_ger_to_eng(value, target_type):
    """
    Convert numeric values from German string format to standard floats/ints.
    Handles German decimal notation (. for thousands, , for decimals).
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
