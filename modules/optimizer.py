"""
OPTIMIZATION ENGINE MODULE
--------------------------
Solves the optimal location-allocation problem to maximize customer coverage at minimum cost.

Key Capabilities:
* Spatial Auditing: Computes Haversine distance matrices and geocodes PLZ data.
* Weighted Decay: Models service quality drop-off using distance-based linear decay.
* Linear Programming: Employs PuLP to minimize costs while hitting 'Service Level' targets.
* Multi-Scenario Testing: Supports iterative runs across various constraint sets (e.g., Aggressive vs. Conservative).
* Result Synthesis: Exports geocoded CSV results and interactive HTML map dashboards.

The engine ensures logival site selection based on hard criteria.
"""

import logging
import pandas as pd
import numpy as np
import pulp
from sklearn.metrics.pairwise import haversine_distances
from typing import Dict, Tuple
import config
from modules import validator

logger = logging.getLogger(__name__)


def calculate_coverage(df_demand: pd.DataFrame, df_candidates: pd.DataFrame, 
                       constraint_set: Dict) -> Tuple[Dict, Dict]:
    """
    Calculate which customers can be reached by each candidate location.
    
    Args:
        df_demand: Customer demand data
        df_candidates: Candidate city locations
        constraint_set: Constraint parameters (max_distance, decay_start, etc.)
        
    Returns:
        Tuple of (customer_to_locations_map, location_statistics)
    """
    logger.info("Calculating coverage matrix and location statistics...")
    
    # Compute distance matrix between all customers and candidates
    max_distance = constraint_set['max_distance_km']
    coords_demand = df_demand[['lat_rad', 'lon_rad']].to_numpy()
    coords_candidates = df_candidates[['lat_rad', 'lon_rad']].to_numpy()
    
    dist_matrix = haversine_distances(coords_demand, coords_candidates) * config.OPTIMIZATION['earth_radius_km']
    logger.info(f"  Distance matrix: {len(df_demand)} PLZ areas /w customers × {len(df_candidates)} candidates cities")
    
    # For each candidate city, identify reachable customers and calculate statistics
    location_stats = {}
    coverage = {}
    max_pop = df_candidates['population_total'].max()
    
    for s_idx in range(len(df_candidates)):
        c_sum_total = 0
        w_sum_weighted = 0
        reachable_indices = []
        
        for k_idx in range(len(df_demand)):
            d = dist_matrix[k_idx, s_idx]
            
            if d <= max_distance:
                reachable_indices.append(k_idx)
                count = df_demand.iloc[k_idx]['customer_count']
                
                # Calculate distance-based weight with decay
                if d <= constraint_set['decay_start_km']:
                    weight = 1.0
                else:
                    dist_ratio = (d - constraint_set['decay_start_km']) / \
                                (max_distance - constraint_set['decay_start_km'])
                    weight = 1.0 - dist_ratio * (1.0 - config.OPTIMIZATION['min_weight_at_max'])
                
                c_sum_total += count
                w_sum_weighted += count * weight
        
        loc_id = df_candidates.index[s_idx]
        coverage[loc_id] = reachable_indices # locations - to - customers dict
        location_stats[loc_id] = {
            'city_name': df_candidates.iloc[s_idx]['city_name'],
            'plz': df_candidates.iloc[s_idx]['plz'],
            'customers_total': float(c_sum_total),
            'customers_weighted': float(w_sum_weighted),
            'pop_factor': df_candidates.iloc[s_idx]['population_total'] / max_pop,
            'covered_customers_idx': reachable_indices
        }
    
    # Add customer factor with min 0-1 max range representing city importance based on customers
    all_weighted = [s['customers_weighted'] for s in location_stats.values()]
    mx, mn = (max(all_weighted), min(all_weighted)) if all_weighted else (1, 0)
    
    for loc_id in location_stats:
        location_stats[loc_id]['customer_factor'] = \
            (location_stats[loc_id]['customers_weighted'] - mn) / (mx - mn) if mx > mn else 1.0
    
    # Generate customer-to-locations mapping
    cust_to_loc = {
        k_idx: [loc_id for loc_id, ids in coverage.items() if k_idx in ids]
        for k_idx in range(len(df_demand))
    }
    
    logger.info(f"  ✓ Coverage calculation complete")
    
    # Validate coverage feasibility
    validator.check_coverage_feasibility(cust_to_loc, df_demand, constraint_set)  
    
    return cust_to_loc, location_stats


def run_optimization(df_demand: pd.DataFrame, df_candidates: pd.DataFrame,
                     coverage: Dict, location_stats: Dict, 
                     constraint_set: Dict) -> Tuple:
    """
    Solve the location optimization problem using linear programming.
    
    Args:
        df_demand: Customer demand data
        df_candidates: Candidate locations
        coverage: Customer-to-locations mapping
        location_stats: Statistics for each location
        constraint_set: Constraint parameters
        
    Returns:
        Tuple of (problem, is_opened, is_served) - PuLP problem and decision variables
    """
    logger.info(f"Starting PuLP optimization for '{constraint_set['name']}'...")
    
    # Create optimization problem (Minimization)
    problem = pulp.LpProblem("Location_Optimization", pulp.LpMinimize)
    
    # Decision variables (binary: 0 or 1)
    is_opened = pulp.LpVariable.dicts("loc", df_candidates.index, cat=pulp.LpBinary)
    is_served = pulp.LpVariable.dicts("cust", df_demand.index, cat=pulp.LpBinary)
    
    # Objective function: Minimize cost with bonuses for attractive locations
    logger.info("  Building objective function...")
    costs = []
    for i in df_candidates.index:
        base_cost = constraint_set['cost_top_city'] if df_candidates.at[i, 'is_top_200'] \
                    else constraint_set['cost_standard']
        
        bonus = (location_stats[i]['customer_factor'] * config.OPTIMIZATION['customer_bonus']) + \
                (location_stats[i]['pop_factor'] * config.OPTIMIZATION['prestige_bonus'])
        
        costs.append(is_opened[i] * (base_cost - bonus))
    
    problem += pulp.lpSum(costs)
    
    # Constraint 1: Each customer can only be served if at least one location covers them
    logger.info("  Adding coverage constraints...")
    for k in df_demand.index:
        problem += pulp.lpSum(is_opened[s] for s in coverage.get(k, [])) >= is_served[k]
    
    # Constraint 2: Service level requirement (e.g., 90% of customers must be covered)
    logger.info("  Adding service level constraint...")
    min_required = df_demand['customer_count'].sum() * config.OPTIMIZATION['service_level']
    problem += pulp.lpSum(
        is_served[i] * df_demand.at[i, 'customer_count'] 
        for i in df_demand.index
    ) >= min_required
    
    # Solve the problem
    logger.info("  Solving optimization problem...")
    problem.solve(pulp.PULP_CBC_CMD(msg=False))
    
    logger.info(f"  ✓ Optimization complete: Status = {pulp.LpStatus[problem.status]}")
    
    # Generate a dataframe based on result aggregating the results (analog to export function but NOW)
    # These file will be handed into check_optimization_result as well and has to have the same values as what will be calculated there
    # this dataframe will then be handed into the export (not something again newly generated)
    
    # Validate results
    validator.check_optimization_result(problem, is_opened, is_served, df_demand, constraint_set)
    
    return problem, is_opened, is_served


def resolve_customer_overlap(df_demand: pd.DataFrame, df_candidates: pd.DataFrame,
                             coverage: Dict, location_stats: Dict,
                             is_opened: Dict, is_served: Dict) -> Dict:
    """
    Post-optimization step: Assigns each served customer to exactly one opened location
    (the closest one) to eliminate double counting in reporting.
    
    Updates location_stats in-place:
    - 'customers_total' becomes the unique assigned count.
    - 'customers_reachable' preserves the original potential count.
    """
    logger.info("Resolving customer overlaps (assigning to closest location)...")
    
    # Initialize counters for unique assignment
    unique_counts = {idx: 0 for idx in df_candidates.index}
    
    # Cache coordinates for faster distance calculation
    cust_coords = df_demand[['lat_rad', 'lon_rad']].to_numpy()
    cand_coords = df_candidates[['lat_rad', 'lon_rad']].to_numpy()
    
    # Pre-filter opened locations
    opened_loc_indices = {idx for idx in df_candidates.index if is_opened[idx].value() > 0.5}
    
    for cust_idx in df_demand.index:
        # Skip if customer is not served
        if is_served[cust_idx].value() <= 0.5:
            continue
            
        # Get potential locations that are actually OPENED
        potential_locs = coverage.get(cust_idx, [])
        candidate_locs = [loc for loc in potential_locs if loc in opened_loc_indices]
        
        if not candidate_locs:
            continue
            
        best_loc = candidate_locs[0]
        
        # If covered by multiple opened locations, find the closest one
        if len(candidate_locs) > 1:
            c_lat, c_lon = cust_coords[cust_idx]
            min_dist = float('inf')
            
            for loc_idx in candidate_locs:
                l_lat, l_lon = cand_coords[loc_idx]
                
                # Haversine approximation for speed
                dlat = l_lat - c_lat
                dlon = l_lon - c_lon
                a = np.sin(dlat/2.0)**2 + np.cos(c_lat) * np.cos(l_lat) * np.sin(dlon/2.0)**2
                dist = 2 * np.arcsin(np.sqrt(a))
                
                if dist < min_dist:
                    min_dist = dist
                    best_loc = loc_idx
        
        # Assign customer count to the best location
        unique_counts[best_loc] += df_demand.at[cust_idx, 'customer_count']

    # Update location_stats with unique counts
    for loc_idx in location_stats:
        # Backup original potential reach
        location_stats[loc_idx]['customers_reachable'] = location_stats[loc_idx]['customers_total']
        
        if loc_idx in opened_loc_indices:
            # Update total to unique count
            location_stats[loc_idx]['customers_total'] = unique_counts[loc_idx]
            
            # Scale weighted score proportionally the quick & dirty solution
            original_total = location_stats[loc_idx]['customers_reachable']
            if original_total > 0:
                ratio = unique_counts[loc_idx] / original_total
                location_stats[loc_idx]['customers_weighted'] *= ratio
        else:
            # Closed locations serve 0 customers
            location_stats[loc_idx]['customers_total'] = 0
            location_stats[loc_idx]['customers_weighted'] = 0
            
    # Log the total deduplicated customer count from the updated stats
    total_unique_customers = sum(stats['customers_total'] for stats in location_stats.values())
    logger.info(f"  Total uniquely assigned customers after deduplication: {total_unique_customers:,.0f}")
            
    logger.info("  ✓ Customer overlaps resolved")
    
    
    
    return location_stats


def export_results(df_candidates: pd.DataFrame, is_opened: Dict, 
                   location_stats: Dict, constraint_name: str,
                   coverage: Dict = None, is_served: Dict = None) -> pd.DataFrame:
    """
    Export optimization results to CSV file.
    
    Args:
        df_candidates: Candidate locations
        is_opened: Decision variables for opened locations
        location_stats: Statistics for each location
        constraint_name: Name of constraint set used
        coverage: Customer-to-locations mapping (optional)
        is_served: Decision variables for served customers (optional)
        
    Returns:
        DataFrame with results
    """
    results_path = config.PATHS['optimized_locations'].format(constraint_name)
    logger.info(f"Exporting results to: {results_path}")
    
    # Identify opened locations
    opened_indices = [idx for idx in df_candidates.index if is_opened[idx].value() > 0.5]
    
    # Build export data
    export_data = []
    for idx in opened_indices:
        row = df_candidates.loc[idx]
        export_data.append({
            'city_name': row['city_name'],
            'plz': row['plz'],
            'lat': row['lat'],
            'lon': row['lon'],
            'city_type': 'Top 200' if row['is_top_200'] else 'Standard',
            'customers_covered_weighted': round(location_stats[idx]['customers_weighted'], 2),
            'customers_covered_total': int(location_stats[idx]['customers_total'])
        })
    
    # Create and save DataFrame
    df_results = pd.DataFrame(export_data)
    df_results = df_results.sort_values(by='customers_covered_total', ascending=False)
    df_results.to_csv(results_path, index=False, encoding='utf-8')
    
    logger.info(f"  ✓ Exported {len(df_results)} opened locations")
    
    return df_results
