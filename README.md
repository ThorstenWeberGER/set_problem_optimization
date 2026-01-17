# Set Coverage Optimizer - where to open a store? 

<img src="collaterals/thinking_hard.png" width="500" alt="Heatmap">

## Reason why - my motivation

**The problem**: How to select minimal amount of outlets to cover a majority of customers? This is a classic optimization problem and can safe a lot of money. 

**Inspired by** a real world business question during my recent intern.

**Fun fact**: As a Management Consultant I did this with my brain, with a good map and some excel sheets. And always it was a long discussion - what is better. We did not use the math...

**The solution**: I used linear programming (PulP) optimizing the locations based on certain constraints. And the output is not just a list, but a beautiful interactive map visualization (Folium). Check it out.

**Includes**
- Set Coverage Problem Solver
- Data collection and cleaning
- Map visualization of outcomes
- Strong data quality foundation
- Logging, testing, validation 

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

### 3. System workflow

<img src="collaterals/workflow.png" width="400" alt="Heatmap">



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
  - **Legends**: Constraints and performance metrics

## ✅ Validation Features

The system performs 9+ comprehensive validation checks:

1. ✓ **File Existence** - Verifies all required input files
2. ✓ **File Structure** - Checks required columns
3. ✓ **Constraint Logic** - Validates parameter relationships
4. ✓ **Optimization Status** - Ensures solution is optimal
5. ⚠ **Geocoding Quality** - Reports failed geocoding (warns if >5%)
6. ⚠ **Coordinate Bounds** - Checks if locations are within Germany
7. ⚠ **Coverage Feasibility** - Warns if service level is tight/impossible
8. ⚠ **Customer Distribution** - Validates total customer counts
9. ⚠ **Duplicate PLZ** - Sums duplicate postal codes with warning

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
- **Force regeneration**: Choose when to fully refresh. Delete `customers.csv` or set switch in  `customer_generator.py`

## 📝 Logging

All operations are logged to `optimization_process.log` with format:
```
2025-01-16 15:30:45 - [module_name] - INFO - Message
```

Each module clearly identifies itself for easy debugging.

## 🎨 Interactive map

- **Interactive Layers (toggle on off)**
   - Customer Distribution (PLZ choropleth)
   - Optimized Locations (markers + circles)
   - Federal State Borders for orientation
- **Legends** giving context and showing main KPIs
- **Tooltips** showing plz codes and details

<img src="resources/visualization.png" width="500" alt="Heatmap">


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

**"Missing required input files**
→ Ensure `sources/` folder contains all GeoJSON/TopoJSON files

**"Geocoding failure rate is high"**
→ Check if PLZ codes in source data are valid German postal codes

**"Service level is impossible"**
→ Increase `max_distance_km` or reduce `service_level` in config

**"Optimization status: Infeasible"**
→ Constraints are too restrictive; adjust constraint set parameters

## 📚 Module Reference

### `customer_generator.py`
- `load_or_generate_customers()` - Smart customer data handling
- `generate_customer_data()` - Synthetic data generation

### `data_loader.py`
- `load_and_clean_cities()` - Process city data
- `add_coordinates()` - Geocode locations

### `optimizer.py`
- `calculate_coverage()` - Distance matrix computation
- `run_optimization()` - PuLP solver execution
- `export_results()` - CSV output

### `visualizer.py`
- `create_comprehensive_map()` - Unified map generation
- Internal layer functions for choropleth, markers, legends


### `validator.py`
- `check_input_files()` - Verify file existence
- `check_constraint_logic()` - Validate parameters
- `check_coverage_feasibility()` - Pre-optimization checks
- `check_optimization_result()` - Post-optimization validation

## 🏆 Engineering Best Practices

I didn't just write code; I wanted to create a reliable, well-tested and document solution which can easily be extended in the future. **Yes, I admit. I like data quality and predictable outcomes.** This project demonstrated how to apply software engineering principles — like modularity, defensive validation, and centralized configuration—transforms and user-friendliness. I went from prototyping in notebooks to py-files, modules, config files. And I implemented continuous logging, testing and validating ensuring that every result is verifiable, and every run is stable. 

<img src="collaterals/best_practices.png" width="600" alt="System Overview"> |

### The Three Patterns

1.  **Defensive Validation Strategy**
    *   *Why*: We don't hope for good data; govern good data and inform when bad data could corrupt decisions.
    *   *Result*: By implementing a dedicated `validator.py` with 8 distinct checkpoints (checking everything from file existence to mathematical feasibility), the system acts as its own quality assurance team. This drastically reduces runtime errors and ensures that if an optimization runs, the result is mathematically sound.

2.  **Modular Architecture**
    *   *Why Use*: Monolithic scripts are hard to debug, impossible to test, and scary to change.
    *   *Result*: We split logic into dedicated modules (`data_loader`, `optimizer`, `visualizer`). This separation of concerns allows for rapid iteration—we can upgrade the visualization engine or swap the solver without risking the integrity of the rest of the system.

3.  **Centralized Configuration**
    *   *Why Use*: Hard-coding values buries business logic deep in the code where it's hard to find and change.
    *   *Result*: Every tunable parameter—from service levels to cost bonuses—lives in `config.py`. This empowers users to run "what-if" scenarios instantly, changing business rules without needing to understand or touch the Python code.

### Codebase Excellence Matrix

| Best Practice | The "Why" & The Return |
| :--- | :--- |
| **Modular Design** | **Maintainability**: Breaks complex logic into manageable, single-purpose files. |
| **Defensive Validation** | **Reliability**: Catches data issues (like missing files or bad coords) *before* they crash the solver. |
| **Centralized Config** | **Agility**: Enables rapid scenario testing by decoupling parameters from code logic. |
| **Unified Logging** | **Observability**: Detailed logs (`optimization_process.log`) make debugging and auditing effortless. |
| **Smart Caching** | **Performance**: Reuses heavy data processes (like customer generation), saving time on repeat runs. |
| **Type Hinting** | **Clarity**: Makes code self-documenting and helps IDEs prevent type-related bugs. |
| **Synthetic Data Gen** | **Testability**: Ensures the system works out-of-the-box, even without proprietary input data. |
| **Interactive Viz** | **Usability**: Delivers results in rich, interactive HTML maps rather than static images. |
| **Clean Directory Structure** | **Onboarding**: Intuitive organization (`sources/`, `results/`) means zero ramp-up time for new users. |
| **Feasibility Checks** | **Intelligence**: The system calculates if a goal is mathematically impossible *before* wasting compute time. |

## 📄 License

This is a private project. All rights reserved.

## 🤝 Contributing

For improvements or bug reports, contact the project maintainer.

---

**Version**: 2.0  
**Last Updated**: January 2025  
**Python**: 3.8+
