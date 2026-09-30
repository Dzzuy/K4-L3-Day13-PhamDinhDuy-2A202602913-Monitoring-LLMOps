from app.dashboard import render_dashboard, summarize


def test_dashboard_computes_values_from_log_events(tmp_path) -> None:
    rows = [
        {"event": "request_received"}, {"event": "request_received"},
        {"event": "response_sent", "latency_ms": 100, "ttft_ms": 50,
         "cost_usd": 0.001, "tokens_in": 20, "tokens_out": 10,
         "quality_score": 0.8, "tool_success": True},
        {"event": "request_failed", "error_type": "RuntimeError", "tool_success": False},
    ]
    result = summarize(rows)
    assert result["requests"] == 2
    assert result["error_rate_pct"] == 50
    assert result["retrieval_success_pct"] == 50
    assert result["tokens_in"] == 20
    assert result["cost_total"] == 0.001
    assert len(result["series"]["traffic"]) == 60


def test_dashboard_has_six_runtime_panels() -> None:
    from pathlib import Path
    config = Path(__file__).resolve().parents[1] / "config/dashboard.yaml"
    page = render_dashboard(summarize([]), config)
    assert page.count("class='panel'") == 6
    assert page.count("<svg") == 0
    assert "No data" in page
    assert "Last 60 minutes" in page
