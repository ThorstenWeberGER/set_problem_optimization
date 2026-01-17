"""
Main Orchestrator Script
Coordinates the complete location optimization workflow.

Usage:
    python main.py
    
Process:
    1. Validate input files
    2. Load and clean city data
    3. Load or generate customer data
    4. Select constraint sets to run
    5. Run optimization for each selected constraint set
    6. Create comprehensive visualization maps
    7. Export results
"""

import logging
import sys
import os
import webbrowser

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from modules import validator, data_loader, customer_generator, optimizer, visualizer


def setup_logging():
    """Configure logging for the entire application."""
    logging.basicConfig(
        level=logging.INFO,
        format=config.LOGGING['format'],
        datefmt=config.LOGGING['datefmt'],
        handlers=[
            logging.FileHandler(config.PATHS['log_file'], mode='a', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def print_banner():
    """Display application banner."""
    banner = """
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║          LOCATION OPTIMIZATION SYSTEM v2.0                 ║
    ║          Optimizing Customer Service Locations             ║
    ║          (C) Thorsten Weber, 2026                          ║
    ╚════════════════════════════════════════════════════════════╝
    """
    print(banner)


def select_constraint_sets():
    """
    Interactive selection of constraint sets to run.
    Returns list of selected constraint sets.
    """
    print("\n" + "="*60)
    print("AVAILABLE CONSTRAINT SETS:")
    print("="*60)
    
    for i, cs in enumerate(config.CONSTRAINT_SETS, 1):
        print(f"{i}. {cs['name']}")
        print(f"   Max Distance: {cs['max_distance_km']}km | Decay Start: {cs['decay_start_km']}km")
        print(f"   Top City Cost: {cs['cost_top_city']} | Standard Cost: {cs['cost_standard']}")
        print()
    
    while True:
        user_input = input("Enter constraint set numbers to run (comma-separated, or 'all'): ").strip().lower()
        
        if user_input == 'all':
            return config.CONSTRAINT_SETS
        
        try:
            # Parse user input
            selections = [int(x.strip()) for x in user_input.split(',')]
            
            # Validate selections
            if all(1 <= s <= len(config.CONSTRAINT_SETS) for s in selections):
                selected = [config.CONSTRAINT_SETS[s-1] for s in selections]
                print(f"\n✓ Selected {len(selected)} constraint set(s): {[cs['name'] for cs in selected]}\n")
                return selected
            else:
                print(f"Error: Please enter numbers between 1 and {len(config.CONSTRAINT_SETS)}")
        
        except (ValueError, IndexError):
            print("Error: Invalid input. Please enter numbers separated by commas or 'all'")


def main():
    """Main execution function."""
    logger = logging.getLogger(__name__)
    
    # Setup
    setup_logging()
    print_banner()
    
    logger.info("="*60)
    logger.info("LOCATION OPTIMIZATION PROCESS STARTED")
    logger.info("="*60)
    
    try:
        # ============================================================
        # STAGE 1: PRE-FLIGHT VALIDATION
        # ============================================================
        logger.info("\n[STAGE 1/6] PRE-FLIGHT VALIDATION")
        validator.check_input_files()
        
        # ============================================================
        # STAGE 2: DATA LOADING & PREPARATION
        # ============================================================
        logger.info("\n[STAGE 2/6] DATA LOADING & PREPARATION")
        
        # Load and clean city data
        df_cities = data_loader.load_and_clean_cities()
        df_cities = data_loader.add_coordinates(df_cities, 'plz')
        
        # Load or generate customer data
        df_customers = customer_generator.load_or_generate_customers(df_cities, force_regenerate=True) # generate new data if True
        df_customers = data_loader.add_coordinates(df_customers, 'plz5')
        df_customers.to_csv(config.PATHS['customers'], index=False, encoding='utf-8')
        # ============================================================
        # STAGE 3: CONSTRAINT SET SELECTION
        # ============================================================
        logger.info("\n[STAGE 3/6] CONSTRAINT SET SELECTION")
        selected_constraint_sets = select_constraint_sets()
        
        # ============================================================
        # STAGE 4: OPTIMIZATION LOOP
        # ============================================================
        logger.info("\n[STAGE 4/6] RUNNING OPTIMIZATIONS")
        logger.info(f"Processing {len(selected_constraint_sets)} constraint set(s)...\n")
        
        results = []
        
        for iteration, constraint_set in enumerate(selected_constraint_sets, 1):
            logger.info("="*60)
            logger.info(f"ITERATION {iteration}/{len(selected_constraint_sets)}: {constraint_set['name']}")
            logger.info("="*60)
            
            # Validate constraint logic
            validator.check_constraint_logic(constraint_set)
            
            # Calculate coverage
            coverage, location_stats = optimizer.calculate_coverage(
                df_customers, df_cities, constraint_set
            )
            
            # Run optimization
            problem, is_opened, is_served = optimizer.run_optimization(
                df_customers, df_cities, coverage, location_stats, constraint_set
            )
            
            # Eliminate duplicate counts (assign customers to closest opened location)
            location_stats = optimizer.resolve_customer_overlap(
                df_customers, df_cities, coverage, location_stats, is_opened, is_served
            )
            
            # Store results
            results.append({
                'constraint_set': constraint_set,
                'problem': problem,
                'is_opened': is_opened,
                'is_served': is_served,
                'location_stats': location_stats,
                'coverage': coverage
            })
            
            logger.info(f"Iteration {iteration} completed successfully.\n")
        
        # ============================================================
        # STAGE 5: RESULTS EXPORT
        # ============================================================
        logger.info("\n[STAGE 5/6] EXPORTING RESULTS")
        
        for result in results:
            optimizer.export_results(
                df_cities,
                result['is_opened'],
                result['location_stats'],
                result['constraint_set']['name'],
                result['coverage'],
                result['is_served']
            )
        
        # ============================================================
        # STAGE 6: VISUALIZATION
        # ============================================================
        logger.info("\n[STAGE 6/6] CREATING VISUALIZATIONS")
        
        map_paths = []
        for result in results:
            map_obj = visualizer.create_comprehensive_map(
                df_cities,
                df_customers,
                result['is_opened'],
                result['is_served'],
                result['location_stats'],
                result['constraint_set']
            )
            
            map_path = config.PATHS['map_output'].format(result['constraint_set']['name'])
            map_paths.append(map_path)
        
        # ============================================================
        # COMPLETION
        # ============================================================
        logger.info("\n" + "="*60)
        logger.info("✓ ALL OPTIMIZATIONS COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        
        print("\n" + "="*60)
        print("PROCESS COMPLETED SUCCESSFULLY")
        print("="*60)
        print(f"\nProcessed {len(results)} constraint set(s)")
        print(f"\nResults saved to: {config.RESULTS_DIR}")
        print("\nGenerated files:")
        for result in results:
            print(f"  • optimized_locations_{result['constraint_set']['name']}.csv")
            print(f"  • optimization_map_{result['constraint_set']['name']}.html")
        
        # Open first map in browser
        if map_paths:
            print(f"\nOpening map in browser: {os.path.basename(map_paths[0])}")
            webbrowser.open('file://' + os.path.realpath(map_paths[0]))
        
        print("\n" + "="*60 + "\n")
        
    except validator.ValidationError as e:
        logger.error(f"\n✗ VALIDATION ERROR: {e}")
        print(f"\n✗ Process failed due to validation error. Check log for details.")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"\n✗ UNEXPECTED ERROR: {e}", exc_info=True)
        print(f"\n✗ Process failed with unexpected error. Check log for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
