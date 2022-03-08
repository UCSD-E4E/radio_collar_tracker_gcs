# RCT GCS
This is the redevelopment of the Radio Telemetry Tracker Ground Control Station
from v1.0.  Working branch v1.0a, becomes v2.0 on release

## Installation on Ubuntu (18.04+) and Windows 10+
1.  [Install Anaconda 2020.02](https://www.anaconda.com/products/individual)
2.  Navigate to the `radio_collar_tracker_gcs` project in a python capable terminal
3.  Run `conda env create -f environment.yml`
4.  Run `conda activate rctGCS`

## Running `rctGCS`
-   Windows:
    1.  Run `rctGCS.bat` by double clicking or running from command line
-   Ubuntu/MacOS:
    1.  From the command line, run `conda activate rctGCS`
    2.  Navigate to the `scripts` folder.
    3.  Run `python rctGCS.py`
    
## Running the simulator for GCS
1. Navigate to the `scripts` folder and run `rctGCS` with the following commands:
    - `$ conda activate rctGCS`
    - `python rctGCS.py`
    This should open up the rctGCS UI
2. Create a new terminal instance and naviagate to the `scripts` folder and run the following commands:
    - `$ conda activate rctGCS`
    - `$ ipython -i droneSimulator.py -- --protocol tcp`
    - `ipython>>> sim.start()`
3. From the rctGCS UI, navigate to the "System: No Connection" tab --> "Connect" --> "Done"
4. Switch back to the `ipython` terminal window
    - `ipython>>> sim.doMission()`

# For Developers
## Prerequisites:
- [VSCode](https://code.visualstudio.com/download)
- [Python 3.6](https://www.python.org/downloads/)
- [Anaconda 2020.02 or later](https://www.anaconda.com/products/individual)

### Configuration
1.  Download this repository and check out the appropriate branch
2.  Navigate to the `radio_collar_tracker_gcs` project in a python capable terminal
3.  Run `conda env create -f environment.yml`
4.  Open VSCode. Naviagate to the `Extensions` tab and download `Python Extension Pack`.
5.  Restart VSCode. Open the `radio_collar_tracker_gcs` project
6.  Open the command palette (`Ctrl`+`Shift`+`P`)
7.  Select `Python: Select Interpreter`/`Python 3.6.13 ('rctGCS')`
