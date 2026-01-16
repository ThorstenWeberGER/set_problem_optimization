"""
Validation Module
Implements recommendations 1-8, 10 from validation discussion.
"""

import os
import logging
import time
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import config

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for critical validation failures."""
    pass


def check_input_files() -> None:
    """
    Validation #1: Check if all required input files exist.
    CRITICAL - Fails fast if files missing.
    """
    logger.info("Validating input files...")
    
    required_files = {
        'Cities Excel': config.PATHS['cities_excel'],
        'PLZ TopoJSON': config.PATHS['plz_topojson'],
        'States GeoJSON': config.PATHS['states_geojson'],
    }
    
    missing_files = []
    for name, path in required_files.items():
        if not os.path.exists(path):
            missing_files.append(f"  ✗ {name}: {path}")
            logger.error(f"Missing file: {path}")
        else:
            logger.info(f"  ✓ {name} found")
    
    if missing_files:
        error_msg = "Missing required input files:\n" + "\n".join(missing_files)
        raise ValidationError(error_msg)
    
    logger.info("All required input files present.")


def check_file_structure(df: pd.DataFrame, required_columns: List[str], 
                         file_description: str) -> None:
    """
    Validation #2: Check if DataFrame has required columns.
    CRITICAL - Fails if columns missing.
    """
    logger.info(f"Validating {file_description} structure...")
    
    missing_cols = [col for col in required_columns if col not in df.columns]
    
    if missing_cols:
        error_msg = f"{file_description} missing required columns: {missing_cols}"
        logger.error(error_msg)
        raise ValidationError(error_msg)
    
    logger.info(f"  ✓ {file_description} has all required columns")


def check_geographic_quality(df: pd.DataFrame, plz_column: str = 'plz') -> None:
    """
    Validation #5, #6: Check geocoding success rate and coordinate bounds.
    WARNING - Logs issues but continues.
    """
    logger.info("Validating geographic data quality...")
    
    total_rows = len(df)
    
    # Check for missing coordinates
    missing_coords = df[['lat', 'lon']].isna().any(axis=1).sum()
    if missing_coords > 0:
        failure_rate = missing_coords / total_rows
        logger.warning(f"  ⚠ {missing_coords} out of {total_rows} records failed geocoding ({failure_rate:.1%})")
        
        if failure_rate > config.VALIDATION['geocoding_warning_threshold']:
            _display_warning(
                f"Geocoding failure rate is {failure_rate:.1%} (threshold: {config.VALIDATION['geocoding_warning_threshold']:.1%}). "
                f"This may affect optimization quality."
            )
    else:
        logger.info("  ✓ All records successfully geocoded")
    
    # Check if coordinates are within Germany bounds
    valid_data = df.dropna(subset=['lat', 'lon'])
    bounds = config.VALIDATION['germany_bounds']
    
    out_of_bounds = (
        (valid_data['lat'] < bounds['lat_min']) | 
        (valid_data['lat'] > bounds['lat_max']) |
        (valid_data['lon'] < bounds['lon_min']) | 
        (valid_data['lon'] > bounds['lon_max'])
    ).sum()
    
    if out_of_bounds > 0:
        logger.warning(f"  ⚠ {out_of_bounds} coordinates outside Germany's bounds - may be removed")
        _display_warning(f"{out_of_bounds} locations have coordinates outside expected Germany bounds.")
    else:
        logger.info("  ✓ All coordinates within Germany bounds")


def check_customer_distribution(df_customers: pd.DataFrame) -> None:
    """
    Validation #8, #10: Check customer data quality.
    WARNING - Logs issues but continues.
    """
    logger.info("Validating customer distribution...")
    
    # Check total customers match config
    total_generated = df_customers['customer_count'].sum()
    expected_total = config.CUSTOMER_GENERATION['total_customers']
    
    if abs(total_generated - expected_total) > 100:  # Allow small rounding differences
        logger.warning(f"  ⚠ Customer count mismatch: generated {total_generated}, expected {expected_total}")
        _display_warning(f"Customer count differs from config: {total_generated} vs {expected_total}")
    else:
        logger.info(f"  ✓ Customer count matches config: {total_generated}")
    
    # Check for invalid PLZ codes (Validation #10 - duplicates handled in data_loader)
    invalid_plz = df_customers[df_customers['plz5'].str.len() != 5]
    if len(invalid_plz) > 0:
        logger.warning(f"  ⚠ Found {len(invalid_plz)} invalid PLZ codes (not 5 digits)")
        _display_warning(f"{len(invalid_plz)} customer records have invalid PLZ codes.")
    else:
        logger.info("  ✓ All PLZ codes are valid (5 digits)")
    
    # Check for zero-customer PLZs
    zero_customers = (df_customers['customer_count'] == 0).sum()
    if zero_customers > 0:
        logger.warning(f"  ⚠ {zero_customers} PLZ codes have 0 customers")


def check_constraint_logic(constraint_set: Dict) -> None:
    """
    Validation #3: Verify constraint set parameters are logical.
    CRITICAL - Fails if constraints are impossible.
    """
    logger.info(f"Validating constraint set '{constraint_set['name']}'...")
    
    errors = []
    
    # max_distance must be greater than decay_start
    if constraint_set['max_distance_km'] <= constraint_set['decay_start_km']:
        errors.append(f"max_distance_km ({constraint_set['max_distance_km']}) must be > decay_start_km ({constraint_set['decay_start_km']})")
    
    # Cost values must be positive
    if constraint_set['cost_top_city'] <= 0 or constraint_set['cost_standard'] <= 0:
        errors.append("Cost values must be positive")
    
    # Service level must be between 0 and 1
    if not (0 < config.OPTIMIZATION['service_level'] <= 1):
        errors.append(f"service_level must be between 0 and 1, got {config.OPTIMIZATION['service_level']}")
    
    if errors:
        error_msg = f"Invalid constraint set '{constraint_set['name']}':\n  " + "\n  ".join(errors)
        logger.error(error_msg)
        raise ValidationError(error_msg)
    
    logger.info(f"  ✓ Constraint set '{constraint_set['name']}' is valid")


def check_coverage_feasibility(coverage: Dict, df_demand: pd.DataFrame, 
                               constraint_set: Dict) -> None:
    """
    Validation #7: Check if required service level is achievable.
    WARNING - Alerts user if service level is tight or impossible.
    """
    logger.info("Checking coverage feasibility...")
    
    # Count how many customers can be covered by at least one location
    coverable_customers = sum(
        df_demand.at[k_idx, 'customer_count']
        for k_idx in coverage.keys()
        if len(coverage[k_idx]) > 0
    )
    
    total_customers = df_demand['customer_count'].sum()
    max_achievable_coverage = coverable_customers / total_customers
    required_coverage = config.OPTIMIZATION['service_level']
    
    logger.info(f"  Maximum achievable coverage: {max_achievable_coverage:.1%}")
    logger.info(f"  Required service level: {required_coverage:.1%}")
    
    if max_achievable_coverage < required_coverage:
        error_msg = (
            f"IMPOSSIBLE SERVICE LEVEL with constraint set '{constraint_set['name']}':\n"
            f"  Maximum achievable: {max_achievable_coverage:.1%}\n"
            f"  Required: {required_coverage:.1%}\n"
            f"  Suggestion: Increase max_distance_km or reduce service_level"
        )
        logger.error(error_msg)
        raise ValidationError(error_msg)
    
    elif max_achievable_coverage < required_coverage + 0.05:  # Tight margin
        _display_warning(
            f"Coverage margin is tight: max achievable {max_achievable_coverage:.1%} "
            f"vs required {required_coverage:.1%}. Optimization may struggle."
        )
    else:
        logger.info("  ✓ Required service level is achievable")


def check_optimization_result(problem, is_opened: Dict, is_served: Dict, 
                              df_demand: pd.DataFrame, constraint_set: Dict) -> None:
    """
    Validation #4: Verify optimization solved successfully.
    CRITICAL - Fails if solution is not optimal.
    """
    import pulp
    
    logger.info("Validating optimization results...")
    
    status = pulp.LpStatus[problem.status]
    logger.info(f"  Optimization status: {status}")
    
    if status != 'Optimal':
        error_msg = (
            f"Optimization failed for constraint set '{constraint_set['name']}':\n"
            f"  Status: {status}\n"
            f"  This indicates the problem is infeasible or unbounded."
        )
        logger.error(error_msg)
        raise ValidationError(error_msg)
    
    # Check if any locations were opened
    num_opened = sum(1 for v in is_opened.values() if v.value() > 0.5)
    if num_opened == 0:
        error_msg = "Optimization resulted in 0 opened locations - check constraints"
        logger.error(error_msg)
        raise ValidationError(error_msg)
    
    logger.info(f"  ✓ Optimization successful: {num_opened} locations opened")
    
    # Verify actual coverage matches requirement
    covered_customers = sum(
        df_demand.at[idx, 'customer_count']
        for idx in df_demand.index
        if is_served[idx].value() > 0.5
    )
    total_customers = df_demand['customer_count'].sum()
    actual_service_level = covered_customers / total_customers
    
    logger.info(f"  Actual service level achieved: {actual_service_level:.1%}")
    
    if actual_service_level < config.OPTIMIZATION['service_level'] - 0.001:  # Small tolerance
        logger.warning(f"  ⚠ Service level below target: {actual_service_level:.1%} < {config.OPTIMIZATION['service_level']:.1%}")


def _display_warning(message: str) -> None:
    """
    Display warning to user and wait for configured seconds.
    """
    logger.warning(message)
    print(f"\n⚠️  WARNING: {message}")
    print(f"   Continuing in {config.VALIDATION['warning_display_seconds']} seconds...\n")
    time.sleep(config.VALIDATION['warning_display_seconds'])
