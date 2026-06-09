# Echo Survey Analysis - Momentum

An automated Python tool to parse, validate, and visually map liquid volumes and statuses from Echo acoustic liquid handler survey and print files (XML).

## Features

- **Automated Directory Monitoring**: The unified orchestrator (`main.py`) monitors a specific output folder (e.g., `\\Access-1615\c\Output\Echo`) and automatically analyzes new files the moment the machine finishes writing them.
- **Dual File Support**: 
  - **SurveyResult**: Analyzes well volumes against dispensing requirements, taking into account plate dead volume.
  - **PrintResult**: Detects skipped or failed liquid transfers and highlights problem wells.
- **Visual Plate Layouts**: Uses `matplotlib` to render a 384-well graphical plate pop-up.
  - **Survey Colors**: >20 uL (Green), 13 uL to 20 uL (Yellow), <13 uL (Red/Warning).
  - **Print Colors**: Successful transfers (Green), Skipped wells (Red with a big 'X').
- **CSV Validation**: For Survey files, it validates the surveyed volumes against a required dispense amount detailed in a CSV file, raising loud warnings if there is insufficient volume.
- **Consolidated Logging**: Writes all operational logs and alerts directly to `echo_analysis.log`, giving you one clean chronological timeline of machine activity.
- **Automated Builds**: Includes a GitHub Actions workflow to automatically package the script into a standalone Windows `.exe` (`EchoAnalysis.exe`) using PyInstaller upon every push to the `main` branch.

## Requirements

To run from the source code, ensure you have Python installed, then install the requirements:

```bash
pip install -r requirements.txt
```

*(Dependencies include: `matplotlib`, `numpy`, `watchdog`, and `pyinstaller`)*

## Usage

### 1. Monitor a folder (Recommended)
This will monitor the default network folder (or a local folder if passed) and check incoming XML files. You can pass the `--csv` argument to preload volume requirements for Survey analysis:

```bash
python main.py --csv sample/Dispense_Samples.csv
```
*(If the network drive is unavailable, it gracefully falls back to your local `sample/` directory)*

### 2. Analyze a single XML file directly
You can manually run an analysis on a single file without using the folder monitoring:

```bash
python main.py --csv sample/Dispense_Samples.csv sample/Plate_Source_SurveyResult29.xml
```
*(You can pass either a SurveyResult or a PrintResult file, and the script will automatically identify it and route it correctly).*

## How It Works

1. `main.py` watches the folder using the `watchdog` library.
2. Once an `.xml` file containing `SurveyResult` or `PrintResult` in its name is detected, it pauses briefly to ensure the file is completely saved.
3. It routes the file to the corresponding module (`survey_analysis.py` or `print_analysis.py`).
4. **For Survey Files**: It compares the Echo's surveyed volume against the required volume listed in the CSV, subtracting the correct dead volume based on the plate type.
5. **For Print Files**: It parses the `<skippedwells>` tags and maps them to the visual layout.
6. It logs a report to `echo_analysis.log` and opens a graphical window flagging any insufficient or skipped wells.
7. The background monitor stops once a file is visualized.
