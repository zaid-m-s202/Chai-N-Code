# 3D Cadastral Intelligence System — Data Model & Schema Specification

This document details the entity-relationship architecture, field dictionary, spatial hierarchy, and lifecycle state machines of the 3D Cadastral Intelligence platform.

---

## 1. Entity-Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ INGESTION_JOBS : "uploads / triggers"
    USERS ||--o{ EVIDENCE : "operates / submits"
    USERS ||--o{ CHANGE_EVENTS : "acts upon"
    USERS ||--o{ CONFLICTS : "resolves / waives"
    USERS ||--o{ PROPERTY_RECORDS : "links / authorizes"

    INGESTION_JOBS ||--o{ EVIDENCE : "creates"
    INGESTION_JOBS ||--o{ SOURCE_OBSERVATIONS : "ingests"

    PROPERTY_OBJECTS ||--o{ PROPERTY_OBJECTS : "parent_id (hierarchy)"
    PROPERTY_OBJECTS ||--o{ PROPERTY_OBJECTS : "superseded_by (versioning)"
    PROPERTY_OBJECTS ||--o{ SOURCE_OBSERVATIONS : "observed attributes"
    PROPERTY_OBJECTS ||--o{ EVIDENCE : "provenance chain"
    PROPERTY_OBJECTS ||--o{ CONFLICTS : "violates / flags"
    PROPERTY_OBJECTS ||--o{ CHANGE_EVENTS : "history trail"
    PROPERTY_OBJECTS ||--o{ PROPERTY_RECORDS : "legal tenure title"

    PROPERTY_OBJECTS {
        uuid id PK
        string three_d_property_id UK "Unique 3D ID"
        string type "parcel | building | floor | unit"
        uuid parent_id FK
        geometry geometry "PostGIS Polygon/MultiPolygon (4326)"
        float z_min "Lower vertical bound (m)"
        float z_max "Upper vertical bound (m)"
        float confidence "0.0 to 1.0"
        string status "SYNTHETIC..VERIFIED"
        json attributes "Semantic attribute bag"
        uuid superseded_by FK
        datetime created_at
    }

    SOURCE_OBSERVATIONS {
        uuid id PK
        uuid property_object_id FK
        string attribute_name "height | floor_count | footprint"
        json observed_value "Observed metric / geometry"
        float source_confidence "Vendor confidence"
        string source_id "Sensor/system identifier"
        uuid ingestion_job_id FK
        datetime observed_at
        datetime created_at
    }

    EVIDENCE {
        uuid id PK
        uuid property_object_id FK
        string evidence_type "geojson | csv | geotiff | plan"
        string file_reference "S3 key or filesystem path"
        string file_hash "SHA-256 digest"
        string original_crs "EPSG:3857, etc."
        string source_system "Authority or sensor tag"
        uuid operator_id FK
        uuid ingestion_job_id FK
        datetime captured_at
        datetime created_at
    }

    CONFLICTS {
        uuid id PK
        uuid property_object_id FK
        string rule_code "VR-01 through VR-08"
        string severity "ERROR | WARNING"
        string status "OPEN | RESOLVED | WAIVED"
        text description "Violation diagnosis"
        uuid resolved_by FK
        datetime resolved_at
        datetime created_at
    }

    CHANGE_EVENTS {
        uuid id PK
        uuid property_object_id FK
        string event_type "created | verified | legal_linked | ..."
        json old_state "Previous state snapshot"
        json new_state "Updated state snapshot"
        uuid actor_id FK
        uuid evidence_id FK
        datetime created_at
    }

    PROPERTY_RECORDS {
        uuid id PK
        uuid property_object_id FK
        string three_d_property_id "Denormalized spatial ID"
        string ulpin "Bhu-Aadhaar ULPIN"
        string owner_party_id "Opaque protected identity"
        string registration_number "Deed registration no"
        datetime registration_date
        string rights_type "freehold | strata_title | ..."
        json encumbrances "Mortgages, liens, court stays"
        string linkage_status "LINKED | PENDING | DISPUTED | UNLINKED"
        string source_system "State Registry Name"
        uuid created_by FK
        datetime sync_time
        datetime created_at
    }
```

---

## 2. Spatial Hierarchy & 3D Identifier Specification

Every spatial object is identified by an immutable `three_d_property_id` conforming to the national cadastre pattern:

$$\mathbf{\{ULPIN\}-\{building\_seq:03d\}-F\{floor\_seq:02d\}-U\{unit\_seq:03d\}}$$

| Hierarchy Level | `type` | Sequence Formatting | Example Identifier | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Parcel (Root)** | `parcel` | `B000-F00-U000` | `INMH0234567-B000-F00-U000` | Statutory cadastral land parcel rooted by ULPIN |
| **Building** | `building` | `B{seq:03d}-F00-U000` | `INMH0234567-B001-F00-U000` | Physical above/below ground building footprint |
| **Floor** | `floor` | `B{seq:03d}-F{seq:02d}-U000` | `INMH0234567-B001-F04-U000` | Horizontal slice at designated vertical interval $[z_{\min}, z_{\max}]$ |
| **Unit** | `unit` | `B{seq:03d}-F{seq:02d}-U{seq:03d}` | `INMH0234567-B001-F04-U402` | Individual apartment, office suite, or commercial space |

### Rules:
1. **Vertical Bounds**: Heights and elevations are represented in standard SI meters (`EPSG:4326` longitude/latitude + ellipsoidal/orthometric elevation $Z$).
2. **Monotonicity**: Floors within a building must maintain non-overlapping, monotonically increasing vertical bounds:
   $$z_{\min}(\text{Floor } k+1) \ge z_{\max}(\text{Floor } k) - \epsilon_{\text{tolerance}}$$
3. **Immutability**: A 3D Property ID identifies the space permanently. If a unit is subdivided, the original unit is superseded and new child unit sequences are assigned.

---

## 3. Status Lifecycle State Machine

The verification status follows an explicit, one-way progression:

$$\text{SYNTHETIC} \longrightarrow \text{INFERRED} \longrightarrow \text{DERIVED} \longrightarrow \text{PROVISIONAL} \overset{\text{Statutory Officer Sign-Off}}{\underset{\text{Rule VR-09 Enforced}}{\longrightarrow}} \text{VERIFIED}$$

| Status | Description | Confidence Baseline | Gating Criteria |
| :--- | :--- | :--- | :--- |
| `SYNTHETIC` | Seeded, synthetic, or preliminary placeholder boundary. | $0.0 - 0.4$ | Awaiting real sensor observations. |
| `INFERRED` | Preliminary shape detected via AI or remote sensing (e.g. raw footprint polygon). | $0.4 - 0.6$ | Unchecked by field survey. |
| `DERIVED` | Enriched via algorithmic pipeline (e.g., $n\text{DSM}$ building height or floor slicing). | $0.6 - 0.8$ | Algorithmic derivation attached. |
| `PROVISIONAL` | Normalized and ready for administrative review. Listed in the **Officer Verification Queue**. | $0.7 - 0.95$ | Ingestion and normalization complete. |
| `VERIFIED` | Statutory government sign-off. | **$1.0$** | **Rule VR-09**: No open conflicts; authorized officer signature. |

---

## 4. Separation of Concerns & Privacy Firewall

The schema maintains strict boundary isolation between physical space, legal tenure, and private personal data:

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. SPATIAL CADASTRE (Public Domain)                         │
│    three_d_property_id, geometry, z_min, z_max, type        │
│    --> Identifies WHERE and WHAT the space is.              │
└──────────────────────────────┬──────────────────────────────┘
                               │ Linked by three_d_property_id
┌──────────────────────────────▼──────────────────────────────┐
│ 2. LEGAL TENURE (Authoritative Registry)                    │
│    ulpin, registration_number, rights_type, encumbrances    │
│    --> Identifies LEGAL DEED and STATUTORY RIGHTS.          │
└──────────────────────────────┬──────────────────────────────┘
                               │ Strict RBAC / Encryption
┌──────────────────────────────▼──────────────────────────────┐
│ 3. OWNER IDENTITY (Protected PII)                           │
│    owner_party_id (Opaque Reference)                        │
│    --> MASKED FOR PUBLIC & FIELD SURVEYORS                  │
│    --> ACCESSIBLE ONLY TO VERIFYING OFFICERS & ADMINS       │
└─────────────────────────────────────────────────────────────┘
```
