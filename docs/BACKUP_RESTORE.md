# 3D Cadastral Intelligence & Land Administration System
## Enterprise Backup, Disaster Recovery & Restore Runbook

---

## 1. Architecture & Storage Overview

The 3D Cadastral platform utilizes **PostgreSQL 16 with PostGIS** for spatial and semantic storage, and **Redis 7** for transient caching and queue state. All spatial entities (`property_objects`), evidence provenance (`evidence`), sensor measurements (`source_observations`), topology conflicts (`conflicts`), legal linkages (`property_records`), and immutable audit histories (`change_events`) reside in PostgreSQL.

---

## 2. Automated Backup Strategy

### 2.1 Backup Cadence Matrix

| Backup Type | Frequency | Retention | Destination | Tool |
| :--- | :--- | :--- | :--- | :--- |
| **Full Database Snapshot** | Daily at 01:00 UTC | 30 Days (Daily), 1 Year (Monthly) | Encrypted S3 / Cloud Storage / Cold Storage | `pg_dump -Fc` |
| **Differential / WAL Archive** | Continuous (every 10 min) | 7 Days | Multi-region Cloud Storage | `pg_receivewal` / WAL-G |
| **Redis State Dump** | Every 6 hours | 3 Days | Local Disk / Volume | `BGSAVE` (`dump.rdb`) |

---

## 3. Step-by-Step Backup Procedures

### 3.1 Logical Backup (`pg_dump` Custom Format)

Execute a compressed, custom-format binary backup preserving all PostGIS spatial geometry types, indices, and sequences:

```bash
# Variables
export TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
export BACKUP_DIR="/var/backups/cadastre"
export DBNAME="cadastre_db"
export DBUSER="postgres"
export DBHOST="localhost"

mkdir -p ${BACKUP_DIR}

# Execute pg_dump with custom format (-Fc), verbose (-v), and blob support (-b)
pg_dump -h ${DBHOST} -U ${DBUSER} -Fc -b -v -f "${BACKUP_DIR}/cadastre_${TIMESTAMP}.dump" ${DBNAME}

# Generate SHA-256 integrity checksum
sha256sum "${BACKUP_DIR}/cadastre_${TIMESTAMP}.dump" > "${BACKUP_DIR}/cadastre_${TIMESTAMP}.dump.sha256"
```

### 3.2 Docker Containerized Backup

If running via `docker-compose.yml`:

```bash
# Execute dump directly from the postgis container
docker compose exec -T postgis pg_dump -U postgres -Fc cadastre_db > ./backups/cadastre_$(date +%Y%m%d_%H%M%S).dump
```

---

## 4. Step-by-Step Restore Procedures

### 4.1 Restoring to a Clean Database

```bash
# 1. Verify Checksum
sha256sum -c cadastre_20260907_010000.dump.sha256

# 2. Terminate existing connections (if restoring existing instance)
psql -h localhost -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'cadastre_db' AND pid <> pg_backend_pid();"

# 3. Drop and Recreate Database
dropdb -h localhost -U postgres --if-exists cadastre_db
createdb -h localhost -U postgres -O postgres cadastre_db

# 4. Enable PostGIS Spatial Extension
psql -h localhost -U postgres -d cadastre_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -h localhost -U postgres -d cadastre_db -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"

# 5. Restore using pg_restore with parallel jobs (-j 4)
pg_restore -h localhost -U postgres -d cadastre_db -v -j 4 --no-owner --no-privileges cadastre_20260907_010000.dump

# 6. Re-index and Analyze
psql -h localhost -U postgres -d cadastre_db -c "VACUUM ANALYZE;"
```

### 4.2 Restoring via Docker

```bash
# Recreate database and restore inside container
docker compose exec -T postgis dropdb -U postgres --if-exists cadastre_db
docker compose exec -T postgis createdb -U postgres cadastre_db
docker compose exec -T postgis psql -U postgres -d cadastre_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
cat ./backups/cadastre_backup.dump | docker compose exec -T postgis pg_restore -U postgres -d cadastre_db --no-owner
```

---

## 5. Post-Restore Verification Checklist

After restoring, run the automated system verification checks:

1. **Verify Database Connectivity & Health**:
   ```bash
   curl -s http://localhost:8000/health/ready
   # Expected: {"status":"ok","service":"3d-cadastral-api","database":"connected"}
   ```

2. **Verify Table Entity Counts**:
   ```sql
   SELECT 'property_objects' AS tbl, count(*) FROM property_objects
   UNION ALL
   SELECT 'property_records', count(*) FROM property_records
   UNION ALL
   SELECT 'change_events', count(*) FROM change_events
   UNION ALL
   SELECT 'conflicts', count(*) FROM conflicts;
   ```

3. **Verify Spatial Indices & SRID**:
   ```sql
   SELECT Find_SRID('public', 'property_objects', 'geometry');
   -- Expected: 4326
   ```

4. **Verify Audit Trail Integrity**:
   ```bash
   curl -s http://localhost:8000/metrics?format=json | grep database_entities
   ```

---

## 6. Point-in-Time Recovery (PITR) & High Availability

For production government infrastructure:
- **Primary-Replica Streaming Replication**: Standby read-replicas for read-heavy public cadastral queries.
- **WAL Archiving**: Continuous archiving of Write-Ahead Logs to object storage allows restoring the exact state of the cadastre down to the second prior to any incident or hardware failure.
