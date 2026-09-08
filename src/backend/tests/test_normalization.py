"""Tests for GIS CRS normalization, unit normalization, and geometry validation."""

import pytest
from shapely.geometry import Point, Polygon
from app.services.normalization import (
    normalize_crs,
    normalize_unit,
    validate_and_repair_geometry,
    CANONICAL_CRS,
)


def test_unit_normalization_feet_to_meters():
    # 10 feet = 3.048 meters
    res = normalize_unit(10.0, "ft")
    assert res == 3.048

    # Strings with embedded units
    assert normalize_unit("100 feet") == 30.48
    assert normalize_unit("50ft") == 15.24
    assert normalize_unit("10 inches") == 0.254
    assert normalize_unit("10 yd") == 9.144
    assert normalize_unit("25.5 m") == 25.5
    assert normalize_unit(None) is None


def test_geometry_validation_and_repair():
    # Valid polygon passes through
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    repaired = validate_and_repair_geometry(poly)
    assert repaired.is_valid

    # Self-intersecting bowtie polygon
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bowtie.is_valid
    repaired_bowtie = validate_and_repair_geometry(bowtie)
    assert repaired_bowtie is not None
    assert repaired_bowtie.is_valid


def test_crs_normalization_epsg3857_to_4326():
    # Bengaluru coordinates in EPSG:3857: approx x=8637775.5, y=1456209.4
    # Corresponding to approx lon=77.5945, lat=12.9715 in EPSG:4326
    pt_3857 = Point(8637775.5, 1456209.4)
    pt_4326 = normalize_crs(pt_3857, source_crs="EPSG:3857", target_crs=CANONICAL_CRS)

    assert pt_4326 is not None
    assert pytest.approx(pt_4326.x, abs=0.01) == 77.5945
    assert pytest.approx(pt_4326.y, abs=0.01) == 12.9715


def test_crs_normalization_already_4326_is_noop():
    pt = Point(77.5945, 12.9715)
    transformed = normalize_crs(pt, source_crs="EPSG:4326", target_crs="EPSG:4326")
    assert transformed.x == pt.x
    assert transformed.y == pt.y
