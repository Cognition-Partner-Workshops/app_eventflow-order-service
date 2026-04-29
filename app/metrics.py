"""In-memory metrics collector exposed via GET /metrics."""

import threading
import time

from fastapi import APIRouter

router = APIRouter(tags=["metrics"])

_start_time = time.monotonic()


class MetricsCollector:
    """Thread-safe in-memory metrics store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._http_requests: dict[str, int] = {}
        self._http_durations: list[float] = []
        self._orders_created: int = 0
        self._events_published: dict[str, int] = {"success": 0, "failure": 0}

    def record_request(
        self, method: str, path: str, status_code: int, duration_seconds: float
    ) -> None:
        key = f"{method}|{path}|{status_code}"
        with self._lock:
            self._http_requests[key] = self._http_requests.get(key, 0) + 1
            self._http_durations.append(duration_seconds)

    def record_order_created(self) -> None:
        with self._lock:
            self._orders_created += 1

    def record_event_published(self, *, success: bool) -> None:
        label = "success" if success else "failure"
        with self._lock:
            self._events_published[label] = self._events_published.get(label, 0) + 1

    def snapshot(self) -> dict:
        with self._lock:
            durations = list(self._http_durations)
            requests_by_key = dict(self._http_requests)
            orders = self._orders_created
            events = dict(self._events_published)

        http_requests_total: list[dict] = []
        for key, count in requests_by_key.items():
            method, path, status = key.split("|", 2)
            http_requests_total.append({
                "method": method,
                "path": path,
                "status_code": int(status),
                "count": count,
            })

        duration_stats: dict[str, float | None] = {
            "count": len(durations),
            "sum": round(sum(durations), 6) if durations else 0,
            "min": round(min(durations), 6) if durations else None,
            "max": round(max(durations), 6) if durations else None,
            "p50": None,
            "p95": None,
            "p99": None,
        }
        if durations:
            sorted_d = sorted(durations)
            duration_stats["p50"] = round(_percentile(sorted_d, 50), 6)
            duration_stats["p95"] = round(_percentile(sorted_d, 95), 6)
            duration_stats["p99"] = round(_percentile(sorted_d, 99), 6)

        return {
            "http_requests_total": http_requests_total,
            "http_request_duration_seconds": duration_stats,
            "orders_created_total": orders,
            "events_published_total": events,
            "service_uptime_seconds": round(time.monotonic() - _start_time, 2),
        }


def _percentile(sorted_data: list[float], pct: float) -> float:
    """Compute the p-th percentile from pre-sorted data."""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * (pct / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


metrics_collector: MetricsCollector | None = None


def init_metrics() -> None:
    """Initialise the global metrics collector."""
    global metrics_collector
    metrics_collector = MetricsCollector()


@router.get("/metrics", summary="Application metrics")
async def get_metrics() -> dict:
    """Return current application metrics as JSON."""
    if metrics_collector is None:
        return {"error": "metrics not enabled"}
    return metrics_collector.snapshot()
