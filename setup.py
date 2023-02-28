"""Example setup file
"""
from setuptools import setup, find_packages

setup(
    name='RctGcs',
    version='0.0.0.1',
    author='UCSD Engineers for Exploration',
    author_email='e4e@eng.ucsd.edu',
    entry_points={
        'console_scripts': [
            'RCTGcs = RctGcs.rctGCS:main',
            'droneSimulator = RctGcs.droneSimulator:main',
        ]
    },
    packages=find_packages(),
    install_requires=[
        "RCTComms @ git+https://github.com/UCSD-E4E/radio_collar_tracker_comms.git",
        "appdirs",
        "utm"
    ],
    extras_require={
        'dev': [
            'pytest',
            'coverage',
            'pylint',
            'wheel',
        ]
    },
)