# RCT GCS
This is the redevelopment of the Radio Telemetry Tracker Ground Control Station
from v1.0.  Working branch v1.0a, becomes v2.0 on release

## Dependencies
1.	python3-tk
2.  libgeos-dev
3.  libgdal-dev

## Installation on Ubuntu (18.04+)
1.  `apt-get install -y python3-tk libgeos-dev libgdal-dev=2.2.3+dfsg-2`
2.  `pip3 install pipenv`
3.  `pipenv install`


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

radio_collar_tracker_drone
====================
Airborne Wildlife Radio Collar Tracker - UAS Component

Engineers for Exploration, UCSD Project

Installing the payload software
===============================
1.	Install the required dependencies
	1.	python3
		1.	`apt-get install python3`
	2.  boost
		1.	`apt-get install libboost-all-dev`
	3.  pythom-mako
		1.	`apt-get install python-mako`
	4.  six
		1.	`pip install six`
	5.  requests
		1.	`pip install requests`
	7.  enum
		1.	`pip install enum`
	8.  pyserial
		1.  `pip3 install pyserial`
	5.	libusb-dev
		1.	`apt-get install libusb-1.0-0-dev`
	9.	libuhd 3.11.01
		1.	`apt-get install cmake build-essential`
		2.	`git clone git://github.com/EttusResearch/uhd.git`
		3.	`cd <uhd_repo>/host`
		4.	`git checkout v3.11.0.1`
		5.	`mkdir build`
		6.	`cd build`
		7.	`cmake -DENABLE_B100=OFF -DENABLE_X300=OFF -DENABLE_N230=OFF -DENABLE_USRP1=OFF -DENABLE_USRP2=OFF -DENABLE_OCTOCLOCK=OFF -DENABLE_RFNOC=OFF -DENABLE_MPMD=OFF -DENABLE_EXAMPLES=OFF -DENABLE_MANUAL=OFF -DENABLE_TESTS=OFF ../`
		8.	`make`
		9.	`make install`
		10.	`ldconfig`
		11.	`/usr/local/lib/uhd/utils/uhd_images_downloader.py -t b2xx*`
	10.	fftw
		1.	`wget http://www.fftw.org/fftw-3.3.8.tar.gz`
		2.	`tar -xzf fftw-3.3.8.targ.gz`
		3.	`cd <fftw>`
		4.	`./bootstrap.sh && ./configure --enable-threads 
		--enable-generic-simd128 --enable-generic-simd256`
		5.	`make`
		6.	`make install`
2.	Install the software
	1.	`cd <radio_collar_tracker_drone>`
	2.	`git checkout online_proc`
	2.  `./autogen.sh`
	3.  `./configure`
	4.	`make`
	5.	`sudo make install`

tl;dr
-----
1.	`sudo apt-get update`
2.	`sudo apt-get install -y git vim htop gdb valgrind cmake build-essential python3 libboost-all-dev python-mako python3-pip libusb-1.0-0-dev autoconf pkg-config picocom python-pip zip wget tmux`
3.	`sudo pip2 install six requests`
4.	`sudo pip3 install pyserial`
5.	`git clone git://github.com/EttusResearch/uhd.git`
6.	`cd uhd`
7.	`git checkout v3.11.0.1`
8.	`mkdir build`
9.	`cd build`
10.	`cmake -DENABLE_B100=OFF -DENABLE_X300=OFF -DENABLE_N230=OFF -DENABLE_USRP1=OFF -DENABLE_USRP2=OFF -DENABLE_OCTOCLOCK=OFF -DENABLE_RFNOC=OFF -DENABLE_MPMD=OFF -DENABLE_EXAMPLES=OFF -DENABLE_MANUAL=OFF -DENABLE_TESTS=OFF ../`
11.	`make -j8`
12.	`sudo make install`
13.	`sudo ldconfig`
14.	`sudo /usr/local/lib/uhd/utils/uhd_images_downloader.py -t b2xx*`
15.	`cd ../..`
16.	`wget http://www.fftw.org/fftw-3.3.8.tar.gz`
17.	`tar -xzf fftw-3.3.8.tar.gz`
18.	`cd fftw-3.3.8`
19.	`./boostrap.sh`
20.	`./configure --enable-threads --enable-generic-simd128 --enable-generic-simd256`
21.	`make -j8`
22.	`sudo make install`
23.	`cd ../`
24.	`git clone git://github.com/UCSD-E4E/radio_collar_tracker_drone.git`
25.	`cd radio_collar_tracker_drone`
26.	`git checkout online_proc`
27.	`./autogen.sh`
28.	`./configure`
29.	`make -j8`
30.	`sudo make install`

Running the payload software (standalone)
=========================================
`sudo service rctrun start`

# Running the payload software (hardware-based initialization)

## Payload Power On Procedure
1.	Disconnect power to AUTOPILOT, PAYLOD
2.	Connect power to PAYLOAD
3.	Connect power to AUTOPILOT
4.	Flip PAYLOAD SWITCH to the ON position.
5.	Wait for the PAYLOAD STATUS LIGHT to turn green for at least 10 seconds.
6.	Flip PAYLOAD SWITCH to the OFF position.
7.	Wait for the PAYLOAD STATUS LIGHT to turn off within 5 seconds.
8.	Connect the GROUND CONTROL STATION to the AUTOPILOT.
9.	Payload Power On Procedure complete.

## Payload Start Procedure
1.	Complete the Payload Power On Procedure.
2.	Flip PAYLOAD SWITCH to the ON position.
3.	Wait for the PAYLOAD STATUS LIGHT to turn green for at least 10 seconds.
4.	Payload Start Procedure complete.

## Payload Stop Procedure
1.	Flip PAYLOAD SWITCH to the OFF position.
2.	Wait for the PAYLOAD STATUS LIGHT to turn off within 5 seconds.
3.	Payload Stop Procedure complete.

## Payload Power Off Procedure
1.	Complete the Payload Stop Procedure.
2.	Disconnect power to the PAYLOAD.
3.	Payload Power Off Procedure complete.

Output Data Format
==================
Output data location is specified in `/usr/local/etc/rct_config`.  Each run
consists of a number of IQ (raw) data files, GPS data files, and a metadata
file.  The name format for each type of file is `[type]_[run]_[file_num]`.  
The `type` field specifies, in capital letters, the type of file (i.e. RAW_DATA,
GPS, or META).  The `run` field specifies a numerical identifier for each run,
assigned sequentially. This field is always 6 characters wide, zero padded.  The
`file_num` field specifies the ordering of the IQ data files.  The first file
recorded would have a file number of 1, sequential files having sequential
numbers.  This field is always 6 characters wide, zero padded.

The raw data files contain the raw IQ data recorded as pairs of 8-bit unsigned
integers.  Each pair represents the in-phase and quadrature components of the
recorded signal in sequence.  See
https://en.wikipedia.org/wiki/In-phase_and_quadrature_components for an
explanation of IQ signal representation.

The GPS data files contain timestamped snapshots of autopilot telemetry.

The metadata file contains metadata pertaining to the configuration of the
payload.  Each line contains one field.  The key for each field is followed by a
colon, then the value for that field, followed by a newline character:
```
[field_name]: [field_value]
```
The whitespace between the colon and field value is optional, and preferred for
readability, but cannot be a newline.  The metadata file contains the following
fields: local IQ data start time (UTC in seconds), SDR center frequency (Hz),
SDR sampling frequency (Hz), SDR gain (dB).

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