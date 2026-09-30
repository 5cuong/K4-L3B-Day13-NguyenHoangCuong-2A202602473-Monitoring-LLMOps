# Evidence

Evidence text outputs are sanitized: no credentials or raw PII are included. The dashboard HTML is a runtime snapshot rendered from the current sanitized `data/logs.jsonl` and `config/dashboard.yaml`.

| File | Contents |
|---|---|
| `00-cp0-environment.txt` | Python/dependency versions, configured-key presence, API health; no secret values |
| `01-pytest.txt` | Final pytest result |
| `02-validate-logs.txt` | Log score and PII scan |
| `03-validate-dashboard.txt` | Dashboard contract result |
| `04-structured-log.png` and `.txt` | Sanitized request event, response headers, and text details |
| `05-pii-redaction.png` and `.txt` | Redaction checks for email, VN phone, CCCD, and card; raw examples omitted |
| `06-trace-list.txt`–`10-prompt-rollback.txt` | Langfuse trace tree, prompt versions, metadata, and rollback evidence; no raw input/output |
| `Screenshot 2026-09-30 122411.png` | Langfuse trace list UI showing the `lab-agent-run`, `retrieval`, and `generation` observation types |
| `11-dashboard-overview.png`, `11-dashboard-overview.html`, `31-dashboard-runtime.txt` | Six-panel dashboard runtime evidence; 60-minute range, 30-second refresh, clean load data |
| `12-practice-metric.txt`–`14-practice-trace.txt` | `tool_fail` practice investigation, clearly separated from official challenge |
| `15-challenge-incident-enable.txt`–`17-challenge-incident-disable.txt` | Official K4 challenge injection, load test, and recovery |
| `18-challenge-metric.txt`–`20-challenge-trace.txt` | Official challenge metric → sanitized log → correlated trace |
| `21-clean-load-test-01.txt`–`30-clean-load-test-10.txt` | Ten incident-free load-test batches spaced over about ten minutes |
| `32-request-id-smoke.txt` | Live API check of valid header preservation and invalid header replacement after restart |

Prompt version and label transitions are documented in the sanitized API evidence; no API keys or raw user inputs are included.
