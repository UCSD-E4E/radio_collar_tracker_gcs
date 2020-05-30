# RCT GCS
This is the redevelopment of the Radio Telemetry Tracker Ground Control Station
from v1.0.  Working branch v1.0a, becomes v2.0 on release

## Dependencies
1.	python3-tk

radio_collar_tracker_drone
====================
Airborne Wildlife Radio Collar Tracker - UAS Component

Engineers for Exploration, UCSD Project



# For Developers
## Prerequisites:
- Eclipse 2020-03 for C/C++ Developers
    - Link: https://www.eclipse.org/downloads/
    - Plugins: PyDev (https://wiki.python.org/moin/PyDev)
- Python 3.6
    - For Windows: https://www.anaconda.com/products/individual
    - For Ubuntu: Use 18.04

### Configuration
1.  Navigate to the `scripts` folder in the `radio_collar_tracker_gcs` project in a python capable terminal
2.  Run `pipenv install`
1.  Install Eclipse 2020-03 for C/C++ Developers
2.  Install PyDev in Eclipse
3.  Open Eclipse.  Set the workspace to the `radio_collar_tracker_gcs` project root.
4.  Create a new project using File/New/Project...
5.  Create a new PyDev Project
10. Set the project name to `scripts`
11. Click `Please configure an interpreter before proceeding`
12. Click `Choose from list`
13. Select a Python 3 interpreter from the list and click `OK`
14. When asked to select folders to be added to the SYSTEM pythonpath, simply click `OK`
15. Click `Click here to configure an interpreter not listed`
16. Click `Create using pipenv`
17. Click `Create Pipenv interpreter`
18. Click `OK`
19. Click `Finish`
20. When asked to `Open the PyDev Perspective`, click `Open Perspective`
21. Configure the run configurations by clicking `Run`/`Run Configurations...`:
    a.  rctGCS.py
        1)  Create a new `Python Run` launch configuration
        2)  Set the project to `scripts`
        3)  Set the `Main Module` to `${workspace_loc:scripts/rctGCS.py}`
        4)  In the `Interpreter` tab, set the `Interpreter` to `scripts (pipenv)`
        5)  Set the name to `rctGCS`
        6)  Click `Apply`
        7)  Click `Close`

### Adding Packages
1.  Open `Windows`/`Preferences`/`PyDev`/`Interpreters`/`Python Interpreters`
2.  Select the `scripts (pipenv)` interpreter
3.  Click `Manage with pipenv`
4.  Enter `install package` with the appropriate package to install