# RCT GCS
This is the redevelopment of the Radio Telemetry Tracker Ground Control Station
from v1.0.  Working branch v1.0a, becomes v2.0 on release

## Installation on Ubuntu (18.04+) and Windows 10+
1.  [Install Miniconda](https://docs.conda.io/en/latest/miniconda.html)
2.  Download this repository
3.  Navigate to the `radio_collar_tracker_gcs` project in a python capable terminal
4.  Run `conda create --name rctGCS --file conda-[os].lock`
5.  Run `conda activate rctGCS`
6.  Run `poetry install`

## Running `rctGCS`
1.  From the command line, run `conda activate rctGCS`
2.  Run `RCTGcs`
    
## Running the simulator for GCS
1. Run `rctGCS` with the following commands:
    - `conda activate rctGCS`
    - `RCTGcs`
    This should open up the rctGCS UI
2. Create a new terminal instance and run the following commands:
    - `conda activate rctGCS`
    - `droneSimulator --spec {spec}`
    - `ipython>>> sim.start()`

The transport spec is a string specification of the connection type:

| Type          | Resulting Object      | Syntax                            |
|---------------|-----------------------|-----------------------------------|
| Serial        | RCTSerialTransport    | serial:{device}?baud={baudrate}   |
| TCP Client    | RCTTCPClient          | tcpc://{hostname}:{port}          |

3. From the rctGCS UI, navigate to the "System: No Connection" tab --> "Connect" --> "Done"
4. Switch back to the `ipython` terminal window
    - `ipython>>> sim.do_mission()`

# For Developers
## Prerequisites:
- [VSCode](https://code.visualstudio.com/download)
- [Miniconda 2023.1.0 or later](https://docs.conda.io/en/latest/miniconda.html)

### Configuration
1.  Download this repository and check out the appropriate branch
2.  Navigate to the `radio_collar_tracker_gcs` project in a python capable terminal
3.  Run `conda create --name rctGCS --file conda-[os].lock`
4.  Run `conda activate rctGCS`
5.  Run `poetry install`
6.  Open VSCode. Open the `radio_collar_tracker_gcs` project
7.  Open the command palette (`Ctrl`+`Shift`+`P`)
8.  Select `Python: Select Interpreter`/`Python 3.9.16 ('rctGCS')`
9.  Install recommended extensions
