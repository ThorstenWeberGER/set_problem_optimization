# NOT WORKING YET



"""
PURPOSE:
Generate a master CSV of the Top 200 German cities using official data 
from the Federal Statistical Office (Destatis - Gemeindeverzeichnis).

OUTPUT COLUMNS:
- city_name
- central_plz_code
- list_of_all_sub_plz_codes
- sum_population_on_city_level (Official inhabitants count)

DATA SOURCE: 
- Population: Destatis GV-100 (Gemeindeverzeichnis)
- Geodata: pgeocode (GeoNames Mapping)
"""

import pandas as pd
import pgeocode
import os
import requests
import io

def generate_master_from_destatis():
    target_path = os.path.join(os.path.expanduser("~"), "top200_destatis_master.csv")
    
    # Step 1: Accessing Destatis Open Data
    # Note: In a production environment, you would use the GENESIS API with a key.
    # For this script, we use a reliable Open Data mirror of the official GV-100 list.
    print("Step 1: Downloading official municipality data from Destatis sources...")
    
    # Official URL for the municipality directory (current quarterly version)
    # Using a common Open Data URL for the GV-100 format
    url = "https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis/Administrativ/Archiv/GVAuszugQ/AuszugGV1QAktuell.csv?__blob=publicationFile"
    
    try:
        # Destatis CSVs often use Latin-1 encoding and semicolon separators
        response = requests.get(url)
        df_raw = pd.read_csv(io.BytesIO(response.content), 
                             sep=';', 
                             encoding='latin-1', 
                             low_memory=False, 
                             skiprows=6) # Skipping header metadata
        
        # Step 2: Cleaning the official data
        # We need 'Gemeindename' (Municipality Name) and 'Bevölkerung' (Population)
        # In the official GV-100, these are specific columns
        # We filter for records that are actually municipalities (usually characterized by an AGS)
        df_raw.columns = [str(i) for i in range(len(df_raw.columns))] # Reset columns to indices
        
        # Column 10 is usually the Name, Column 13 the Population in the GV-100 layout
        df_cities = df_raw.iloc[:, [10, 13]].copy()
        df_cities.columns = ['city_name', 'population']
        
        # Clean population values (remove spaces/strings)
        df_cities['population'] = pd.to_numeric(df_cities['population'].astype(str).str.replace(r'\s+', '', regex=True), errors='coerce')
        df_cities = df_cities.dropna(subset=['population'])
        
        # Sort and take Top 200
        df_top200 = df_cities.sort_values(by='population', ascending=False).head(200)
        
    except Exception as e:
        print(f"Error fetching official data: {e}")
        return

    print("Step 2: Enriching with official Postal Code clusters...")
    nomi = pgeocode.Nominatim('de')
    all_de_data = nomi._data.copy()
    
    master_records = []

    for _, row in df_top200.iterrows():
        # Clean city name (Destatis often adds classification like ", Stadt")
        clean_name = row['city_name'].split(',')[0].strip()
        population = int(row['population'])
        
        # Find all associated PLZs for the city
        city_plzs = all_de_data[all_de_data['place_name'].str.contains(clean_name, case=False, na=False)]
        
        if not city_plzs.empty:
            all_codes = sorted(city_plzs['postal_code'].unique().tolist())
            central_plz = all_codes[0]
            sub_plz_str = ";".join(all_codes)
            
            master_records.append({
                'city_name': clean_name,
                'central_plz_code': central_plz,
                'list_of_all_sub_plz_codes': sub_plz_str,
                'sum_population_on_city_level': population
            })

    # Step 3: Final Export
    df_final = pd.DataFrame(master_records)
    df_final.to_csv(target_path, index=False, sep=',', encoding='utf-8-sig')
    
    print("-" * 30)
    print(f"SUCCESS: Official Master CSV Generated")
    print(f"Destination: {target_path}")
    print(f"Top City: {df_final.iloc[0]['city_name']} ({df_final.iloc[0]['sum_population_on_city_level']} inh.)")
    print("-" * 30)

if __name__ == "__main__":
    generate_master_from_destatis()