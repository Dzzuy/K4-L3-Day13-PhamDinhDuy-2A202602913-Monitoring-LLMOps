from __future__ import annotations

from collections import Counter
from statistics import mean
from threading import Lock

_LOCK = Lock()

REQUEST_LATENCIES: list[int] = []
REQUEST_TTFT: list[int] = []
REQUEST_COSTS: list[float] = []
REQUEST_TOKENS_IN: list[int] = []
REQUEST_TOKENS_OUT: list[int] = []
ERRORS: Counter[str] = Counter()
TRAFFIC: int = 0
QUALITY_SCORES: list[float] = []


def record_request(
    latency_ms: int,
    ttft_ms: int,
    cost_usd: float,
    tokens_in: int,
    tokens_out: int,
    quality_score: float,
) -> None:
    global TRAFFIC
    with _LOCK:
        TRAFFIC += 1
        REQUEST_LATENCIES.append(latency_ms)
        REQUEST_TTFT.append(ttft_ms)
        REQUEST_COSTS.append(cost_usd)
        REQUEST_TOKENS_IN.append(tokens_in)
        REQUEST_TOKENS_OUT.append(tokens_out)
        QUALITY_SCORES.append(quality_score)



def record_error(error_type: str) -> None:
    with _LOCK:
        ERRORS[error_type] += 1



def percentile(values: list[int], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[idx])



def snapshot() -> dict:
    with _LOCK:
        traffic = TRAFFIC
        latencies = REQUEST_LATENCIES.copy()
        ttfts = REQUEST_TTFT.copy()
        costs = REQUEST_COSTS.copy()
        tokens_in = REQUEST_TOKENS_IN.copy()
        tokens_out = REQUEST_TOKENS_OUT.copy()
        errors = dict(ERRORS)
        qualities = QUALITY_SCORES.copy()
    return {
        "traffic": traffic,
        "latency_p50": percentile(latencies, 50),
        "latency_p95": percentile(latencies, 95),
        "latency_p99": percentile(latencies, 99),
        "ttft_p95": percentile(ttfts, 95),
        "avg_cost_usd": round(mean(costs), 4) if costs else 0.0,
        "total_cost_usd": round(sum(costs), 4),
        "tokens_in_total": sum(tokens_in),
        "tokens_out_total": sum(tokens_out),
        "error_breakdown": errors,
        "quality_avg": round(mean(qualities), 4) if qualities else 0.0,
    }
