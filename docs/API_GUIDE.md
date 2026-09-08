# 3D Cadastral Intelligence System — REST API Technical Guide

This document provides a technical reference for the 3D Cadastral Intelligence REST API.

---

## 1. Global Conventions & Standards

- **Base URL**: `http://localhost:8000/api/v1` (or production host)
- **Content-Type**: `application/json` (except multipart file uploads)
- **Spatial CRS**: `EPSG:4326` (WGS 84, Coordinates: `[longitude, latitude]`)
- **Authentication**: Bearer Token JWT passed in the HTTP Authorization header:
  ```http
  Authorization: Bearer <access_token>
  ```
- **Security Headers**: All responses include OWASP-compliant headers (`X-Content-Type-Options`, `X-Frame-Options`, `X-Request-ID`, `Strict-Transport-Security`).
- **Standard Error Format**:
  ```json
  {
    "detail": "Descriptive error message indicating the violation or policy failure"
  }
  ```

---

## 2. Authentication & Identity Management

### `POST /api/v1/auth/login`
Authenticates a user with username and password, returning a JWT token.
- **Access**: Public
- **Request Body**:
  ```json
  {
    "username": "officer_sharma",
    "password": "DemoPass123!"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
    "token_type": "bearer"
  }
  ```

### `POST /api/v1/auth/quick-token`
Generates a signed JWT for testing role-based workflows without entering passwords.
- **Access**: Public (Demo / Testing Mode)
- **Query Parameters**: `role` (`VERIFYING_OFFICER` | `FIELD_SURVEYOR` | `PUBLIC_VIEWER` | `ADMIN`)
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
    "token_type": "bearer"
  }
  ```

### `GET /api/v1/auth/me`
Returns details of the currently authenticated user session.
- **Access**: Authenticated

---

## 3. Sensor Ingestion & Provenance

### `POST /api/v1/ingestion/jobs`
Uploads a geospatial file (GeoJSON or tabular CSV with WKT) for asynchronous processing.
- **Access**: Surveyor, Officer, Admin
- **Request**: Multipart Form Data (`file: <binary>`, optional `source_system: string`)
- **Response `200 OK`**:
  ```json
  {
    "job_id": "8b087095-2c0b-47e1-95ad-a1288c3a5b04",
    "filename": "ward_pilot_footprints.geojson",
    "format": "geojson",
    "status": "COMPLETED",
    "record_count": 18,
    "file_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
  }
  ```

### `GET /api/v1/ingestion/jobs/{id}`
Retrieves the execution status, progress, and error logs of an ingestion job.
- **Access**: Public

---

## 4. 3D Spatial Hierarchy & Property Intelligence

### `GET /api/v1/properties`
Queries active property objects with pagination and filtering.
- **Query Parameters**:
  - `status`: Filter by status (`SYNTHETIC`, `INFERRED`, `DERIVED`, `PROVISIONAL`, `VERIFIED`)
  - `type`: Filter by level (`parcel`, `building`, `floor`, `unit`)
  - `parent_id`: Filter by parent UUID
  - `limit` (default: 50), `offset` (default: 0)
- **Response `200 OK`**: Array of `PropertyObjectResponse` items.

### `GET /api/v1/properties/{id}`
Returns complete spatial, volumetric, confidence, and semantic metadata for a single property by UUID or `three_d_property_id`.
- **Response `200 OK`**:
  ```json
  {
    "id": "7b0b9794-06da-4d76-96b6-3a78f24b277d",
    "three_d_property_id": "INMH0234567-B001-F01-U001",
    "type": "unit",
    "parent_id": "c13876d7-873b-48bc-b34a-95ec88a09cf9",
    "status": "VERIFIED",
    "confidence": 1.0,
    "z_min": 560.0,
    "z_max": 563.5,
    "attributes": {
      "unit_number": "101",
      "carpet_area_sqm": 240.0,
      "use": "Bank Branch"
    },
    "created_at": "2026-09-07T12:00:00Z"
  }
  ```

### `GET /api/v1/properties/{id}/history`
Fetches the immutable, event-sourced chronological change log (`ChangeEvent` records).
- **Access**: Public

### `GET /api/v1/properties/{id}/evidence`
Lists all provenance records, source file references, and SHA-256 hashes attached to the object.
- **Access**: Public

### `GET /api/v1/properties/{id}/observations`
Returns all raw, un-aggregated sensor observations (`SourceObservation` records) from all vendors.
- **Access**: Public

### `POST /api/v1/properties/{id}/refuse`
Re-runs the multi-source weighted consensus algorithm across all observations for the object.
- **Access**: Verifying Officer, Admin

---

## 5. Statutory Verification & Officer Queue

### `GET /api/v1/verification-queue`
Returns all properties currently in `PROVISIONAL` status awaiting officer review.
- **Query Parameters**: `has_conflicts` (`true` | `false` | omitted for all)
- **Response `200 OK`**: Array of provisional property objects with conflict flags.

### `POST /api/v1/properties/{id}/verify`
Statutory verification endpoint. Promotes a `PROVISIONAL` record to `VERIFIED` and sets `confidence = 1.0`.
- **Access**: **Verifying Officer, Admin** (Requires valid JWT with role)
- **Rule VR-09 Enforcement**: If the property or its immediate children have open `Conflict` records, the request is rejected with `409 Conflict`.
- **Request Body**:
  ```json
  {
    "notes": "Verified against sanctioned building layout drawings dated 2026-03-12."
  }
  ```
- **Response `200 OK`**: Updated `PropertyObject` with `status: "VERIFIED"`.

### `POST /api/v1/properties/{id}/reject`
Rejects a provisional submission, returning it to draft with officer notes and creating an audit record.
- **Access**: **Verifying Officer, Admin**
- **Request Body**:
  ```json
  {
    "notes": "Rejected: boundary survey overhang of 14cm exceeds building envelope."
  }
  ```

---

## 6. Deterministic Topology & Conflict Register

### `GET /api/v1/conflicts`
Lists recorded topological, geometric, and fusion violations.
- **Query Parameters**:
  - `status`: `OPEN`, `RESOLVED`, `WAIVED`
  - `rule_code`: `VR-01` through `VR-08`
  - `property_object_id`: Target property UUID

### `POST /api/v1/conflicts/run-topology`
Triggers batch deterministic rule evaluation across the spatial hierarchy.
- **Access**: **Verifying Officer, Admin**
- **Response `200 OK`**:
  ```json
  {
    "message": "Topology validation completed.",
    "total_violations": 2,
    "violations_by_rule": {
      "VR-02": 1,
      "VR-04": 1
    }
  }
  ```

### `POST /api/v1/conflicts/{id}/resolve`
Marks a conflict as resolved with explanatory notes.
- **Access**: **Verifying Officer, Admin**

### `POST /api/v1/conflicts/{id}/waive`
Statutory waiver of a non-critical discrepancy (e.g. minor non-structural architectural overhang).
- **Access**: **Verifying Officer, Admin**

---

## 7. Geospatial Search & Map Layers

### `GET /api/v1/search?q={query}`
Full-text and identifier search supporting 3D Property ID prefix, ULPIN, building name, or ward.
- **Query Parameters**: `q` (e.g., `INMH0234567` or `Kalyani`)
- **Response `200 OK`**: Array of matching properties with spatial coordinates and status.

### `GET /api/v1/map/objects`
Returns a GeoJSON `FeatureCollection` for MapLibre / WebGL 2D/3D map rendering.
- **Query Parameters**:
  - `bbox`: Bounding box `min_lon,min_lat,max_lon,max_lat`
  - `type`: Optional level filter (`parcel`, `building`, `unit`)
  - `status`: Optional status filter

---

## 8. AI/GIS Spatial Analysis Adapters

### `GET /api/v1/analysis/adapters`
Returns status, version, and capabilities of all registered AI/GIS analysis adapters.

### `POST /api/v1/analysis/dsm-dem-height`
Calculates normalized Digital Surface Model ($n\text{DSM} = \text{DSM} - \text{DEM}$) building height.
- **Request Body**:
  ```json
  {
    "dsm_height": 588.0,
    "dem_height": 560.0
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "derived_height": 28.0,
    "confidence": 0.92,
    "algorithm": "dsm_dem_difference_v1"
  }
  ```

### `POST /api/v1/analysis/estimate-floors`
Estimates floor count and vertical 3D intervals $[z_{\min}, z_{\max}]$ from height and usage heuristic.
- **Request Body**:
  ```json
  {
    "height_m": 28.0,
    "use_type": "commercial",
    "base_elevation_m": 560.0
  }
  ```

### `POST /api/v1/properties/{id}/analyze`
Runs the complete AI analysis pipeline on a property record and attaches derived observations.
- **Status Gating**: Updates property status to `DERIVED` or `INFERRED`, **never** `VERIFIED`.

---

## 9. Legal & Land Registry Linkage

### `POST /api/v1/legal/records`
Links a spatial `PropertyObject` to external land registry deed titles.
- **Access**: **Verifying Officer, Admin**
- **Request Body**:
  ```json
  {
    "property_object_id": "7b0b9794-06da-4d76-96b6-3a78f24b277d",
    "ulpin": "INMH0234567",
    "owner_party_id": "IN-MAH-REG-2021-998812-P",
    "registration_number": "MH-PUN-HAV-2021/008892",
    "registration_date": "2021-06-18T11:30:00Z",
    "rights_type": "freehold",
    "encumbrances": [
      {
        "type": "mortgage",
        "institution": "State Bank of India",
        "amount_inr": 25000000,
        "status": "ACTIVE"
      }
    ],
    "source_system": "MAHARASHTRA_IGR_DEED_REGISTRY"
  }
  ```

### `GET /api/v1/legal/records`
Lists linked legal records with **automated field-level PII masking**:
- **Officer/Admin**: Full unredacted `owner_party_id`.
- **Surveyor/Public**: `owner_party_id` is masked as `🔒 Protected by Cadastral Privacy RBAC`.

---

## 10. Compliance Audit & Bulk Data Export

### `GET /api/v1/audit/events`
Queries immutable forensic audit records.
- **Access**: **Verifying Officer, Admin**
- **Query Parameters**: `event_type`, `property_object_id`, `actor_id`, `start_date`, `end_date`

### `GET /api/v1/audit/summary`
Returns statistical aggregation of audit events across the platform.
- **Access**: **Verifying Officer, Admin**

### `GET /api/v1/export/cadastral`
Bulk export of cadastral and property records in JSON or CSV format.
- **Query Parameters**:
  - `format`: `json` | `csv`
  - `status`: Optional status filter
  - `redact_pii`: Defaults to `true`. When set to `false`, requires Officer role and mandatory `justification` query parameter.

---

## 11. System Observability & Health

### `GET /health`
Liveness probe returning operational state and process uptime.

### `GET /health/ready`
Readiness probe verifying spatial database connectivity and table migration status.

### `GET /metrics`
Prometheus standard metric output (`format=json` supported via query parameter).
- Metric items include: `http_requests_total`, `http_request_duration_seconds`, `properties_total_by_status`, `conflicts_open_total`.
