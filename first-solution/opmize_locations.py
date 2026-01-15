# =========================================================================
# PURPOSE: Minimize locations to cover a specified amount of customers 
# =========================================================================

import os
import pandas as pd
import numpy as np
import pulp
import pgeocode
import folium
import webbrowser
import logging
from sklearn.metrics.pairwise import haversine_distances

# == CONFIGURATION ========================================================
# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Base configuration (shared across all constraint sets)
BASE_CONFIG = {
    'service_level': 0.90,
    'cost_top_city': 0.8,
    'cost_standard': 1.0,
    'customer_bonus': 0.2,
    'prestige_bonus': 0.1,
    'earth_radius_km': 6371.0,
    'min_weight_at_max': 0.5,
    'candidates_path': os.path.join(SCRIPT_DIR, 'results', 'german_cities_clean_utf8.csv'),
    'demand_path': os.path.join(SCRIPT_DIR, 'results', 'customers.csv'),
    'log_file': os.path.join(SCRIPT_DIR, 'optimization_process.log')
}

# Define different constraint sets to optimize with
CONSTRAINT_SETS = [
    {
        'name': 'Conservative',
        'max_distance_km': 35.0,
        'decay_start_km': 10.0,
        'cost_top_city': 0.8,
        'cost_standard': 1.0,
    },
    # Add more constraint sets here as needed
    # {
    #     'name': 'Moderate',
    #     'max_distance_km': 40.0,
    #     'decay_start_km': 15.0,
    #     'cost_top_city': 0.75,
    #     'cost_standard': 0.95,
    # },
    # {
    #     'name': 'Aggressive',
    #     'max_distance_km': 45.0,
    #     'decay_start_km': 20.0,
    #     'cost_top_city': 0.7,
    #     'cost_standard': 0.9,
    # },
]

# == LOGGING ================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(filename)s] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BASE_CONFIG['log_file'], mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def log_separator():
    """Print a visual separator in the log at script start."""
    try:
        filename = os.path.basename(__file__)
    except NameError:
        filename = "Interactive_Session"
    logging.info("="*60)
    logging.info(f"START: Execution of {filename}")
    logging.info("="*60)

# =============================================================================
# DATA LOADING & PREPARATION
# =============================================================================

def read_data():
    """Load candidate cities and customer demand data from CSV files."""
    logging.info("Reading input CSV files...")
    try:
        # Load candidate cities and identify top 200
        df_candidates = pd.read_csv(BASE_CONFIG['candidates_path'], dtype={'plz': str})
        threshold = df_candidates['population_total'].nlargest(200).min()
        df_candidates['is_top_200'] = df_candidates['population_total'] >= threshold
        
        # Load and normalize demand data
        df_demand = pd.read_csv(BASE_CONFIG['demand_path'])
        if 'plz5' not in df_demand.columns and 'plz-nummer' in df_demand.columns:
            df_demand = df_demand.rename(columns={'plz-nummer': 'plz5'})
        
        df_demand['plz5'] = df_demand['plz5'].astype(str)
        logging.info(f"Loaded {len(df_candidates)} candidates and {len(df_demand)} demand points.")
        return df_candidates, df_demand
    except Exception as e:
        logging.error(f"Failed to read data: {e}")
        raise

def add_coordinates(df, plz_column):
    """Enrich dataframe with latitude and longitude coordinates from postal codes."""
    
    logging.info(f"Enriching coordinates for {plz_column}...")
    
    # Load reference data and filter valid postal codes
    geo = pgeocode.Nominatim('de')
    valid_geo_data = geo._data.dropna(subset=['latitude', 'longitude'])
    valid_zip_set = set(valid_geo_data['postal_code'].unique())

    # Clean postal codes and keep only those with valid coordinates
    df[plz_column] = df[plz_column].str.replace('.0', '', regex=False).str.zfill(5)
    initial_count = len(df)
    df = df[df[plz_column].isin(valid_zip_set)].copy()
    
    # Query and convert coordinates to radians for distance calculations
    geo_info = geo.query_postal_code(df[plz_column].tolist())
    df['lat'] = geo_info['latitude'].values
    df['lon'] = geo_info['longitude'].values
    df[['lat_rad', 'lon_rad']] = np.radians(df[['lat', 'lon']])
    
    logging.info(f"Geocoding finished. {len(df)}/{initial_count} locations valid.")
    return df.reset_index(drop=True)

# =============================================================================
# LOGIC & OPTIMIZATION
# =============================================================================

def calculate_coverage(df_demand, df_candidates, config):
    """Calculate which customers can be reached by each candidate location."""
    
    logging.info("Calculating catchment areas and weights...")
    
    # Compute distance matrix between all customer and candidate locations
    max_distance = config['max_distance_km']
    coords_demand = df_demand[['lat_rad', 'lon_rad']].to_numpy()
    coords_candidates = df_candidates[['lat_rad', 'lon_rad']].to_numpy()
    dist_matrix = haversine_distances(coords_demand, coords_candidates) * config['earth_radius_km']
    
    # For each candidate location, identify reachable customers and calculate statistics
    location_stats = {}
    coverage = {}
    demand_col = 'customer_count'
    max_pop = df_candidates['population_total'].max()

    for s_idx in range(len(df_candidates)):
        c_sum_total = 0
        w_sum_weighted = 0
        reachable_indices = []
        for k_idx in range(len(df_demand)):
            d = dist_matrix[k_idx, s_idx]
            if d <= max_distance:
                reachable_indices.append(k_idx)
                count = df_demand.iloc[k_idx][demand_col]
                if d <= config['decay_start_km']:
                    weight = 1.0
                else:
                    dist_ratio = (d - config['decay_start_km']) / (max_distance - config['decay_start_km'])
                    weight = 1.0 - dist_ratio * (1.0 - config['min_weight_at_max'])
                c_sum_total += count
                w_sum_weighted += count * weight
        
        loc_id = df_candidates.index[s_idx]
        coverage[loc_id] = reachable_indices
        location_stats[loc_id] = {
            'customers_total': float(c_sum_total),
            'customers_weighted': float(w_sum_weighted),
            'pop_factor': df_candidates.iloc[s_idx]['population_total'] / max_pop
        }

    # Normalize customer factor to 0-1 range for optimization weighting
    all_weighted = [s['customers_weighted'] for s in location_stats.values()]
    mx, mn = (max(all_weighted), min(all_weighted)) if all_weighted else (1, 0)
    for loc_id in location_stats:
        location_stats[loc_id]['customer_factor'] = (location_stats[loc_id]['customers_weighted'] - mn) / (mx - mn) if mx > mn else 1.0
       
    # Generate mapping for all customers: customers can be covered by following locations      
    cust_to_loc = {k_idx: [loc_id for loc_id, ids in coverage.items() if k_idx in ids] for k_idx in range(len(df_demand))}
    return cust_to_loc, location_stats

def optimize_locations(df_demand, df_candidates, coverage, location_stats, config):
    """Solve the location optimization problem using linear programming."""
    
    logging.info("Starting PuLP optimization...")
    
    # Create optimization problem (Minimization) and decision variables (0 for not opened/not covered, 1 for opened/ covered)
    problem = pulp.LpProblem("Location_Optimization", pulp.LpMinimize)
    is_opened = pulp.LpVariable.dicts("loc", df_candidates.index, cat=pulp.LpBinary)
    is_served = pulp.LpVariable.dicts("cust", df_demand.index, cat=pulp.LpBinary)
    
    # Define objective function with cost incentives and bonuses
    costs = []
    for i in df_candidates.index:
        base_cost = config['cost_top_city'] if df_candidates.at[i, 'is_top_200'] else config['cost_standard']
        bonus = (location_stats[i]['customer_factor'] * config['customer_bonus']) + \
                (location_stats[i]['pop_factor'] * config['prestige_bonus'])
        costs.append(is_opened[i] * (base_cost - bonus))
    
    # Load solver with cost function
    problem += pulp.lpSum(costs)
    
    # Add coverage constraints (every customer should be covered by at least one location) 
    # and service level requirement
    for k in df_demand.index:
        problem += pulp.lpSum(is_opened[s] for s in coverage.get(k, [])) >= is_served[k]
    
    demand_col = 'customer_count'
    min_required = df_demand[demand_col].sum() * config['service_level']
    problem += pulp.lpSum(is_served[i] * df_demand.at[i, demand_col] for i in df_demand.index) >= min_required
    
    # Solve and return results
    problem.solve(pulp.PULP_CBC_CMD(msg=False))
    logging.info(f"Optimization Status: {pulp.LpStatus[problem.status]}")
    return problem, is_opened, is_served # Return problem to check status in main

# =============================================================================
# EXPORT & VISUALIZATION
# =============================================================================

def export_results_to_csv(df_candidates, is_opened, stats, constraint_name):
    """Export opened locations and their coverage statistics to CSV file."""
    
    results_path = os.path.join(SCRIPT_DIR, 'results', f'optimized_locations_{constraint_name}.csv')
    logging.info(f"Generating results CSV: {results_path}")
    
    # Identify and collect all opened locations
    opened_indices = [idx for idx in df_candidates.index if is_opened[idx].value() > 0.5]
    
    # Build export data with formatted statistics
    export_data = []
    for idx in opened_indices:
        row = df_candidates.loc[idx]
        export_data.append({
            'city_name': row['city_name'],
            'plz': row['plz'],
            'city_type': 'Top 200' if row['is_top_200'] else 'Standard',
            'patients_covered_weighted': round(stats[idx]['customers_weighted'], 2),
            'patients_covered_total': int(stats[idx]['customers_total'])
        })
    
    # Save to CSV with proper formatting
    df_results = pd.DataFrame(export_data)
    df_results = df_results.sort_values(by='patients_covered_total', ascending=False)
    df_results.to_csv(results_path, index=False, encoding='utf-8')
    logging.info(f"Export successful. {len(df_results)} locations exported.")

def visualize_and_open(df_candidates, df_demand, is_opened, is_served, stats, constraint_name, config):
    """Create an interactive map dashboard and save it as HTML."""
    
    logging.info(f"Creating final dashboard map for {constraint_name}...")
    
    # Initialize map centered on Germany
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6, control_scale=True)
    
    # Calculate key metrics for the legend
    demand_col = 'customer_count'
    total_customers_data = int(df_demand[demand_col].sum())
    opened_indices = [idx for idx in df_candidates.index if is_opened[idx].value() > 0.5]
    num_opened = len(opened_indices)
    
    covered_customers = sum(
        df_demand.at[idx, demand_col] 
        for idx in df_demand.index 
        if is_served[idx].value() > 0.5
    )

    # Plot opened locations with popup information
    for idx in opened_indices:
        row = df_candidates.loc[idx]
        
        popup_html = f"""
        <div style="font-family: Arial; width: 220px;">
            <h4 style="margin-bottom:5px;">{row['city_name']}</h4>
            <hr>
            <b>Status:</b> Opened<br>
            <b>Total Customers in Reach:</b> {stats[idx]['customers_total']:.0f}<br>
            <b>Weighted Potential:</b> {stats[idx]['customers_weighted']:.1f}<br>
            <b>City Type:</b> {'Top 200' if row['is_top_200'] else 'Standard'}
        </div>
        """
        
        folium.Marker(
            [row['lat'], row['lon']], 
            icon=folium.Icon(color='blue', icon='shopping-cart', prefix='fa'), 
            popup=folium.Popup(popup_html, max_width=250)
        ).add_to(m)
        
        # Visualize catchment radius
        folium.Circle(
            [row['lat'], row['lon']], 
            radius=config['max_distance_km'] * 1000, 
            color='blue', 
            fill=True, 
            fill_opacity=0.1,
            weight=1
        ).add_to(m)

    # Add constraints legend (top legend)
    constraints_html = f'''
    <div style="
        position: fixed; 
        bottom: 250px; right: 50px; width: 300px; height: 160px; 
        background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
        padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        ">
        <b style="font-size: 16px;">Constraint Set</b><br>
        <b style="font-size: 13px; color: #0066cc;">{constraint_name}</b><br>
        <hr style="margin: 8px 0;">
        <i class="fa fa-road" style="color:#d9534f"></i> Max Distance: <b>{config['max_distance_km']}km</b><br>
        <i class="fa fa-line-chart" style="color:#5cb85c"></i> Decay Start: <b>{config['decay_start_km']}km</b><br>
        <i class="fa fa-money" style="color:#f0ad4e"></i> Top City Cost: <b>{config['cost_top_city']}</b><br>
        <i class="fa fa-money" style="color:#f0ad4e"></i> Standard Cost: <b>{config['cost_standard']}</b>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(constraints_html))

    # Add dashboard legend with key performance indicators (bottom legend)
    legend_html = f'''
    <div style="
        position: fixed; 
        bottom: 50px; right: 50px; width: 300px; height: 160px; 
        background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
        padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        ">
        <b style="font-size: 16px;">Results & Performance</b><br>
        <hr style="margin: 8px 0;">
        <i class="fa fa-users" style="color:navy"></i> Total Customers: <b>{total_customers_data:,}</b><br>
        <i class="fa fa-map-marker" style="color:blue"></i> Opened Locations: <b>{num_opened}</b><br>
        <i class="fa fa-check-circle" style="color:green"></i> Covered Customers: <b>{int(covered_customers):,}</b><br>
        <i class="fa fa-pie-chart" style="color:orange"></i> Actual Service Level: <b>{(covered_customers/total_customers_data)*100:.1f}%</b>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # Save map and open in browser
    map_path = os.path.join(SCRIPT_DIR, 'results', f'location_optimization_dashboard_{constraint_name}.html')
    m.save(map_path)
    
    logging.info(f"Dashboard saved: {map_path}")
    logging.info(f"Result: {num_opened} locations cover {int(covered_customers)} customers.")
    webbrowser.open('file://' + os.path.realpath(map_path))

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def start_optimize():
    """Execute the complete location optimization workflow."""
    # 1. Logging start
    log_separator()
    logging.info("--- Optimization Process Started ---")
    logging.info(f"Processing {len(CONSTRAINT_SETS)} constraint set(s)...")
    
    # 2. Data loading and enrichment (done once, shared across all iterations)
    df_candidates, df_demand = read_data()
    df_candidates = add_coordinates(df_candidates, 'plz')
    df_demand = add_coordinates(df_demand, 'plz5')
    
    # 3. Iterate through each constraint set
    for iteration, constraint_set in enumerate(CONSTRAINT_SETS, start=1):
        logging.info(f"\n{'='*60}")
        logging.info(f"ITERATION {iteration}: {constraint_set['name']} (max_distance: {constraint_set['max_distance_km']}km, decay_start: {constraint_set['decay_start_km']}km)")
        logging.info(f"{'='*60}")
        
        # Create config for this iteration by combining base and constraint set
        config = {**BASE_CONFIG, **constraint_set}
        
        # Coverage calculation with current constraints
        coverage, stats = calculate_coverage(df_demand, df_candidates, config)
        
        # Run optimization
        problem, is_opened, is_served = optimize_locations(df_demand, df_candidates, coverage, stats, config)

        # Export and Visualization only if optimal solution found
        if pulp.LpStatus[problem.status] == 'Optimal':
            visualize_and_open(df_candidates, df_demand, is_opened, is_served, stats, constraint_set['name'], config)
            export_results_to_csv(df_candidates, is_opened, stats, constraint_set['name'])
            logging.info(f"Iteration {iteration} completed successfully.")
        else:
            logging.error(f"Iteration {iteration} - Solution status: {pulp.LpStatus[problem.status]}. Export and Visualization skipped.")
    
    # 4. Logging completion
    logging.info(f"\n{'='*60}")
    logging.info("--- All Optimization Iterations Finished Successfully ---")
    logging.info(f"{'='*60}")

if __name__ == "__main__":
    start_optimize()