"""
Script Name: draw_map.py

Purpose:
    This script generates an interactive map visualizing customer distribution across 
    German postal code areas (PLZ5) colored by customer density and company locations.

Key Functionalities:
    1. Data Generation: Creates synthetic customer data with realistic distributions 
       (exponential/beta) mapped to postal codes read from a TopoJSON file.
    2. Map Visualization: Uses Folium to create an interactive map.
    3. Layers:
       - Postal Code Areas: TopoJSON layer colored by customer density (Choropleth).
       - Company Locations: Markers with popups showing status and metrics.
       - State Borders: GeoJSON layer for regional context.
    4. Output: Saves the final visualization as an HTML file ('kunden_analyse_premium.html').

Dependencies: folium, pandas, numpy, json, os
"""
     
import folium
import pandas as pd
import json
import random
import numpy as np
import os
import logging

# == CONFIGURATION ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # returns directory of this python file
PARENT_DIR = os.path.dirname(SCRIPT_DIR) # used on a directory it returns the parent directory

# Base configuration (shared across all constraint sets)
BASE_CONFIG = {
    'map_path': os.path.join(PARENT_DIR, 'results', 'customers_outlets_map.html'),
    'plz5_path': os.path.join(PARENT_DIR, 'sources', 'ger_plz-5stellig.topojson'),
    'state_borders_path': os.path.join(PARENT_DIR, 'sources', 'states_ger_geo.json'),
    'log_file': os.path.join(PARENT_DIR, 'optimization_process.log'),
    'demand_path': os.path.join(PARENT_DIR, 'results', 'customers.csv')
}


def get_real_world_data(demand_path=BASE_CONFIG['demand_path']) -> pd.DataFrame:
    """
    Read customers data.
    """
    logging.info("Reading customer files...")
    try:
        data = pd.read_csv(demand_path, sep=',', usecols=['plz5', 'customer_count'])
        logging.info(f"Loaded {len(data)} demand points.")
        return pd.DataFrame(data)
    except:
        logging.error('Error reading customers data.')

def get_location_data() -> list:
    """Defines locations with contrast colors."""
    return [
        {"name": "Headquarters North", "lat": 53.5511, "lon": 9.9937, "customers": 1250, "status": "active"},
        {"name": "Hub West", "lat": 50.9375, "lon": 6.9603, "customers": 890, "status": "planned"},
        {"name": "Branch South", "lat": 48.1351, "lon": 11.5820, "customers": 2100, "status": "active"},
        {"name": "Regional Office East", "lat": 52.5200, "lon": 13.4050, "customers": 1420, "status": "planned"}
    ]

def get_color_scale(df_customers):
    """
    Creates a dynamic color scale based on data quantiles.
    Uses 'Viridis' - a colorblind-friendly and high-contrast palette.
    """
    logging.info('Generating color scale based on customers data.')
    
    import branca.colormap as cm
    
    min_val = df_customers['customer_count'].min()
    max_val = 50 # manual override required for better color presentation | df_customers['customer_count'].max()
        
    colormap = cm.linear.viridis.scale(min_val, max_val)
    colormap.caption = 'Customer_count per PLZ5'
    
    logging.info('Color scale generated successfully.')
    return colormap

def add_location_layer(map_obj, locations):
    """Adds locations with high contrast."""
    
    logging.info('Adding locations to map...')
    fg_locations = folium.FeatureGroup(name="Company Locations", show=True)

    for loc in locations:
        icon_color = 'red' if loc['status'] == 'active' else 'cadetblue'
        
        html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 10px;">
            <strong style="color: #2c3e50; font-size: 14px;">{loc['name']}</strong><br>
            <span style="color: #7f8c8d; font-size: 11px;">Status: {loc['status']}</span>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 8px 0;">
            <table style="width: 100%; font-size: 12px;">
                <tr><td><strong>Customers:</strong></td><td style="text-align: right;">{loc['customers']}</td></tr>
                <tr><td><strong>Lat:</strong></td><td style="text-align: right;">{loc['lat']:.2f}</td></tr>
            </table>
        </div>
        """
        
        folium.Marker(
            location=[loc['lat'], loc['lon']],
            popup=folium.Popup(html, max_width=250),
            tooltip=f"Location: {loc['name']}",
            icon=folium.Icon(color=icon_color, icon='map-marker', prefix='fa')
        ).add_to(fg_locations)

    fg_locations.add_to(map_obj)
    logging.info('Locations added to map successfully.')

def add_postal_code_layer(map_obj, geojson_path, customer_data=None):
    """
    Adds German postal codes (PLZ5) as Choropleth layer.
    FIXED VERSION: Properly handles TopoJSON format and adds customer data.
    """
    
    logging.info('Adding postal code layer to map...')
    
    try:
        # Reading topojson format
        logging.info("    [PLZ] Loading TopoJSON file...")
        with open(geojson_path, 'r', encoding='utf-8') as f:
            topojson_data = json.load(f)
        # Check if TopoJSON
        if 'objects' not in topojson_data:
            logging.error(f"    [PLZ] ✗ Error: This is not a TopoJSON file!")
            return
        logging.info(f"    [PLZ] ✓ TopoJSON file detected with objects: {list(topojson_data['objects'].keys())}")

        # Create folium feature group        
        fg_plz = folium.FeatureGroup(name="Postal Codes (PLZ5)", show=False)
        
        logging.info("    [PLZ] Processing customer data...")
        # Convert customer data to plz-to-customer_count dictionary for fast lookups
        customer_map = {}
        if customer_data is not None:
            # Normalize PLZ to 5-digit strings to ensure matching works (handles int/str/float types)
            customer_map = {
                str(plz).split('.')[0].zfill(5): count 
                for plz, count in zip(customer_data['plz5'], customer_data['customer_count'])
            }
                 
        logging.info("    [PLZ] Adding customer counts to TopoJSON geometries...")        
        # Access the correct path: objects -> data -> geometries
        if 'data' in topojson_data['objects']:
            geometries_list = topojson_data['objects']['data'].get('geometries', [])
            logging.info(f"    [PLZ] Found {len(geometries_list)} PLZ5 geometries in 'data' object")
            
            # Add customer data to each geometry's properties
            for i, geometry in enumerate(geometries_list):
                if isinstance(geometry, dict) and 'properties' in geometry:
                    props = geometry['properties']
                    
                    # Try differnet options for possible field names
                    plz_val = props.get('plz') or props.get('postal_code') or props.get('plz5')
                    
                    if plz_val:
                        # Add customer count to properties
                        key = str(plz_val).split('.')[0].zfill(5)
                        props['customer_count'] = customer_map.get(key, 0)
                    else:
                        props['customer_count'] = 0
                        
            logging.info("    [PLZ] ✓ Customer counts added to all geometries")
        else:
            logging.error(f"    [PLZ] ✗ Error: 'data' object not found in TopoJSON")
            return
        
        # Generate dynamic color scale from customer data
        logging.info("    [PLZ] Generating dynamic color scale...")
        viridis_scale = get_color_scale(customer_data)
        
        # Color function: Colors based on customer count and colorscale passed
        def get_color(feature, colorscale):
            """Returns color based on customer count using viridis color scale."""
            customers = 0
            if feature and 'properties' in feature:
                customers = feature['properties'].get('customer_count', 0)
            
            # Use the viridis_scale to get the color (returns hex string like '#440154')
            try:
                color = colorscale(customers)
                return color
            except Exception as e:
                logging.warning(f"    [PLZ] Warning: Error getting color for {customers} customers: {e}")
                return '#cccccc'  # Fallback gray color
        
        # Create TopoJson layer
        logging.info("    [PLZ] Creating TopoJson layer with styling...")
        topo = folium.TopoJson(
            topojson_data,
            'objects.data',
            style_function=lambda feature: {
                'fillColor': get_color(feature, viridis_scale),
                'color': '#999999',
                'weight': 0.5,
                'opacity': 0.3,
                'fillOpacity': 0.55,
            }
        )   
        # Add tooltip to the TopoJson layer
        folium.GeoJsonTooltip(
            fields=['plz', 'customer_count'],
            aliases=['PLZ:', 'Customers:'],
            style=("background-color: white; color: #333; font-family: sans-serif; "
                   "font-size: 12px; padding: 10px;")
        ).add_to(topo)       
        topo.add_to(fg_plz)
        fg_plz.add_to(map_obj)
        logging.info("    [PLZ] ✓ Tooltip and FeatureGroup added to map")

    except FileNotFoundError:
        logging.error(f"    [PLZ] ✗ Error: TopoJSON file not found at '{geojson_path}'")
    except Exception as e:
        logging.error(f"    [PLZ] ✗ Error: {e}")
        import traceback
        traceback.print_exc()

def add_state_borders(map_obj, geojson_path):
    """Adds borders of German federal states as a layer."""
    try:
        logging.info('Adding federal state borders to map')
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        fg_states = folium.FeatureGroup(name="Federal State Borders", show=True)
        
        folium.GeoJson(
            geojson_data,
            style_function=lambda feature: {
                'fillColor': 'transparent',
                'color': '#555555',
                'weight': 0.6,
                'opacity': 0.6,
                'dashArray': '5, 5'
            }
        ).add_to(fg_states)
        
        fg_states.add_to(map_obj)

    except FileNotFoundError:
        logging.warning(f"Warning: GeoJSON file '{geojson_path}' not found.")
    except Exception as e:
        logging.error(f"Error loading federal state borders: {e}")

def create_map(df=None, locs=None, states_geojson=BASE_CONFIG['state_borders_path'], 
               plz_geojson=BASE_CONFIG['plz5_path']):
    """
    Main function for map creation. Can be called as a module.
    Returns the Folium Map object.
    """
    logging.info("\n" + "="*60)
    logging.info("MAP CREATION PROCESS STARTED")
    logging.info("="*60)
    
    # Fallback to dummy data if none provided
    if df is None:
        logging.info("Reading customer data...")
        df = get_real_world_data()
    if locs is None:
        logging.info("Loading location data...")
        locs = get_location_data()
    
    # Build script-relative paths for GeoJSON files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    states_path = os.path.join(script_dir, states_geojson)
    plz_path = os.path.join(script_dir, plz_geojson)
    
    # Create map (without tiles in Layer Control)
    logging.info("Creating base Folium map...")
    m = folium.Map(
        location=[51.1657, 10.4515], 
        zoom_start=6, 
        tiles="CartoDB Positron", 
        control_scale=True
    )

    # Color scale
    logging.info("Generating color scale...")
    viridis_scale = get_color_scale(df)

    # Add layers
    logging.info("\nAdding layers to map:")
    try:
        add_postal_code_layer(m, plz_path, customer_data=df)
        logging.info("- Postal code layer added successfully")
        
        add_state_borders(m, states_path)
        logging.info("- State borders layer added successfully")
        
        add_location_layer(m, locs)
        logging.info("- Location layer added successfully")
    
    except Exception as e:
        logging.error(f"✗ Error while adding layers: {e}")
        import traceback
        traceback.print_exc()
    
    # Layer switcher (shows only overlays, no base tiles)
    logging.info("Adding layer control...")
    folium.LayerControl(collapsed=False, autoZIndex=True).add_to(m)
    
    logging.info("MAP CREATION SUCCESSFULLY COMPLETED")
   
    return m

if __name__ == "__main__":
    # Test execution when script is started directly
    logging.info("Starting map creation...")
    map_instance = create_map()
    
    map_instance.save(BASE_CONFIG['map_path'])
    logging.info("Map saved to BASE_CONFIG['map_path']")