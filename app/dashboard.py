from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from .metrics import percentile


def load_recent_logs(path: Path, *, now: datetime | None = None) -> list[dict[str, Any]]:
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(minutes=60)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
            continue
        if cutoff <= timestamp <= current and isinstance(record, dict):
            records.append(record)
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    requests = [record for record in records if record.get("event") == "request_received"]
    responses = [record for record in records if record.get("event") == "response_sent"]
    failures = [record for record in records if record.get("event") == "request_failed"]
    numeric = lambda key: [float(row[key]) for row in responses if isinstance(row.get(key), (int, float))]
    latencies = numeric("latency_ms")
    ttfts = numeric("ttft_ms")
    costs = numeric("cost_usd")
    qualities = numeric("quality_score")
    outcomes = [row.get("tool_success") for row in responses + failures if isinstance(row.get("tool_success"), bool)]
    start = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=59)
    minutes = [(start + timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M") for index in range(60)]
    buckets: dict[str, list[dict[str, Any]]] = {minute: [] for minute in minutes}
    for row in records:
        minute = str(row.get("ts", ""))[:16]
        if minute in buckets:
            buckets[minute].append(row)

    def minute_series(kind: str) -> list[float]:
        values: list[float] = []
        for minute in minutes:
            rows = buckets[minute]
            received = [row for row in rows if row.get("event") == "request_received"]
            sent = [row for row in rows if row.get("event") == "response_sent"]
            failed = [row for row in rows if row.get("event") == "request_failed"]
            if kind == "traffic":
                values.append(float(len(received)))
            elif kind == "latency":
                values.append(percentile([float(row["latency_ms"]) for row in sent if isinstance(row.get("latency_ms"), (int, float))], 95))
            elif kind == "errors":
                values.append(len(failed) / len(received) * 100 if received else 0.0)
            elif kind == "cost":
                values.append(sum(float(row.get("cost_usd") or 0) for row in sent))
            elif kind == "tokens":
                values.append(sum(float(row.get("tokens_in") or 0) + float(row.get("tokens_out") or 0) for row in sent))
            else:
                quality = [float(row["quality_score"]) for row in sent if isinstance(row.get("quality_score"), (int, float))]
                values.append(mean(quality) if quality else 0.0)
        return values

    return {
        "requests": len(requests),
        "rate_per_minute": len(requests) / 60,
        "latency_p50": percentile(latencies, 50) if latencies else None,
        "latency_p95": percentile(latencies, 95) if latencies else None,
        "latency_p99": percentile(latencies, 99) if latencies else None,
        "ttft_p95": percentile(ttfts, 95) if ttfts else None,
        "error_rate_pct": len(failures) / len(requests) * 100 if requests else None,
        "errors": dict(Counter(row.get("error_type") or "unknown" for row in failures)),
        "retrieval_success_pct": outcomes.count(True) / len(outcomes) * 100 if outcomes else None,
        "cost_total": sum(costs),
        "cost_per_minute": sum(costs) / 60,
        "tokens_in": sum(numeric("tokens_in")),
        "tokens_out": sum(numeric("tokens_out")),
        "quality_avg": mean(qualities) if qualities else None,
        "series": {kind: minute_series(kind) for kind in ("latency", "traffic", "errors", "cost", "tokens", "quality")},
    }


def render_dashboard(summary: dict[str, Any], config_path: Path) -> str:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["dashboard"]
    panels = {panel["id"]: panel for panel in config["panels"]}

    def show(value: float | None, unit: str = "", digits: int = 1) -> str:
        return "No data" if value is None else f"{value:,.{digits}f}{unit}"

    content = {
        "latency": [
            ("P50", show(summary["latency_p50"], " ms")),
            ("P95", show(summary["latency_p95"], " ms")),
            ("P99", show(summary["latency_p99"], " ms")),
            ("TTFT P95", show(summary["ttft_p95"], " ms")),
        ],
        "traffic": [("Requests", str(summary["requests"])),
                    ("Rate", show(summary["rate_per_minute"], " req/min", 2))],
        "errors": [("Error rate", show(summary["error_rate_pct"], "%")),
                   ("Retrieval success", show(summary["retrieval_success_pct"], "%")),
                   ("Breakdown", ", ".join(f"{key}: {count}" for key, count in summary["errors"].items()) or "None")],
        "cost": [("Total", show(summary["cost_total"], " USD", 6)),
                 ("Per minute", show(summary["cost_per_minute"], " USD/min", 6))],
        "tokens": [("Input", str(int(summary["tokens_in"]))),
                   ("Output", str(int(summary["tokens_out"])))],
        "quality": [("Mean score", show(summary["quality_avg"], " / 1", 2))],
    }
    cards = []

    def sparkline(values: list[float], has_requests: bool) -> str:
        ceiling = max(values, default=0.0)
        if ceiling <= 0 and not has_requests:
            return "<p class='empty-chart'>No events in this window</p>"
        points = " ".join(
            f"{index * 300 / 59:.1f},{80 - value * 68 / ceiling:.1f}" if ceiling > 0
            else f"{index * 300 / 59:.1f},80"
            for index, value in enumerate(values)
        )
        return ("<svg viewBox='0 0 300 84' role='img' aria-label='Minute-by-minute trend for the last 60 minutes'>"
                "<line x1='0' y1='80' x2='300' y2='80' stroke='#dce4ef'/>"
                f"<polyline fill='none' stroke='#3769bf' stroke-width='2' points='{points}'/>"
                "</svg>")

    for panel_id in ("latency", "traffic", "errors", "cost", "tokens", "quality"):
        panel = panels[panel_id]
        threshold = panel["threshold"]
        rows = "".join(
            f"<div class='measure'><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>"
            for label, value in content[panel_id]
        )
        cards.append(
            f"<section class='panel'><h2>{html.escape(panel['title'])}</h2>{rows}"
            f"{sparkline(summary['series'][panel_id], summary['requests'] > 0)}"
            f"<p class='threshold'>Threshold: {html.escape(str(threshold['aggregation']))} "
            f"{html.escape(str(threshold['operator']))} {html.escape(str(threshold['value']))} "
            f"{html.escape(panel['unit'])}</p></section>"
        )
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta http-equiv='refresh' content='30'><meta name='viewport' content='width=device-width'>"
            "<title>Day 13 Monitoring Dashboard</title><style>"
            "body{font-family:system-ui,sans-serif;background:#f3f6fb;color:#15233b;margin:0;padding:28px}"
            "main{max-width:1180px;margin:auto}header{margin-bottom:24px}h1{margin:0 0 8px}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}"
            ".panel{background:white;border:1px solid #dce4ef;border-radius:12px;padding:20px;box-shadow:0 2px 8px #19355c0a}"
            "h2{font-size:1.1rem;margin:0 0 16px}.measure{display:flex;justify-content:space-between;gap:16px;"
            "border-bottom:1px solid #edf0f5;padding:9px 0}.measure strong{text-align:right}"
            ".threshold{font-size:.84rem;color:#54647a;margin:16px 0 0}"
            "svg{display:block;width:100%;height:84px;margin-top:14px}.empty-chart{color:#697a91;font-size:.84rem}"
            "</style></head><body><main><header><h1>Monitoring &amp; LLMOps</h1>"
            "<p>Source: data/logs.jsonl · Last 60 minutes · Refresh every 30 seconds · All values from runtime logs</p>"
            "</header><div class='grid'>" + "".join(cards) + "</div></main></body></html>")
