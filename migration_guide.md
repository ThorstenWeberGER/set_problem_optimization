# Migration Guide: From Old Scripts to Modular System

## 📋 Pre-Migration Checklist

Before starting, ensure you have:
- [ ] All original scripts backed up
- [ ] Active Python environment with dependencies installed
- [ ] Source data files in `sources/` folder
- [ ] Write permissions to create new folders

## 🔄 Step-by-Step Migration

### Step 1: Create New Folder Structure

```bash
# In your project root, create:
mkdir modules
mkdir results
mkdir _archive
```

### Step 2: Move Old Scripts to Archive

```bash
# Move original scripts (don't delete yet!)
mv optimize_locations.py _archive/
mv draw_map.py _archive/
mv generate_customers.py _archive/
mv read_and_clean_city_data.py _archive/
```

### Step 3: Create New Files

Create the following files in your project root:

1. **config.py** - Copy from artifact `config_module`
2. **main.py** - Copy from artifact `main_script`

### Step 4: Create Module Files

In the `modules/` folder, create:

1. **\_\_init\_\_.py** - Copy from artifact `modules_init`
2. **validator.py** - Copy from artifact `validator_module`
3. **data_loader.py** - Copy from artifact `data_loader_module`
4. **customer_generator.py** - Copy from artifact `customer_generator_module`
5. **optimizer.py** - Copy from artifact `optimizer_module`
6. **visualizer.py** - Copy from artifact `visualizer_module`

### Step 5: Verify File Structure

Your project should now look like:

```
project_root/
├── main.py                    ✓ NEW
├── config.py                  ✓ NEW
├── modules/                   ✓ NEW
│   ├── __init__.py
│   ├── validator.py
│   ├── data_loader.py
│   ├── customer_generator.py
│   ├── optimizer.py
│   └── visualizer.py
├── sources/                   ✓ EXISTING
│   ├── german_cities.xlsx
│   ├── ger_plz-5stellig.topojson
│   └── states_ger_geo.json
├── results/                   ✓ EXISTING (or new)
├── _archive/                  ✓ NEW
│   ├── optimize_locations.py
│   ├── draw_map.py
│   ├── generate_customers.py
│   └── read_and_clean_city_data.py
└── optimization_process.log   ✓ EXISTING
```

## ⚙️ Configuration Transfer

### Old Configuration Locations → New Location

| Old Script | Old Config | New Location in config.py |
|-----------|-----------|---------------------------|
| optimize_locations.py | `BASE_CONFIG` | `OPTIMIZATION` + `PATHS` |
| generate_customers.py | `CONFIG` | `CUSTOMER_GENERATION` |
| draw_map.py | `BASE_CONFIG` | `PATHS` |
| All | `CONSTRAINT_SETS` | `CONSTRAINT_SETS` (same) |

### What Changed?

**Paths**: Now all centralized in `config.PATHS`
```python
# OLD (scattered):
BASE_CONFIG['map_path'] = os.path.join(...)
CONFIG['output_file'] = os.path.join(...)

# NEW (centralized):
config.PATHS['map_output']
config.PATHS['customers']
```

**Parameters**: Grouped by purpose
```python
# OLD (mixed):
'service_level': 0.90
'total_customers': 90000

# NEW (grouped):
config.OPTIMIZATION['service_level']
config.CUSTOMER_GENERATION['total_customers']
```

## 🧪 Testing Your Migration

### Test 1: Run Main Script
```bash
python main.py
```

**Expected**: Interactive prompt asking for constraint set selection

### Test 2: Check Validation
Delete a source file temporarily:
```bash
mv sources/german_cities.xlsx sources/german_cities.xlsx.bak
python main.py
```

**Expected**: Validation error message, process stops

Restore file:
```bash
mv sources/german_cities.xlsx.bak sources/german_cities.xlsx
```

### Test 3: Verify Outputs

After successful run, check:
- [ ] `results/customers.csv` created
- [ ] `results/optimized_locations_*.csv` created
- [ ] `results/optimization_map_*.html` created
- [ ] Map opens in browser automatically
- [ ] All layers visible in map (choropleth, markers, borders)

## 🔍 Comparing Old vs New

### Functionality Mapping

| Old Functionality | New Module | Function |
|------------------|-----------|----------|
| Load city data | `data_loader.py` | `load_and_clean_cities()` |
| Generate customers | `customer_generator.py` | `load_or_generate_customers()` |
| Geocoding | `data_loader.py` | `add_coordinates()` |
| Coverage calculation | `optimizer.py` | `calculate_coverage()` |
| PuLP optimization | `optimizer.py` | `run_optimization()` |
| CSV export | `optimizer.py` | `export_results()` |
| Simple map (old) | `visualizer.py` | Merged into `create_comprehensive_map()` |
| Choropleth map | `visualizer.py` | Merged into `create_comprehensive_map()` |

### Key Improvements

✅ **No more duplicate code** - Single visualization function  
✅ **Automatic customer loading** - Checks if file exists first  
✅ **Comprehensive validation** - 8 checks before/during/after optimization  
✅ **Better logging** - Module names in every log entry  
✅ **Interactive selection** - Choose which constraint sets to run  
✅ **Unified maps** - Both choropleth AND markers in one map  

## 🐛 Common Migration Issues

### Issue 1: Import Errors
```
ModuleNotFoundError: No module named 'modules'
```

**Fix**: Ensure `modules/__init__.py` exists and contains proper imports

### Issue 2: Config Not Found
```
NameError: name 'config' is not defined
```

**Fix**: Check `config.py` is in project root, not in `modules/`

### Issue 3: Path Errors
```
FileNotFoundError: [Errno 2] No such file or directory
```

**Fix**: Verify `sources/` folder with all GeoJSON/TopoJSON files

### Issue 4: Old Log Conflicts
```
PermissionError: [Errno 13] Permission denied: 'optimization_process.log'
```

**Fix**: Close any open log file viewers, or delete and regenerate

## 📊 Performance Comparison

| Metric | Old System | New System |
|--------|-----------|-----------|
| Lines of Code | ~800 (scattered) | ~1200 (organized) |
| File Count | 4 scripts | 1 main + 6 modules |
| Reusability | Low | High |
| Maintainability | Medium | High |
| Validation | Minimal | Comprehensive (8 checks) |
| Error Messages | Generic | Specific with suggestions |
| Customer Handling | Always regenerate | Smart load/generate |
| Maps | 2 separate | 1 unified |

## ✅ Post-Migration Checklist

After successful migration:

- [ ] Delete `_archive/` folder (optional, after verification)
- [ ] Update any external scripts that called old files
- [ ] Update documentation/wikis referencing old structure
- [ ] Train team members on new `main.py` workflow
- [ ] Set up version control if not already done

## 🎓 Learning the New System

### For Daily Use
1. Just run `python main.py`
2. Select constraint sets
3. Wait for results
4. Check `results/` folder

### For Customization
1. Edit `config.py` for parameters
2. Add new constraint sets in `config.CONSTRAINT_SETS`
3. Modify validation thresholds in `config.VALIDATION`

### For Development
1. Each module is self-contained
2. Import only what you need:
   ```python
   from modules import optimizer
   optimizer.run_optimization(...)
   ```
3. Add new features as new functions in appropriate modules

## 🔄 Rollback Plan

If you need to revert:

```bash
# Restore old scripts
cp _archive/*.py .

# Delete new structure
rm -rf modules/
rm main.py config.py

# Continue using old system
python optimize_locations.py
```

## 📞 Support

If issues persist:
1. Check `optimization_process.log` for detailed errors
2. Verify all dependencies are installed
3. Compare your folder structure with this guide
4. Ensure Python 3.8+

---

**Migration Complete!** 🎉

You now have a professional, modular optimization system with comprehensive validation and unified visualization.
