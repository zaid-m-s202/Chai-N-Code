#!/usr/bin/env python3
"""Seed the database using the complete Pune PostGIS data ingestion engine."""

import os
import sys

# Ensure the backend package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.import_pune_data import ingest_pune_data


def seed():
    ingest_pune_data()


if __name__ == "__main__":
    seed()
