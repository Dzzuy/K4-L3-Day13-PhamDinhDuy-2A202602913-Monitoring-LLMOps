# Alert runbooks

These are alert definitions and operator instructions. This lab does not include a Slack delivery service; the configured channel identifies where an operator would route the alert. Evaluate conditions only when the minimum request count in `config/alert_rules.yaml` is met.

## Alert 1 — high response latency

- Severity: warning; duration: 5 minutes; owner: service-operator; Slack: `#day13-llmops-alerts`.
- Symptom: P95 response latency exceeds 3000 ms. Related SLO: `fast_successful_requests`.
- Metrics: confirm the time window, P95/P99, TTFT, traffic, and whether errors also rose.
- Logs: filter `response_sent` for high `latency_ms` and select a `correlation_id`.
- Traces: find that ID, compare retrieval and generation spans, then name the dominant duration.
- Mitigation: reduce concurrency or disable a practice incident; if retrieval is slow, inspect the retriever and its timeout before changing generation settings.
- Verification: rerun the same workload, check P95 below 3000 ms and confirm a new trace shows the affected span recovered.

## Alert 2 — high request failure rate

- Severity: critical; duration: 5 minutes; owner: service-operator; Slack: `#day13-llmops-alerts`.
- Symptom: more than 2% of requests fail. Related SLO: `fast_successful_requests`.
- Metrics: check error rate, error breakdown, traffic, and retrieval success.
- Logs: filter `request_failed` by time, inspect `error_type`, `tool_success`, and a representative `correlation_id`.
- Traces: inspect the matching retrieval/generation observation and its error status.
- Mitigation: disable the practice fault, restore the failing dependency, or use a controlled fallback if the product contract permits it.
- Verification: repeat the workload, verify errors fall below 2%, and inspect a successful trace.

## Alert 3 — high cost per request

- Severity: warning; duration: 10 minutes; owner: service-operator; Slack: `#day13-llmops-alerts`.
- Symptom: average successful request cost exceeds 0.01 USD, roughly 4.6 times the measured 10-request local baseline of 0.0021534 USD/request. Related guardrail: daily cost at most 2.5 USD.
- Metrics: compare cost/request, total cost, traffic, and input/output token totals.
- Logs: filter `response_sent` for high `cost_usd` and `tokens_out`, then select a `correlation_id`.
- Traces: inspect the matching generation usage and prompt version; check whether output tokens or model changed.
- Mitigation: disable a practice cost spike, restore the prior prompt version if it caused longer output, or lower output limits after checking answer quality.
- Verification: rerun the same input set and compare cost/request and quality to the baseline.
