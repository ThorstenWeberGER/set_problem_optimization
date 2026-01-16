"""
Visualizer Module
Creates comprehensive interactive maps combining optimization results and customer distribution.
Merges functionality from draw_map.py and optimize_locations.py visualization.
"""

import logging
import json
import folium
import pandas as pd
import branca.colormap as cm
import config

logger = logging.getLogger(__name__)


def create_comprehensive_map(df_candidates: pd.DataFrame, df_demand: pd.DataFrame,
                             is_opened: dict, is_served: dict, location_stats: dict,
                             constraint_set: dict) -> folium.Map:
    """
    Create unified map with:
    - Choropleth PLZ layer (color-coded by customer density)
    - Optimized location markers with catchment areas
    - State borders
    - Multiple legends
    
    Args:
        df_candidates: Candidate locations
        df_demand: Customer demand data
        is_opened: Opened location decision variables
        is_served: Served customer decision variables
        location_stats: Statistics for each location
        constraint_set: Constraint parameters used
        
    Returns:
        Folium Map object
    """
    logger.info("="*60)
    logger.info(f"CREATING COMPREHENSIVE MAP: {constraint_set['name']}")
    logger.info("="*60)
    
    # Initialize base map
    logger.info("Creating base map...")
    m = folium.Map(
        location=[51.1657, 10.4515],  # Center of Germany
        zoom_start=6,
        tiles="CartoDB Positron",
        control_scale=True
    )
    
    # Add layers in order (bottom to top)
    _add_postal_code_choropleth_layer(m, df_demand)
    _add_state_borders_layer(m)
    _add_optimized_locations_layer(m, df_candidates, is_opened, location_stats, constraint_set)
    
    # Add legends
    _add_constraint_legend(m, constraint_set)
    _add_performance_legend(m, df_demand, is_opened, is_served)
    
    # Add color scale for choropleth
    _add_color_scale_legend(m, df_demand)
    
    # Add layer control
    folium.LayerControl(collapsed=False, autoZIndex=True).add_to(m)
    
    # Save map
    map_path = config.PATHS['map_output'].format(constraint_set['name'])
    m.save(map_path)
    logger.info(f"✓ Map saved to: {map_path}")
    
    return m


def _add_postal_code_choropleth_layer(map_obj: folium.Map, df_customers: pd.DataFrame) -> None:
    """
    Add PLZ choropleth layer showing customer density.
    """
    logger.info("Adding postal code choropleth layer...")
    
    try:
        # Load TopoJSON
        with open(config.PATHS['plz_topojson'], 'r', encoding='utf-8') as f:
            topojson_data = json.load(f)
        
        if 'objects' not in topojson_data:
            logger.error("Invalid TopoJSON format")
            return
        
        logger.info(f"  TopoJSON loaded: {list(topojson_data['objects'].keys())}")
        
        # Create feature group
        fg_plz = folium.FeatureGroup(name="Customer Distribution (PLZ)", show=True)
        
        # Convert customer data to PLZ-to-count mapping
        customer_map = {
            str(plz).split('.')[0].zfill(5): count
            for plz, count in zip(df_customers['plz5'], df_customers['customer_count'])
        }
        
        # Add customer counts to TopoJSON geometries
        if 'data' in topojson_data['objects']:
            geometries = topojson_data['objects']['data'].get('geometries', [])
            logger.info(f"  Processing {len(geometries)} PLZ geometries...")
            
            for geometry in geometries:
                if isinstance(geometry, dict) and 'properties' in geometry:
                    props = geometry['properties']
                    plz_val = props.get('plz') or props.get('postal_code') or props.get('plz5')
                    
                    if plz_val:
                        key = str(plz_val).split('.')[0].zfill(5)
                        props['customer_count'] = customer_map.get(key, 0)
                    else:
                        props['customer_count'] = 0
        
        # Create color scale
        min_val = df_customers['customer_count'].min()
        max_val = 50  # Manual cap for better visualization
        colormap = cm.linear.viridis.scale(min_val, max_val)
        
        def get_color(feature):
            """Get color based on customer count."""
            customers = 0
            if feature and 'properties' in feature:
                customers = feature['properties'].get('customer_count', 0)
            try:
                return colormap(customers)
            except:
                return '#cccccc'
        
        # Create TopoJSON layer
        topo = folium.TopoJson(
            topojson_data,
            'objects.data',
            style_function=lambda feature: {
                'fillColor': get_color(feature),
                'color': '#999999',
                'weight': 0.5,
                'opacity': 0.3,
                'fillOpacity': 0.55,
            }
        )
        
        # Add tooltip
        folium.GeoJsonTooltip(
            fields=['plz', 'customer_count'],
            aliases=['PLZ:', 'Customers:'],
            style=("background-color: white; color: #333; font-family: sans-serif; "
                   "font-size: 12px; padding: 10px;")
        ).add_to(topo)
        
        topo.add_to(fg_plz)
        fg_plz.add_to(map_obj)
        logger.info("  ✓ Choropleth layer added")
        
    except FileNotFoundError:
        logger.error(f"TopoJSON file not found: {config.PATHS['plz_topojson']}")
    except Exception as e:
        logger.error(f"Error adding choropleth layer: {e}")


def _add_state_borders_layer(map_obj: folium.Map) -> None:
    """
    Add German federal state borders.
    """
    logger.info("Adding state borders...")
    
    try:
        with open(config.PATHS['states_geojson'], 'r', encoding='utf-8') as f:
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
        logger.info("  ✓ State borders added")
        
    except FileNotFoundError:
        logger.warning(f"State borders file not found: {config.PATHS['states_geojson']}")
    except Exception as e:
        logger.error(f"Error adding state borders: {e}")


def _add_optimized_locations_layer(map_obj: folium.Map, df_candidates: pd.DataFrame,
                                   is_opened: dict, location_stats: dict, 
                                   constraint_set: dict) -> None:
    """
    Add optimized location markers with catchment areas.
    """
    logger.info("Adding optimized locations and catchment areas...")
    
    fg_locations = folium.FeatureGroup(name="Optimized Locations", show=True)
    opened_indices = [idx for idx in df_candidates.index if is_opened[idx].value() > 0.5]
    
    for idx in opened_indices:
        row = df_candidates.loc[idx]
        
        # Create detailed popup
        popup_html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 10px;">
            <strong style="color: #2c3e50; font-size: 14px;">{row['city_name']}</strong><br>
            <span style="color: #7f8c8d; font-size: 11px;">PLZ: {row['plz']}</span>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 8px 0;">
            <table style="width: 100%; font-size: 12px;">
                <tr><td><strong>Status:</strong></td><td style="text-align: right;">Opened</td></tr>
                <tr><td><strong>City Type:</strong></td><td style="text-align: right;">{'Top 200' if row['is_top_200'] else 'Standard'}</td></tr>
                <tr><td><strong>Customers (Total):</strong></td><td style="text-align: right;">{location_stats[idx]['customers_total']:.0f}</td></tr>
                <tr><td><strong>Customers (Weighted):</strong></td><td style="text-align: right;">{location_stats[idx]['customers_weighted']:.1f}</td></tr>
            </table>
        </div>
        """
        
        # Add marker
        folium.Marker(
            location=[row['lat'], row['lon']],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"Location: {row['city_name']}",
            icon=folium.Icon(color='blue', icon='map-marker', prefix='fa')
        ).add_to(fg_locations)
        
        # Add catchment radius circle
        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=constraint_set['max_distance_km'] * 1000,  # Convert to meters
            color='blue',
            fill=True,
            fill_opacity=0.1,
            weight=1
        ).add_to(fg_locations)
    
    fg_locations.add_to(map_obj)
    logger.info(f"  ✓ Added {len(opened_indices)} optimized locations")


def _add_constraint_legend(map_obj: folium.Map, constraint_set: dict) -> None:
    """
    Add legend showing constraint parameters used.
    """
    constraints_html = f'''
    <div style="
        position: fixed; 
        bottom: 250px; right: 50px; width: 300px; height: 160px; 
        background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
        padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        ">
        <b style="font-size: 16px;">Constraint Set</b><br>
        <b style="font-size: 13px; color: #0066cc;">{constraint_set['name']}</b><br>
        <hr style="margin: 8px 0;">
        <i class="fa fa-road" style="color:#d9534f"></i> Max Distance: <b>{constraint_set['max_distance_km']}km</b><br>
        <i class="fa fa-line-chart" style="color:#5cb85c"></i> Decay Start: <b>{constraint_set['decay_start_km']}km</b><br>
        <i class="fa fa-money" style="color:#f0ad4e"></i> Top City Cost: <b>{constraint_set['cost_top_city']}</b><br>
        <i class="fa fa-money" style="color:#f0ad4e"></i> Standard Cost: <b>{constraint_set['cost_standard']}</b>
    </div>
    '''
    map_obj.get_root().html.add_child(folium.Element(constraints_html))


def _add_performance_legend(map_obj: folium.Map, df_demand: pd.DataFrame,
                            is_opened: dict, is_served: dict) -> None:
    """
    Add legend showing optimization results and KPIs.
    """
    total_customers = df_demand['customer_count'].sum()
    num_opened = sum(1 for v in is_opened.values() if v.value() > 0.5)
    covered_customers = sum(
        df_demand.at[idx, 'customer_count']
        for idx in df_demand.index
        if is_served[idx].value() > 0.5
    )
    
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
        <i class="fa fa-users" style="color:navy"></i> Total Customers: <b>{int(total_customers):,}</b><br>
        <i class="fa fa-map-marker" style="color:blue"></i> Opened Locations: <b>{num_opened}</b><br>
        <i class="fa fa-check-circle" style="color:green"></i> Covered Customers: <b>{int(covered_customers):,}</b><br>
        <i class="fa fa-pie-chart" style="color:orange"></i> Actual Service Level: <b>{(covered_customers/total_customers)*100:.1f}%</b>
    </div>
    '''
    map_obj.get_root().html.add_child(folium.Element(legend_html))


def _add_color_scale_legend(map_obj: folium.Map, df_customers: pd.DataFrame) -> None:
    """
    Add color scale legend for choropleth layer.
    """
    min_val = df_customers['customer_count'].min()
    max_val = 50  # Manual cap for better visualization
    
    colormap = cm.linear.viridis.scale(min_val, max_val)
    colormap.caption = 'Customers per PLZ'
    colormap.add_to(map_obj)
