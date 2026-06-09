import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import os

def parse_printresult_xml(xml_file):
    """
    Parses the Echo PrintResult XML file.
    Returns:
        total_skipped (int): Number of skipped wells.
        skipped_wells (list): List of skipped well names (e.g. ['A1', 'B2']).
        plate_barcode (str): Barcode of the source plate.
    """
    if not os.path.exists(xml_file):
        print(f"Error: File '{xml_file}' not found.")
        return None, None, None

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        plate_info = root.find('.//plateInfo')
        barcode = "Unknown"
        if plate_info is not None:
            source_plate = plate_info.find(".//plate[@type='source']")
            if source_plate is not None:
                barcode = source_plate.attrib.get('barcode', 'Unknown')
                
        skipped_wells_node = root.find('.//skippedwells')
        total_skipped = 0
        skipped_wells = []
        
        if skipped_wells_node is not None:
            total_skipped = int(skipped_wells_node.attrib.get('total', '0'))
            # Try to extract the skipped well names if they are child elements
            for child in skipped_wells_node:
                well_name = child.attrib.get('n')
                if well_name:
                    skipped_wells.append(well_name)
                    
        return total_skipped, skipped_wells, barcode

    except Exception as e:
        print(f"Error parsing XML: {e}")
        return None, None, None

def plot_print_plate(filename, total_skipped, skipped_wells):
    """
    Creates a matplotlib visualization of the 384-well plate.
    Green = Successful
    Red = Skipped
    """
    rows = 16
    cols = 24

    # 0 = Default (Empty/Unknown)
    # 1 = Skipped (Red)
    # 2 = Success (Green)
    color_map_data = np.zeros((rows, cols))
    text_data = [["" for _ in range(cols)] for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            well_name = f"{chr(65+r)}{c+1}"
            if well_name in skipped_wells:
                color_map_data[r, c] = 1
                text_data[r][c] = "X"
            else:
                color_map_data[r, c] = 2

    print(f"\n--- Print Check Report for: {filename} ---")
    if total_skipped > 0:
        print(f"WARNING: Found {total_skipped} skipped wells!")
        if skipped_wells:
            for w in skipped_wells:
                print(f"  - Well {w} was skipped.")
        else:
            print("  - Detailed skipped well names were not found in the XML.")
            
        print("--------------------------------------------------\n")
        
        # Set up the matplotlib figure
        fig, ax = plt.subplots(figsize=(max(10, cols * 0.45), max(6, rows * 0.45)))
        
        cmap = mcolors.ListedColormap(['#e0e0e0', '#ff6666', '#66cc66'])
        bounds = [-0.5, 0.5, 1.5, 2.5]
        norm = mcolors.BoundaryNorm(bounds, cmap.N)
    
        ax.imshow(color_map_data, cmap=cmap, norm=norm, origin='upper', aspect='equal')
    
        for r in range(rows):
            for c in range(cols):
                val = text_data[r][c]
                if val:
                    ax.text(c, r, val, ha='center', va='center', color='black', 
                            fontsize=14, fontweight='bold')
    
        ax.set_xticks(np.arange(cols))
        ax.set_yticks(np.arange(rows))
        ax.set_xticklabels([str(i+1) for i in range(cols)])
        ax.set_yticklabels([chr(65+i) for i in range(rows)])
    
        ax.set_xticks(np.arange(-0.5, cols, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, rows, 1), minor=True)
        ax.grid(which='minor', color='black', linestyle='-', linewidth=1)
        ax.tick_params(which='minor', bottom=False, left=False)
    
        plt.title(f"Print Layout: {os.path.basename(filename)}\nWARNING: {total_skipped} wells were SKIPPED!", color='red', fontweight='bold')
        
        warning_text = f"Skipped Wells:\n"
        if skipped_wells:
            for w_name in skipped_wells[:12]:
                warning_text += f"{w_name}\n"
            if len(skipped_wells) > 12:
                warning_text += f"...and {len(skipped_wells) - 12} more."
        else:
            warning_text += f"Total: {total_skipped}\n(Details unavailable in XML)"
                
        plt.figtext(0.82, 0.5, warning_text, ha="left", va="center", fontsize=10, color="red",
                    bbox=dict(facecolor='white', alpha=0.9, edgecolor='red', boxstyle='round,pad=0.5'))
        plt.tight_layout(rect=[0, 0, 0.8, 1])
        plt.show()

    else:
        print("SUCCESS: All transfered wells were successful (0 skipped wells).")
        print("--------------------------------------------------\n")
