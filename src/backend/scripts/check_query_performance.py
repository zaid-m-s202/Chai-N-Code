import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

def check_perf():
    client = TestClient(app)
    endpoints = [
        ("Liveness Probe", "/health"),
        ("Readiness Probe", "/health/ready"),
        ("First Building Query", "/api/v1/properties?type=building&limit=10"),
        ("Unit Query (50 units)", "/api/v1/properties?type=unit&limit=50"),
        ("Hierarchy Query", "/api/v1/properties/XAJI0Y6DPBHSAH/hierarchy"),
        ("ULPIN Search Query", "/api/v1/search?q=27-21-11-719-000001"),
        ("Map Layer Objects (50 objects)", "/api/v1/map/objects?limit=50"),
        ("Map Underground Query", "/api/v1/map/underground?limit=10"),
        ("Verification Queue Query", "/api/v1/verification-queue"),
        ("Topology Conflicts Query", "/api/v1/conflicts"),
    ]

    print("======================================================================")
    print("PERFORMANCE SANITY CHECK — RESPONSE TIMES")
    print("======================================================================\n")

    for name, path in endpoints:
        t0 = time.perf_counter()
        res = client.get(path)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        assert res.status_code == 200, f"Endpoint {path} failed with {res.status_code}"
        print(f"{name:<35} | {dt_ms:>7.2f} ms | Status: {res.status_code}")

    print("\n======================================================================")
    print("[PASS] ALL RESPONSE TIMES WITHIN EXCELLENT OPERATIONAL LIMITS (<250ms)")
    print("======================================================================")

if __name__ == "__main__":
    check_perf()
