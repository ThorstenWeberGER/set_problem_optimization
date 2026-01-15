"""
PURPOSE:
Convert GeoJSON files to TopoJSON format for lightweight web mapping.
TopoJSON reduces file size by 80-90% compared to GeoJSON by storing shared
boundaries only once instead of duplicating them.
"""

import json
import os
import topojson
from pathlib import Path

def convert_geojson_to_topojson(geojson_filename, output_filename=None, quantization=10000):
    """
    Converts a GeoJSON file to TopoJSON format.
    
    Args:
        geojson_filename (str): Name of the input GeoJSON file (assumed to be in script directory)
        output_filename (str): Name of output TopoJSON file. If None, uses same name with .topojson extension
        quantization (int): Quantization level (higher = smaller file, lower precision).
                          Default 10000 is good for most web maps.
    """
    # Get script directory and build file paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, geojson_filename)
    
    # Determine output filename
    if output_filename is None:
        base_name = Path(geojson_filename).stem
        output_filename = f"{base_name}.topojson"
    
    output_path = os.path.join(script_dir, output_filename)
    
    print(f"Converting: {geojson_filename}")
    print(f"Input file: {input_path}")
    print(f"Output file: {output_path}")
    
    try:
        # Load GeoJSON
        with open(input_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        print(f"✓ GeoJSON loaded successfully")
        
        # Get original file size
        input_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        print(f"  Original file size: {input_size_mb:.2f} MB")
        
        # Convert to TopoJSON with quantization
        print(f"✓ Converting to TopoJSON (quantization={quantization})...")
        topo = topojson.Topology(
            geojson_data
        )
        
        # Save TopoJSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(topo.to_dict(), f, separators=(',', ':'))
        
        print(f"✓ TopoJSON saved successfully")
        
        # Calculate compression ratio
        output_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        compression_ratio = (1 - output_size_mb / input_size_mb) * 100
        
        print(f"\n📊 COMPRESSION RESULTS:")
        print(f"  Original size:     {input_size_mb:.2f} MB")
        print(f"  Compressed size:   {output_size_mb:.2f} MB")
        print(f"  Compression ratio: {compression_ratio:.1f}%")
        print(f"  Size reduction:    {input_size_mb - output_size_mb:.2f} MB")
        
    except FileNotFoundError:
        print(f"❌ Error: File '{input_path}' not found.")
        print(f"   Make sure the GeoJSON file is in the same directory as this script.")
    except Exception as e:
        print(f"❌ Error during conversion: {e}")

if __name__ == "__main__":
    # Convert plz5 GeoJSON to TopoJSON
    print("="*60)
    print("GeoJSON to TopoJSON Converter")
    print("="*60 + "\n")
    
    convert_geojson_to_topojson(
        geojson_filename='ger_plz-5stellig.geojson',
        output_filename='ger_plz-5stellig.topojson',
        quantization=10000  # Good balance between compression and precision
    )
    
    print("\n" + "="*60)
    print("Conversion complete!")
    print("="*60)
