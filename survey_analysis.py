import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import sys
import os
import time
import queue
import argparse
import csv
from collections import defaultdict

def parse_dispense_csv(csv_filepath):
    """
    Parses the dispense CSV file and returns a dictionary with the required
    volume (in nL) for each well of each source plate.
    Format: dict[barcode][well] = total_volume_nl
    """
    required_volumes = defaultdict(lambda: defaultdict(float))
    with open(csv_filepath, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            barcode = row['Source Plate Barcode']
            well = row['Source Well']
            vol = float(row['Volume'])
            required_volumes[barcode][well] += vol
    return required_volumes

def plot_plate(xml_file, required_volumes=None):
    if not os.path.exists(xml_file):
        print(f"Error: File '{xml_file}' not found.")
        return

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML: {e}")
        return

    # Extract dimensions from the root element
    rows = int(root.attrib.get('rows', 16))
    cols = int(root.attrib.get('cols', 24))
    
    # Try to extract barcode from filename as requested: <BC>_SurveyResult.xml
    filename = os.path.basename(xml_file)
    barcode = filename.split('_SurveyResult')[0]
    
    # Fallback to XML attribute if filename doesn't match the expected pattern
    if not barcode or barcode == filename:
        barcode = root.attrib.get('barcode', '')

    plate_name = root.attrib.get('name', '')
    dead_volume_uL = 0.0
    if "PP" in plate_name:
        dead_volume_uL = 13.0
    elif "LDV" in plate_name:
        dead_volume_uL = 4.0

    plate_requirements = {}
    if required_volumes and barcode in required_volumes:
        plate_requirements = required_volumes[barcode]
        print(plate_requirements)

    # Values for color mapping:
    # 0 = empty/default (gray)
    # 1 = < 13 uL (red)
    # 2 = >= 13 uL and <= 20 uL (yellow)
    # 3 = > 20 uL (green)
    color_map_data = np.zeros((rows, cols))
    text_data = [["" for _ in range(cols)] for _ in range(rows)]
    insufficient_wells = []

    for w in root.findall('.//w'):
        try:
            r = int(w.attrib['r'])
            c = int(w.attrib['c'])
            well_name = w.attrib.get('n', '')
            
            cvl_str = w.attrib.get('cvl', '0')
            cvl = float(cvl_str)
            cvl_rounded = round(cvl)
            
            text_data[r][c] = f"{cvl_rounded}uL"
            
            if cvl > 20:
                color_map_data[r, c] = 3
            elif cvl < 13:
                color_map_data[r, c] = 1
            else:
                color_map_data[r, c] = 2
                
            # Check against required volumes if applicable
            if well_name in plate_requirements:
                req_nL = plate_requirements[well_name]
                avail_nL = (cvl - dead_volume_uL) * 1000
                if avail_nL < req_nL:
                    insufficient_wells.append((well_name, req_nL, avail_nL, cvl, dead_volume_uL))
                    # Optionally override the color to red to flag insufficient volume
                    color_map_data[r, c] = 1
                    text_data[r][c] += "\n(Low!)"
                    
        except (KeyError, ValueError):
            continue

    skipped_wells_elem = root.find('.//skippedwells')
    skipped_count = 0
    if skipped_wells_elem is not None:
        skipped_count = int(skipped_wells_elem.attrib.get('total', '0'))

    if plate_requirements:
        print(f"\n--- Volume Check Report for Plate: {barcode} ---")
        if insufficient_wells or skipped_count > 0:
            if insufficient_wells:
                print(f"WARNING: Found {len(insufficient_wells)} wells with insufficient volume!")
                for w_name, req, avail, total_uL, dead_uL in insufficient_wells:
                    print(f"  - Well {w_name}: Required {req} nL, but only has {max(0, avail):.2f} nL available "
                          f"(Total: {total_uL} uL, Dead Volume: {dead_uL} uL).")
            if skipped_count > 0:
                print(f"WARNING: Found {skipped_count} skipped wells!")
        else:
            print("SUCCESS: All required wells have sufficient volume and no wells were skipped.")
        print("--------------------------------------------------\n")

    # Set up the matplotlib figure
    fig, ax = plt.subplots(figsize=(max(10, cols * 0.45), max(6, rows * 0.45)))
    
    # Define custom colors
    cmap = mcolors.ListedColormap(['#e0e0e0', '#ff6666', '#ffff66', '#66cc66'])
    bounds = [-0.5, 0.5, 1.5, 2.5, 3.5]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # Plot the grid colors
    ax.imshow(color_map_data, cmap=cmap, norm=norm, origin='upper', aspect='equal')

    # Add the text to each well
    for r in range(rows):
        for c in range(cols):
            val = text_data[r][c]
            if val:
                ax.text(c, r, val, ha='center', va='center', color='black', 
                        fontsize=9)

    # Configure axes to look like a plate
    ax.set_xticks(np.arange(cols))
    ax.set_yticks(np.arange(rows))
    
    # Column numbers (1 to N)
    ax.set_xticklabels([str(i+1) for i in range(cols)])
    
    # Row letters (A to ...)
    ax.set_yticklabels([chr(65+i) for i in range(rows)])

    # Create borders between cells
    ax.set_xticks(np.arange(-0.5, cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, rows, 1), minor=True)
    ax.grid(which='minor', color='black', linestyle='-', linewidth=1)
    ax.tick_params(which='minor', bottom=False, left=False)

    if insufficient_wells or skipped_count > 0:
        warning_parts = []
        if insufficient_wells:
            warning_parts.append(f"{len(insufficient_wells)} insufficient")
        if skipped_count > 0:
            warning_parts.append(f"{skipped_count} skipped")
            
        plt.title(f"Plate Layout: {filename}\nWARNING: {', '.join(warning_parts)}!", color='red', fontweight='bold')
        
        warning_text = ""
        if insufficient_wells:
            warning_text += f"Low Volume Wells:\n"
            for w_name, req, avail, total_uL, dead_uL in insufficient_wells[:12]:
                warning_text += f"{w_name}: Req {req}nL, Avail {max(0, avail):.0f}nL\n"
            if len(insufficient_wells) > 12:
                warning_text += f"...and {len(insufficient_wells) - 12} more.\n"
        if skipped_count > 0:
            warning_text += f"\nSkipped Wells: {skipped_count}"
            
        plt.figtext(0.82, 0.5, warning_text.strip(), ha="left", va="center", fontsize=8, color="red",
                    bbox=dict(facecolor='white', alpha=0.9, edgecolor='red', boxstyle='round,pad=0.5'))
        plt.tight_layout(rect=[0, 0, 0.8, 1])
    else:
        plt.title(f"Plate Layout: {filename}")
        plt.tight_layout()
    
    # This will display the window popup
    plt.show()
    
    return len(insufficient_wells) > 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Echo Survey Analysis Monitor")
    parser.add_argument("--csv", help="Path to Dispense_Samples.csv to validate required volumes", default=None)
    parser.add_argument("path", nargs="?", default=r"/Users/fbarbos/AntigravityProjects/echo_survey/sample", 
                        help="Directory to monitor or specific XML file to analyze")
    
    args = parser.parse_args()
    
    req_vols = None
    if args.csv:
        if os.path.exists(args.csv):
            print(f"Loading volume requirements from {args.csv}...")
            try:
                req_vols = parse_dispense_csv(args.csv)
                print(f"Successfully loaded requirements for {len(req_vols)} plates.")
            except Exception as e:
                print(f"Error reading CSV file: {e}")
                sys.exit(1)
        else:
            print(f"Error: CSV file '{args.csv}' not found.")
            sys.exit(1)

    target_path = args.path
    if os.path.isfile(target_path):
        # Just analyze the single file
        has_errors = plot_plate(target_path, req_vols)
        if has_errors:
            print("Exiting with code 1")
            sys.exit(1)
        else:
            print("Exiting with code 0")
            sys.exit(0)
    else:
        print(f"Error: Path '{target_path}' does not exist or is not a file.")
        sys.exit(1)
