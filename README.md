# RCT GCS
This is the redevelopment of the Radio Telemetry Tracker Ground Control Station
from v1.0.  Working branch v1.0a, becomes v2.0 on release

## Installation on Ubuntu (18.04+) and Windows 10+
1.  [Install Miniconda](https://docs.conda.io/en/latest/miniconda.html)
2.  Download this repository
3.  Navigate to the `radio_collar_tracker_gcs` project in a python capable terminal
4.  Run `conda env create -f conda-{os}.lock`
5.  Run `conda activate rctGCS`
6.  Run `python -m pip install git+https://github.com/UCSD-E4E/radio_collar_tracker_comms.git@v0.0.0.9`

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
    - `ipython>>> sim.do_mission()`

# For Developers
## Prerequisites:
- [VSCode](https://code.visualstudio.com/download)
- [Python 3.6](https://www.python.org/downloads/)
- [Anaconda 2020.02 or later](https://www.anaconda.com/products/individual)

### Configuration
1.  Download this repository and check out the appropriate branch
2.  Download the [comms directory](https://github.com/UCSD-E4E/radio_collar_tracker_comms/tree/communications_HG) and checkout the appropriate branch
3.  Navigate to the `radio_collar_tracker_comms` project in a python capable terminal
4.  Run `python -m pip install .`
5.  Navigate to the `radio_collar_tracker_gcs` project in a python capable terminal
6.  Run `conda env create -f environment.yml`
7.  Open VSCode. Naviagate to the `Extensions` tab and download `Python Extension Pack`.
8.  Restart VSCode. Open the `radio_collar_tracker_gcs` project
9.  Open the command palette (`Ctrl`+`Shift`+`P`)
10.  Select `Python: Select Interpreter`/`Python 3.6.13 ('rctGCS')`
