import sys
import os
import time
import queue
import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import the logic from our refactored modules
from survey_analysis import plot_plate, parse_dispense_csv
from print_analysis import parse_printresult_xml, plot_print_plate

class Logger(object):
    def __init__(self, filename="echo_analysis.log"):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")
        
    def write(self, message):
        if self.terminal:
            self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        if self.terminal:
            self.terminal.flush()
        self.log.flush()

# Route all prints and errors to the unified log file
sys.stdout = Logger()
sys.stderr = sys.stdout

class UnifiedFileHandler(FileSystemEventHandler):
    def __init__(self, file_queue):
        self.file_queue = file_queue
        self.processed_files = set()
        super().__init__()

    def on_any_event(self, event):
        if event.is_directory:
            return
        
        if event.event_type in ['created', 'modified']:
            filepath = event.src_path
            filename = os.path.basename(filepath)
            
            if filename.endswith('.xml'):
                if "SurveyResult" in filename:
                    file_type = "survey"
                elif "PrintResult" in filename:
                    file_type = "print"
                else:
                    return # Ignore other XML files
                    
                if filepath not in self.processed_files:
                    self.processed_files.add(filepath)
                    print(f"\nNew {file_type} file detected: {filename}")
                    self.file_queue.put((file_type, filepath))

def monitor_directory(path, required_volumes=None):
    print(f"Monitoring directory for new SurveyResult and PrintResult XML files: {path}")
    
    file_queue = queue.Queue()
    event_handler = UnifiedFileHandler(file_queue)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    
    try:
        while True:
            try:
                file_type, filepath = file_queue.get(timeout=1)
                
                # Give it a short delay to ensure the file is completely written before parsing
                time.sleep(1)
                
                print(f"Analyzing {file_type} file: {filepath}...")
                
                if file_type == "survey":
                    has_errors = plot_plate(filepath, required_volumes)
                    return has_errors
                elif file_type == "print":
                    total_skipped, skipped_wells, barcode = parse_printresult_xml(filepath)
                    if total_skipped is not None:
                        has_errors = plot_print_plate(filepath, total_skipped, skipped_wells)
                        return has_errors
                    else:
                        return True

                
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        print("\nStopping monitoring...")
    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Echo Monitor for Survey and Print Results.")
    parser.add_argument("target", nargs='?', default=r"\\Access-1615\c\Output\Echo",
                        help="Path to the directory to monitor.")
    parser.add_argument("--csv", help="Path to Dispense_Samples.csv to validate survey volumes", default=None)
    args = parser.parse_args()

    target_path = args.target
    req_vols = None

    # Parse survey volumes if provided
    if args.csv:
        if os.path.exists(args.csv):
            print(f"Loading volume requirements from {args.csv}...")
            req_vols = parse_dispense_csv(args.csv)
            if req_vols:
                print(f"Successfully loaded requirements for {len(req_vols)} plates.")
        else:
            print(f"Error: CSV file '{args.csv}' not found.")
            sys.exit(1)

    # Resolve target directory
    if target_path == r"\\Access-1615\c\Output\Echo" and not os.path.exists(target_path):
        local_sample = "/Users/fbarbos/AntigravityProjects/echo_survey/sample"
        if os.path.exists(local_sample):
            print(f"Default network directory '{target_path}' not found. Falling back to local '{local_sample}' directory.")
            target_path = local_sample
        else:
            print(f"Error: Default network directory '{target_path}' not found.")
            print("Please ensure the network path is accessible, or provide a valid local file/directory as an argument.")
            sys.exit(1)
            
    if os.path.isdir(target_path):
        has_errors = monitor_directory(target_path, required_volumes=req_vols)
        sys.exit(1 if has_errors else 0)
    elif os.path.isfile(target_path):
        has_errors = False
        # Determine type and process immediately
        if "SurveyResult" in target_path:
            has_errors = plot_plate(target_path, req_vols)
        elif "PrintResult" in target_path:
            total_skipped, skipped_wells, barcode = parse_printresult_xml(target_path)
            if total_skipped is not None:
                has_errors = plot_print_plate(target_path, total_skipped, skipped_wells)
            else:
                has_errors = True
        else:
            print(f"Error: File '{target_path}' is neither a recognized SurveyResult nor PrintResult XML file.")
            sys.exit(1)
        sys.exit(1 if has_errors else 0)
    else:
        print(f"Error: Path '{target_path}' does not exist.")
        sys.exit(1)
