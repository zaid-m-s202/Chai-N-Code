"""Prometheus & In-Memory Observability Metrics (Phase 8).

Tracks HTTP telemetry, cadastral object counts, open conflicts, and
event-sourced change logs. Exposes both Prometheus-compatible text
and structured JSON summary formats.
"""

import time
from collections import defaultdict
from typing import Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.property_object import PropertyObject
from app.models.conflict import Conflict
from app.models.change_event import ChangeEvent
from app.models.ingestion_job import IngestionJob


class MetricsCollector:
    """Thread-safe metrics accumulator."""

    def __init__(self):
        self.start_time = time.time()
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.status_counts: Dict[int, int] = defaultdict(int)
        self.latency_sum_ms: float = 0.0
        self.latency_count: int = 0

    def increment_request(self, method: str, path: str):
        key = f"{method.upper()}:{path}"
        self.request_counts[key] += 1

    def record_response(self, method: str, path: str, status_code: int, duration_ms: float):
        self.status_counts[status_code] += 1
        self.latency_sum_ms += duration_ms
        self.latency_count += 1

    def get_system_counts(self, db: Session) -> Dict[str, Any]:
        """Aggregate current entity counts from the database."""
        try:
            # Properties by status
            prop_status_counts = (
                db.query(PropertyObject.status, func.count(PropertyObject.id))
                .filter(PropertyObject.superseded_by == None)  # active only
                .group_by(PropertyObject.status)
                .all()
            )
            status_map = {status: count for status, count in prop_status_counts}

            # Conflicts by status
            conflict_counts = (
                db.query(Conflict.status, func.count(Conflict.id))
                .group_by(Conflict.status)
                .all()
            )
            conflict_map = {status: count for status, count in conflict_counts}

            # Change events total
            total_change_events = db.query(func.count(ChangeEvent.id)).scalar() or 0

            # Ingestion jobs total
            total_jobs = db.query(func.count(IngestionJob.id)).scalar() or 0

            return {
                "properties_by_status": status_map,
                "conflicts_by_status": conflict_map,
                "total_change_events": total_change_events,
                "total_ingestion_jobs": total_jobs,
            }
        except Exception:
            return {
                "properties_by_status": {},
                "conflicts_by_status": {},
                "total_change_events": 0,
                "total_ingestion_jobs": 0,
            }

    def to_prometheus_text(self, db: Session) -> str:
        """Render metrics in standard Prometheus exposition format."""
        uptime = time.time() - self.start_time
        avg_latency = (self.latency_sum_ms / self.latency_count) if self.latency_count > 0 else 0.0
        sys_counts = self.get_system_counts(db)

        lines = [
            "# HELP cadastre_uptime_seconds Process uptime in seconds",
            "# TYPE cadastre_uptime_seconds gauge",
            f"cadastre_uptime_seconds {uptime:.2f}",
            "",
            "# HELP cadastre_http_requests_total Total HTTP requests processed",
            "# TYPE cadastre_http_requests_total counter",
        ]

        total_reqs = sum(self.request_counts.values())
        lines.append(f"cadastre_http_requests_total {total_reqs}")

        # Status code breakdowns
        lines.extend([
            "",
            "# HELP cadastre_http_responses_total Total HTTP responses by status code",
            "# TYPE cadastre_http_responses_total counter",
        ])
        for sc, cnt in sorted(self.status_counts.items()):
            lines.append(f'cadastre_http_responses_total{{code="{sc}"}} {cnt}')

        lines.extend([
            "",
            "# HELP cadastre_http_request_duration_ms_avg Average HTTP duration in milliseconds",
            "# TYPE cadastre_http_request_duration_ms_avg gauge",
            f"cadastre_http_request_duration_ms_avg {avg_latency:.2f}",
            "",
            "# HELP cadastre_properties_count Active 3D properties by status",
            "# TYPE cadastre_properties_count gauge",
        ])
        for st in ("SYNTHETIC", "INFERRED", "DERIVED", "PROVISIONAL", "VERIFIED"):
            val = sys_counts["properties_by_status"].get(st, 0)
            lines.append(f'cadastre_properties_count{{status="{st}"}} {val}')

        lines.extend([
            "",
            "# HELP cadastre_conflicts_count Active topology/boundary conflicts",
            "# TYPE cadastre_conflicts_count gauge",
        ])
        for c_st in ("OPEN", "RESOLVED", "WAIVED"):
            val = sys_counts["conflicts_by_status"].get(c_st, 0)
            lines.append(f'cadastre_conflicts_count{{status="{c_st}"}} {val}')

        lines.extend([
            "",
            "# HELP cadastre_audit_events_total Total change events recorded",
            "# TYPE cadastre_audit_events_total counter",
            f'cadastre_audit_events_total {sys_counts["total_change_events"]}',
            "",
            "# HELP cadastre_ingestion_jobs_total Total ingestion jobs processed",
            "# TYPE cadastre_ingestion_jobs_total counter",
            f'cadastre_ingestion_jobs_total {sys_counts["total_ingestion_jobs"]}',
        ])

        return "\n".join(lines) + "\n"

    def to_json_summary(self, db: Session) -> Dict[str, Any]:
        """Render JSON metrics summary."""
        uptime = time.time() - self.start_time
        avg_latency = (self.latency_sum_ms / self.latency_count) if self.latency_count > 0 else 0.0
        sys_counts = self.get_system_counts(db)

        return {
            "uptime_seconds": round(uptime, 2),
            "total_requests": sum(self.request_counts.values()),
            "status_codes": dict(self.status_counts),
            "avg_latency_ms": round(avg_latency, 2),
            "database_entities": sys_counts,
        }


metrics_collector = MetricsCollector()
