"""
VALIDATION MODULE
-----------------
Provides runtime integrity checks for the geographic optimization pipeline.

Key Responsibilities:
* Critical Path: Validates file existence, schema structure, and logical constraints.
* Data Quality: Audits coordinate bounds, PLZ formats, and geocoding success rates.
* Optimization Audits: Verifies feasibility before execution and solution optimality.

Enforces a 'fail-fast' policy for critical errors while providing timed warnings 
for non-breaking data quality issues. 
"""

import os
import logging
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
            logger.warning(
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
    else:
        logger.info(f"  ✓ Customer count matches config: {total_generated}")
    
    # Check for invalid PLZ codes (Validation #10 - duplicates handled in data_loader)
    invalid_plz = df_customers[df_customers['plz5'].str.len() != 5]
    if len(invalid_plz) > 0:
        logger.warning(f"  ⚠ Found {len(invalid_plz)} invalid PLZ codes (not 5 digits)")
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
    logger.info("Checking coverage after transformation from customers list to coverage matrix...")
    
    # Count how many customers can be covered
    coverable_customers = sum(
        df_demand.at[k_idx, 'customer_count']
        for k_idx in coverage.keys()
        if len(coverage[k_idx]) > 0
    )
    
    total_customers = df_demand['customer_count'].sum()
    max_achievable_coverage = coverable_customers / total_customers
    required_coverage = config.OPTIMIZATION['service_level']
    
    logger.info(f"  Total customers: {total_customers} and customers-to-location-mapping: {coverable_customers}")
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
        logger.warning(
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
        
    # Verify actual coverage matches requirement
    covered_customers = sum(
        df_demand.at[idx, 'customer_count']
        for idx in df_demand.index
        if is_served[idx].value() > 0.5
    )
    total_customers = df_demand['customer_count'].sum()
    actual_service_level = covered_customers / total_customers
    
    logger.info(f"    {num_opened} locations opened covering {covered_customers} customers out of {total_customers}")
    logger.info(f"    Actual service level achieved: {actual_service_level:.1%}")
    
    if actual_service_level < config.OPTIMIZATION['service_level'] - 0.001:  # Small tolerance
        logger.warning(f"  ⚠ Service level below target: {actual_service_level:.1%} < {config.OPTIMIZATION['service_level']:.1%}")


def check_visualization_data_integrity(df_customers: pd.DataFrame, topojson_data: Dict) -> None:
    """
    Validation #9: Verify that visualization data matches input customer data.
    Ensures no customers are lost during TopoJSON property injection.
    """
    logger.info("Validating visualization data integrity...")
    
    # 1. Calculate input sum
    input_sum = df_customers['customer_count'].sum()
    
    # 2. Calculate output sum from TopoJSON
    output_sum = 0
    try:
        # Navigate TopoJSON structure: objects -> data -> geometries
        if 'objects' in topojson_data and 'data' in topojson_data['objects']:
            geometries = topojson_data['objects']['data'].get('geometries', [])
            
            for geom in geometries:
                props = geom.get('properties', {})
                output_sum += props.get('customer_count', 0)
    except Exception as e:
        logger.error(f"Failed to validate visualization data structure: {e}")
        return

    # 3. Log and Compare
    logger.info(f"  Input customer count: {input_sum:,.0f}")
    logger.info(f"  Map layer customer count: {output_sum:,.0f}")
    
    if abs(input_sum - output_sum) < 1.0:
        logger.info("  ✓ Visualization data matches input data exactly")
    else:
        diff = input_sum - output_sum
        msg = f"Visualization mismatch: {diff:,.0f} customers not shown on map."
        if diff > 0:
            msg += " (PLZs missing in TopoJSON?)"
        logger.warning(f"  ⚠ {msg}")


def check_customer_uniqueness(df_customers: pd.DataFrame) -> None:
    """
    Validation #11: Verify that customer data has unique PLZ codes.
    CRITICAL - Fails if duplicates exist after aggregation.
    """
    logger.info("Validating customer PLZ uniqueness...")
    
    duplicate_count = df_customers.duplicated(subset=['plz5']).sum()
    
    if duplicate_count > 0:
        error_msg = f"Duplicate PLZ codes found in customer data: {duplicate_count} duplicates."
        logger.error(error_msg)
        raise ValidationError(error_msg)
    
    logger.info("  ✓ All PLZ codes are unique")
