"""
Centralized Configuration Module
All paths, parameters, and constraint sets in one place.
"""

import os

# == DIRECTORY STRUCTURE ======================================================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES_DIR = os.path.join(PROJECT_ROOT, 'sources')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, '_archive')

# Ensure directories exist
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# == FILE PATHS ===============================================================
PATHS = {
    # Input files
    'cities_excel': os.path.join(SOURCES_DIR, 'german_cities.xlsx'),
    'plz_topojson': os.path.join(SOURCES_DIR, 'ger_plz-5stellig.topojson'),
    'states_geojson': os.path.join(SOURCES_DIR, 'states_ger_geo.json'),
    
    # Output files
    'cities_cleaned': os.path.join(RESULTS_DIR, 'german_cities_cleaned.csv'),
    'customers': os.path.join(RESULTS_DIR, 'customers.csv'),
    'log_file': os.path.join(PROJECT_ROOT, 'optimization_process.log'),
    
    # Dynamic outputs (filled at runtime)
    'optimized_locations': os.path.join(RESULTS_DIR, 'optimized_locations_{}.csv'),
    'map_output': os.path.join(RESULTS_DIR, 'optimization_map_{}.html'),
}

# == OPTIMIZATION PARAMETERS ==================================================
OPTIMIZATION = {
    'service_level': 0.90,  # 90% of customers must be covered
    'customer_bonus': 0.2,  # Bonus for locations with high customer density
    'prestige_bonus': 0.1,  # Bonus for top 200 cities
    'earth_radius_km': 6371.0,
    'min_weight_at_max': 0.5,  # Minimum weight at max distance (decay function)
}

# == CUSTOMER GENERATION ======================================================
CUSTOMER_GENERATION = {
    'total_customers': 90000,
    'distribution': {
        'top10': 0.40,      # 40% in top 10 cities
        'top200': 0.56,     # 56% in cities 11-200
        'rural': 0.04       # 4% in rural areas
    }
}

# == DATA CONVERSION ==========================================================
CONVERSION = {
    'int_cols': ['id_key', 'population_total', 'population_male', 'population_female'],
    'float_cols': ['city_area_squared_km', 'population_per_squared_km']
}

# == CONSTRAINT SETS ==========================================================
# Multiple scenarios for optimization
CONSTRAINT_SETS = [
    {
        'name': 'Conservative',
        'max_distance_km': 100.0,
        'decay_start_km': 90.0,
        'cost_top_city': 0.8,
        'cost_standard': 1.0,
    },
    {
        'name': 'Moderate',
        'max_distance_km': 40.0,
        'decay_start_km': 15.0,
        'cost_top_city': 0.75,
        'cost_standard': 0.95,
    },
    {
        'name': 'Aggressive',
        'max_distance_km': 45.0,
        'decay_start_km': 20.0,
        'cost_top_city': 0.7,
        'cost_standard': 0.9,
    },
]

# == VALIDATION THRESHOLDS ====================================================
VALIDATION = {
    'germany_bounds': {
        'lat_min': 47.0,
        'lat_max': 55.0,
        'lon_min': 6.0,
        'lon_max': 15.0
    },
    'geocoding_warning_threshold': 0.05,  # Warn if >5% fail
    'max_reasonable_density': 50000,  # people per km²
    'warning_display_seconds': 5,
}

# == LOGGING CONFIGURATION ====================================================
LOGGING = {
    'level': 'INFO',
    'format': '%(asctime)s - [%(module)s] - %(levelname)s - %(message)s',
    'datefmt': '%Y-%m-%d %H:%M:%S'
}
