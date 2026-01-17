# Location Optimization System v2.0

## Reason why - my motivation

**The problem**: How to select minimal amount of outlets to cover a majority of customers? 

*A classic optimization problem.*

This repo showcases solutions for this classic real-world problem (Set Coverage Problem). This repo goes the whole way. From data collection, cleaning, optimization algorythms and finally map visualization of outcomes. 

**Inspired by** a business question of my recent intern.

**The solution**, a modular Python system for optimizing customer service location placement using linear programming (PuLP) and interactive visualization (Folium).

## 📁 Project Structure

```
project_root/
│
├── main.py                      # Main orchestrator script
├── config.py                    # Centralized configuration
│
├── modules/                     # Core functionality modules
│   ├── __init__.py
│   ├── validator.py            # Data validation (8 checks)
│   ├── data_loader.py          # City data loading & geocoding
│   ├── customer_generator.py   # Synthetic customer generation
│   ├── optimizer.py            # PuLP optimization engine
│   └── visualizer.py           # Interactive map creation
│
├── sources/                     # Input data files
│   ├── german_cities.xlsx
│   ├── ger_plz-5stellig.topojson
│   └── states_ger_geo.json
│
├── results/                     # Output files
│   ├── customers.csv
│   ├── optimized_locations_*.csv
│   └── optimization_map_*.html
│
├── _archive/                    # Original scripts (for reference)
│   ├── optimize_locations.py
│   ├── draw_map.py
│   ├── generate_customers.py
│   └── read_and_clean_city_data.py
│
└── optimization_process.log     # Unified log file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install folium pandas numpy pulp pgeocode scikit-learn branca openpyxl
```

### 2. Run the System

```bash
python main.py
```

### 3. Follow Interactive Prompts

The system will:
1. Validate all input files
2. Load and clean city data
3. Load existing customers (or generate new ones)
4. Ask which constraint sets to run
5. Run optimizations
6. Create comprehensive maps
7. Open results in browser

## 🔧 Configuration

All settings are centralized in `config.py`:

### Key Parameters

```python
# Optimization
service_level = 0.90          # 90% customer coverage required
customer_bonus = 0.2          # Bonus for high-density locations
prestige_bonus = 0.1          # Bonus for top 200 cities

# Customer Generation
total_customers = 90000
distribution = {
    'top10': 0.40,            # 40% in top 10 cities
    'top200': 0.56,           # 56% in cities 11-200
    'rural': 0.04             # 4% rural
}

# Constraint Sets
CONSTRAINT_SETS = [
    {
        'name': 'Conservative',
        'max_distance_km': 100.0,
        'decay_start_km': 90.0,
        'cost_top_city': 0.8,
        'cost_standard': 1.0,
    },
    # Add more sets as needed
]
```

## 📊 Output Files

### CSV Files
- `customers.csv` - Generated customer distribution
- `optimized_locations_{constraint_name}.csv` - Opened locations with statistics

### HTML Maps
- `optimization_map_{constraint_name}.html` - Interactive maps with:
  - **Choropleth Layer**: Customer density by postal code
  - **Location Markers**: Optimized outlet locations
  - **Catchment Areas**: Service radius circles
  - **State Borders**: Geographic reference
  - **Legends**: Constraints and performance metrics

## ✅ Validation Features

The system performs 8 comprehensive validation checks:

1. ✓ **File Existence** - Verifies all required input files
2. ✓ **File Structure** - Checks required columns
3. ✓ **Constraint Logic** - Validates parameter relationships
4. ✓ **Optimization Status** - Ensures solution is optimal
5. ⚠ **Geocoding Quality** - Reports failed geocoding (warns if >5%)
6. ⚠ **Coordinate Bounds** - Checks if locations are within Germany
7. ⚠ **Coverage Feasibility** - Warns if service level is tight/impossible
8. ⚠ **Customer Distribution** - Validates total customer counts
10. ⚠ **Duplicate PLZ** - Sums duplicate postal codes with warning

**✓ = Critical (stops process) | ⚠ = Warning (displays 5s, continues)**

## 🎯 Workflow

```
1. Pre-flight Check
   └─→ Validate input files

2. Data Preparation
   ├─→ Load & clean city data
   ├─→ Geocode locations
   ├─→ Load/generate customers
   └─→ Validate data quality

3. Constraint Selection
   └─→ User selects which scenarios to run

4. Optimization Loop
   ├─→ Calculate coverage matrix
   ├─→ Run PuLP optimization
   └─→ Validate results

5. Export Results
   └─→ Save CSV files with location data

6. Visualization
   ├─→ Create comprehensive maps
   └─→ Open in browser
```

## 🔄 Customer Data Handling

The system intelligently handles customer data:

- **First run**: Generates synthetic customers → saves to `customers.csv`
- **Subsequent runs**: Loads from `customers.csv` (faster)
- **Force regeneration**: Delete `customers.csv` or modify `customer_generator.py`

## 📝 Logging

All operations are logged to `optimization_process.log` with format:
```
2025-01-16 15:30:45 - [module_name] - INFO - Message
```

Each module clearly identifies itself for easy debugging.

## 🎨 Map Features

The comprehensive maps include:

### Interactive Layers (toggle on/off)
- Customer Distribution (PLZ choropleth)
- Optimized Locations (markers + circles)
- Federal State Borders

### Legends
- **Constraint Parameters**: Max distance, decay, costs
- **Performance Metrics**: Total/covered customers, service level
- **Color Scale**: Customer density gradient

### Tooltips
- PLZ codes with customer counts
- Location details with coverage statistics

## 🛠️ Customization

### Adding New Constraint Sets

Edit `config.py`:
```python
CONSTRAINT_SETS.append({
    'name': 'Custom',
    'max_distance_km': 60.0,
    'decay_start_km': 30.0,
    'cost_top_city': 0.7,
    'cost_standard': 0.9,
})
```

### Adjusting Validation Thresholds

Edit `config.py`:
```python
VALIDATION = {
    'geocoding_warning_threshold': 0.05,  # Warn if >5% fail
    'warning_display_seconds': 5,         # Countdown duration
    # ... more settings
}
```

## 🐛 Troubleshooting

### "Missing required input files"
→ Ensure `sources/` folder contains all GeoJSON/TopoJSON files

### "Geocoding failure rate is high"
→ Check if PLZ codes in source data are valid German postal codes

### "Service level is impossible"
→ Increase `max_distance_km` or reduce `service_level` in config

### "Optimization status: Infeasible"
→ Constraints are too restrictive; adjust constraint set parameters

## 📚 Module Reference

### `validator.py`
- `check_input_files()` - Verify file existence
- `check_constraint_logic()` - Validate parameters
- `check_coverage_feasibility()` - Pre-optimization checks
- `check_optimization_result()` - Post-optimization validation

### `data_loader.py`
- `load_and_clean_cities()` - Process city data
- `add_coordinates()` - Geocode locations

### `customer_generator.py`
- `load_or_generate_customers()` - Smart customer data handling
- `generate_customer_data()` - Synthetic data generation

### `optimizer.py`
- `calculate_coverage()` - Distance matrix computation
- `run_optimization()` - PuLP solver execution
- `export_results()` - CSV output

### `visualizer.py`
- `create_comprehensive_map()` - Unified map generation
- Internal layer functions for choropleth, markers, legends

## 📄 License

This is a private project. All rights reserved.

## 🤝 Contributing

For improvements or bug reports, contact the project maintainer.

---

**Version**: 2.0  
**Last Updated**: January 2025  
**Python**: 3.8+
