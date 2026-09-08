"""Tests for geometric validation service (PRD §5.6 / VR-01, VR-02)."""

from shapely.geometry import Polygon
from app.services.validation import containment_ok, overlap_ratio


def test_containment_ok_when_inside():
    parcel = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    building = Polygon([(2, 2), (6, 2), (6, 6), (2, 6)])
    assert containment_ok(building, parcel) is True


def test_containment_fails_when_protruding():
    parcel = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    building = Polygon([(8, 8), (12, 8), (12, 12), (8, 12)])
    assert containment_ok(building, parcel) is False


def test_containment_with_tolerance():
    parcel = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    # Building exceeds slightly: touches 10.5
    building = Polygon([(1, 1), (10.5, 1), (10.5, 9), (1, 9)])
    assert containment_ok(building, parcel, tolerance=0.0) is False
    assert containment_ok(building, parcel, tolerance=1.0) is True


def test_overlap_ratio():
    poly_a = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])  # area 16
    poly_b = Polygon([(2, 0), (6, 0), (6, 4), (2, 4)])  # area 16, intersection is (2,0)-(4,4) = area 8, union 24
    ratio = overlap_ratio(poly_a, poly_b)
    assert round(ratio, 2) == round(8 / 24, 2)


def test_disjoint_overlap_is_zero():
    poly_a = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    poly_b = Polygon([(5, 5), (7, 5), (7, 7), (5, 7)])
    assert overlap_ratio(poly_a, poly_b) == 0.0
