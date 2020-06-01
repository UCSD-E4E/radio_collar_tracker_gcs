# RCT GCS
This is the redevelopment of the Radio Telemetry Tracker Ground Control Station
from v1.0.  Working branch v1.0a, becomes v2.0 on release

## Installation on Ubuntu (18.04+) and Windows 10+
1.  Install Anaconda 2020.02
2.  Run `conda env create -f environment.yml`
3.  Run `conda activate rctGCS`

## Running `rctGCS`
-   Windows:
    1.  Run `rctGCS.bat` by double clicking or running from command line
    
## Setting up simulator for GCS
1.  `> ssh -L 9002:localhost:9002 rct-ui@e4e-brix.dynamic.ucsd.edu`
2.  `rct-ui@e4e-brix> tmux`
3.  `rct-ui@e4e-brix (tmux a)> ~/connect_UPCORE`
4.  `e4e@e4e-UPCORE-1 (tmux a)> sudo service rctstart stop`
5.  `e4e@e4e-UPCORE-1 (tmux a)> ~/simulator`
6.  `rct-ui@e4e-brix (tmux b)> ~/forward_RCT.sh`
7.  `> cd scripts`
8.  `> python rctGCS.py`
9.  `> mkfifo /tmp/fifo`
10. `> netcat -b -u localhost 9000 < /tmp/fifo | netcat localhost 9002 > /tmp/fifo`

Note that for step 5 to step 6, you will need to switch to a new tmux pane.

For step 9 to step 10, `rctGCS.py` should be trying to connect during this time.

Steps 5, 6, 8, and 10 should not return to a prompt immediately.

Essentially, start the simulator on the payload, start the UDP forwarding on the Brix, start the GCS, then start the UDP translating on the local machine.

# For Developers
## Prerequisites:
- Eclipse 2020-03 for C/C++ Developers
    - Link: https://www.eclipse.org/downloads/
    - Plugins: PyDev (https://wiki.python.org/moin/PyDev)
- Python 3.6
    - Anaconda 2020.02 or later

### Configuration
1.  Navigate to the `scripts` folder in the `radio_collar_tracker_gcs` project in a python capable terminal
2.  Run `conda env create -f environment.yml`
3.  Install Eclipse 2020-03 for C/C++ Developers
4.  Open Eclipse.  Set the workspace to the `radio_collar_tracker_gcs` project root.
5.  Install PyDev in Eclipse if not already installed
    1. `Help`/`Install New Software...`
    2. Work with `http://www.pydev.org/updates`
    3. Select `PyDev`
6.  Configure a new interpreter by going to `Window`/`Preferences`/`PyDev`/`Interpreters`/`Python Interpreters`
7.  Click `Browse for python/pypy exe`
8.  Navigate to the location of the environment created in step 2
    a.  In Windows, this is likely to be `C:\Users\${username}\.conda\envs\rctGCS\python.exe`
    b.  In Ubuntu, this is likely to be `/home/${username}/anaconda3/envs/rctGCS/bin/python`
9.  Set the `Interpreter Name` to `rctGCS` and click `OK`
10. When asked to select folders to be added to the SYSTEM pythonpath, simply click `OK`
11. Ensure the checkbox labelled `Load conda env vars before run?` is checked.
12. Click `Apply and Close`
13. Import a new project using `File`/`Import...`
14. Select `Existing Projects into Workspace` under `General`
15. Set the root directory to the workspace directory
16. Ensure that the `scripts` project is selected
17. Click `Finish`
18. Close the Welcome page
19. Configure the run configurations by clicking `Run`/`Run Configurations...`:
    a.  rctGCS.py
        1)  Create a new `Python Run` launch configuration
        2)  Set the project to `scripts`
        3)  Set the `Main Module` to `${workspace_loc:scripts/rctGCS.py}`
        4)  Set the name to `rctGCS`
        6)  Click `Apply`
        7)  Click `Close`

### Adding Packages
1.  Open `Windows`/`Preferences`/`PyDev`/`Interpreters`/`Python Interpreters`
2.  Select the `rctGCS` interpreter
3.  Click `Manage with conda`
4.  Enter the appropriate package to install