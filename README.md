# RCT GCS
This is the redevelopment of the Radio Telemetry Tracker Ground Control Station
from v1.0. Working branch v1.0a, becomes v2.0 on release

## Installation on Ubuntu (18.04+)
1.  [Install Miniconda](https://docs.conda.io/en/latest/miniconda.html)
2.  Download this repository
3.  Navigate to the `radio_collar_tracker_gcs` project in a python capable terminal
4.  Run `conda create --name rctGCS --file conda-linux.lock`
5.  Run `conda activate rctGCS`
6.  Run `poetry install`
7.  Set the `_CONDA_ROOT` environment variable by echoing it into your `.bashrc` file. Replace `/path/to/miniconda3` with your actual Miniconda installation path:
    ```bash
    echo 'export _CONDA_ROOT=/path/to/miniconda3' >> ~/.bashrc
    ```
8.  Source your `.bashrc` to apply the changes:
    ```bash
    source ~/.bashrc
    ```

## Installation on Windows 10+
1.  [Install Miniconda](https://docs.conda.io/en/latest/miniconda.html)
2.  Navigatte to conda bin (likey at `C:\Users\<user>\anaconda3\condabin`) and run `.\conda init`.
3.  Run `Set-ExecutionPolicy RemoteSigned`
4.  Download this repository
5.  Navigate to the `radio_collar_tracker_gcs` project in a python capable terminal
6.  Run `conda create --name rctGCS --file conda-win.lock`
7.  Run `conda activate rctGCS`
8.  Run `poetry install`

## Running `rctGCS`
1.  From the command line, run `conda activate rctGCS`
2.  Run `RCTGcs`

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
