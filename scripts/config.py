'''Provides global configuration structures
'''
from __future__ import annotations

import os
from configparser import ConfigParser
from enum import Enum
from pathlib import Path
from socket import gaierror, gethostbyname
from typing import Any, Dict, Tuple


class ConnectionMode(Enum):
    """GCS Connection Modes

    Args:
        Enum (str):
    """
    DRONE = 'drone'
    TOWER = 'tower'

class Configuration:
    """Configuration file interface object
    """
    def __init__(self, config_path: Path) -> None:
        self.__config_path = config_path

        self.__map_extent_nw: Tuple[float, float] = (90., -180.)
        self.__map_extent_se: Tuple[float, float] = (-90., 180.)

        self.__qgis_prefix_path: Path = self.__get_qgis_path()
        self.__qgis_prefix_set: bool = False

        self.__connection_addr: str = '127.0.0.1'
        self.__connection_port: int = 9000
        self.__connection_mode: ConnectionMode = ConnectionMode.DRONE

    def __create_dict(self):
        return {
            "FilePaths": {
                "PrefixPath": self.__qgis_prefix_path.as_posix(),
                "PrefixSet" : self.__qgis_prefix_set
            },
            "LastCoords": {
                'lat1': self.__map_extent_nw[0],
                'lat2': self.__map_extent_se[0],
                'lon1': self.__map_extent_nw[1],
                'lon2': self.__map_extent_se[1]
            },
            "Connection": {
                'addr': self.__connection_addr,
                'port': self.__connection_port,
                'mode': self.__connection_mode.value
            }
        }

    def load(self) -> None:
        """Loads the configuration from the specified file
        """
        parser = ConfigParser()
        parser.read_dict(self.__create_dict())
        parser.read(self.__config_path.as_posix())

        if parser['FilePaths']['PrefixPath'] is None:
            self.__qgis_prefix_path = self.__get_qgis_path()
        else:
            self.__qgis_prefix_path = Path(parser['FilePaths']['PrefixPath'])

        self.__qgis_prefix_set = parser['FilePaths'].getboolean('PrefixSet')

        self.__map_extent_nw = (
            parser['LastCoords'].getfloat('lat1'),
            parser['LastCoords'].getfloat('lon1')
            )
        self.__map_extent_se = (
            parser['LastCoords'].getfloat('lat2'),
            parser['LastCoords'].getfloat('lon2')
            )

        self.__connection_port = parser['Connection'].getint('port')
        self.__connection_addr = parser['Connection'].getint('addr')
        self.__connection_mode = ConnectionMode(parser['Connection']['mode'])

    def write(self) -> None:
        """Writes the configuration to the file
        """
        parser = ConfigParser()
        parser.read_dict(self.__create_dict())
        with open(self.__config_path, 'w', encoding='ascii') as handle:
            parser.write(handle)

    @property
    def connection_port(self) -> int:
        """Last connection port

        Returns:
            int: Connection port
        """
        return self.__connection_port

    @connection_port.setter
    def connection_port(self, value: Any) -> None:
        if not isinstance(value, int):
            raise TypeError
        if not 0 <= value < 65536:
            raise ValueError
        self.__connection_port = value

    @property
    def connection_addr(self) -> str:
        """Last connection address

        Returns:
            str: Connection address
        """
        return self.__connection_addr

    @connection_addr.setter
    def connection_addr(self, value: Any) -> None:
        if not isinstance(value, str):
            raise TypeError
        try:
            gethostbyname(value)
        except gaierror as exc:
            raise ValueError from exc
        self.__connection_addr = value

    @property
    def connection_mode(self) -> ConnectionMode:
        """Connection mode for GCS

        Returns:
            ConnectionMode: GCS connection mode
        """
        return self.__connection_mode

    @connection_mode.setter
    def connection_mode(self, value: Any) -> None:
        if not isinstance(value, ConnectionMode):
            raise TypeError
        self.__connection_mode = value

    @property
    def map_extent(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Map previous extent

        Returns:
            Tuple[Tuple[float, float], Tuple[float, float]]: NW and SE map extents in dd.dddddd
        """
        return (self.__map_extent_nw, self.__map_extent_se)

    @map_extent.setter
    def map_extent(self, value: Any) -> None:
        if not isinstance(value, tuple):
            raise TypeError
        if len(value) != 2:
            raise TypeError
        for coordinate in value:
            if not isinstance(coordinate, tuple):
                raise TypeError
            if len(value) != 2:
                raise TypeError

            if not isinstance(coordinate[0], float):
                raise TypeError
            if not -90 <= coordinate[0] <= 90:
                raise ValueError

            if not isinstance(coordinate[1], float):
                raise TypeError
            if not -180 <= coordinate[1] < 180:
                raise ValueError
        self.__map_extent_nw = value[0]
        self.__map_extent_se = value[1]

    @property
    def qgis_prefix_path(self) -> Path:
        """QGis Installation Prefix

        Returns:
            Path: Path to QGis Install
        """
        return self.__qgis_prefix_path

    @qgis_prefix_path.setter
    def qgis_prefix_path(self, value: Any) -> None:
        if not isinstance(value, Path):
            raise TypeError
        if not value.is_dir():
            raise ValueError
        self.__qgis_prefix_path = value

    @property
    def qgis_prefix_set(self) -> bool:
        """QGis Prefix Set Flag

        Returns:
            bool: True if set, otherwise False
        """
        return self.__qgis_prefix_set

    @qgis_prefix_set.setter
    def qgis_prefix_set(self, value: Any) -> None:
        if not isinstance(value, bool):
            raise TypeError
        self.__qgis_prefix_set = value

    @classmethod
    def __get_qgis_path(cls) -> Path:
        if "_CONDA_ROOT" not in os.environ:
            raise RuntimeError("Not a conda environment")
        pkgs_dir = Path(os.environ['_CONDA_ROOT']).joinpath('pkgs')
        qgis_dirs = [qgis_dir for qgis_dir in pkgs_dir.glob('qgis*') if qgis_dir.is_dir()]
        return sorted(qgis_dirs)[-1]

    def __enter__(self) -> Configuration:
        self.load()
        return self

    def __exit__(self, exc, exp, exv) -> None:
        self.write()


__config_instance: Dict[Path, Configuration] = {}
def get_instance(path: Path) -> Configuration:
    """Retrieves the corresponding configuration instance singleton

    Args:
        path (Path): Path to config path

    Returns:
        Configuration: Configuration singleton
    """
    if path not in __config_instance:
        __config_instance[path] = Configuration(path)
    return __config_instance[path]
