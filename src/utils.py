"""
Provides utility functions for data directory setup, JSON operations, spatial
data operations, and validation of spatial coordinate reference systems (CRS).

This module includes functions to create necessary data directories, serialize
and deserialize JSON files, load and save shapefiles and GeoJSON data, determine
if a point is within a polygon, and validate or reproject GeoDataFrames to match
a specified CRS.
"""

import json
from pathlib import Path

import geopandas as gpd
from geopandas import GeoDataFrame
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.point import Point

import src.config as cfg


def setup_data_directories() -> None:
    """
    Creates directories for raw, processed, interim, and external data paths
    if they do not already exist. The paths are retrieved from the global
    configuration and their parent directories are ensured to exist.

    :raises OSError: Raised if there is an issue creating the directories.
    :return: None
    """
    Path(cfg.RAW_DATA_PATH).mkdir(parents=True, exist_ok=True)
    Path(cfg.PROCESSED_DATA_PATH).mkdir(parents=True, exist_ok=True)
    Path(cfg.INTERIM_DATA_PATH).mkdir(parents=True, exist_ok=True)
    Path(cfg.EXTERNAL_DATA_PATH).mkdir(parents=True, exist_ok=True)
    Path(cfg.PDF_DUMP_PATH).mkdir(parents=True, exist_ok=True)


def load_json_from_path(path: Path) -> dict:
    """
    Loads a JSON object from a file located at the specified path.

    This function opens the file at the given path, reads its contents,
    and parses it as a JSON object, returning the resulting dictionary.

    :param path: The path to the JSON file. Must be provided as a Path object.
    :return: A dictionary representing the parsed JSON object from the file.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json_to_path(data: dict | list, path: Path) -> None:
    """
    Serialize a Python dictionary as JSON and save it to a file at the specified path.

    This function takes a Python dictionary and saves it as a JSON file with an
    indentation level of 4 spaces. If the file at the given path already exists,
    it will be overwritten.

    :param data: The dictionary to be serialized to JSON.
    :type data: dict
    :param path: The file path where the JSON content should be saved.
    :type path: Path
    :return: None
    """
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_shapefile(path: Path) -> gpd.GeoDataFrame:
    """
    Loads a shapefile and returns it as a GeoDataFrame.

    This function reads a shapefile from the specified file path and converts it
    into a GeoDataFrame using the GeoPandas library. The shapefile should be
    accessible at the provided path.

    :param path: A ``Path`` object representing the file path of the shapefile to
        be loaded.
    :return: A GeoDataFrame containing the spatial data from the shapefile.
    :rtype: gpd.GeoDataFrame
    """
    with open(path, encoding='utf-8') as f:
        return gpd.read_file(f)


def save_shapefile(df: gpd.GeoDataFrame, path: Path) -> None:
    """
    Saves a given GeoDataFrame as a GeoJSON file to the specified path.

    This function uses the GeoPandas library to serialize a GeoDataFrame and write it
    to a file in GeoJSON format.

    :param df: The GeoDataFrame containing spatial data to be saved.
    :type df: gpd.GeoDataFrame
    :param path: The file path where the GeoJSON file will be saved.
    :type path: Path
    :return: None
    """
    df.to_file(path, driver='GeoJSON')


def point_in_polygon(point: Point, polygon: MultiPolygon) -> bool:
    """
    Checks if a given point is inside a given polygon.
    :param point: shapely Point
    :param polygon: shapely MultiPolygon
    :return: True, if the point is inside the polygon, False otherwise.
    """
    return polygon.contains(point)


def validate_crs(gdf: GeoDataFrame) -> GeoDataFrame:
    """
    Validates and adjusts the coordinate reference system (CRS) of the provided GeoDataFrame.

    If the CRS of the given GeoDataFrame does not match the required CRS specified in the
    configuration (`cfg.CRS`), the function reprojects the GeoDataFrame to the correct CRS.
    The resulting GeoDataFrame is then returned.

    :param gdf: A GeoDataFrame whose CRS needs to be validated against the required CRS.
    :type gdf: GeoDataFrame
    :return: A GeoDataFrame with its CRS matching the required CRS.
    :rtype: GeoDataFrame
    """
    if gdf.crs != cfg.CRS:
        gdf = gdf.to_crs(cfg.CRS)
    return gdf