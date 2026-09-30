# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

## 1. Thông tin

- **Họ và tên:** Nguyen Hoang Cuong
- **MSSV:** 2A202602473
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/5cuong/K4-L3B-Day13-NguyenHoangCuong-2A202602473-Monitoring-LLMOps; commit SHA là HEAD của nhánh `main` sau khi push.
- **Challenge ID chính thức:** `day13-k4-l3b-monitoring-llmops-v1` (K4, `rag_slow`).
- **Project Langfuse:** `day13-k4-l3b-2A202602473`

## 2. Evidence

| Nội dung | Tệp |
|---|---|
| CP0 environment | [00-cp0-environment.txt](evidence/00-cp0-environment.txt) |
| Pytest cuối | [01-pytest.txt](evidence/01-pytest.txt) |
| Log validator | [02-validate-logs.txt](evidence/02-validate-logs.txt) |
| Dashboard validator | [03-validate-dashboard.txt](evidence/03-validate-dashboard.txt) |
| Structured log và response headers | [04-structured-log.png](evidence/04-structured-log.png), [text details](evidence/04-structured-log.txt) |
| PII redaction | [05-pii-redaction.png](evidence/05-pii-redaction.png), [text details](evidence/05-pii-redaction.txt) |
| Valid/invalid request ID live smoke | [32-request-id-smoke.txt](evidence/32-request-id-smoke.txt) |
| Trace list | [06-trace-list.txt](evidence/06-trace-list.txt) |
| Langfuse trace list UI | [screenlangfuse.png](evidence/screenlangfuse.png) |
| Trace waterfall | [07-trace-waterfall.txt](evidence/07-trace-waterfall.txt) |
| Trace metadata và token/cost | [08-trace-metadata.txt](evidence/08-trace-metadata.txt) |
| Prompt versions | [09-prompt-versions.txt](evidence/09-prompt-versions.txt) |
| Promote và rollback | [10-prompt-rollback.txt](evidence/10-prompt-rollback.txt) |
| Dashboard runtime 6 panel | [11-dashboard-overview.png](evidence/11-dashboard-overview.png), [HTML snapshot](evidence/11-dashboard-overview.html), [runtime summary](evidence/31-dashboard-runtime.txt) |
| CP3 practice metric/log/trace | [12-practice-metric.txt](evidence/12-practice-metric.txt), [13-practice-log.txt](evidence/13-practice-log.txt), [14-practice-trace.txt](evidence/14-practice-trace.txt) |
| CP3 official inject/load/disable | [15-challenge-incident-enable.txt](evidence/15-challenge-incident-enable.txt), [16-challenge-load-test.txt](evidence/16-challenge-load-test.txt), [17-challenge-incident-disable.txt](evidence/17-challenge-incident-disable.txt) |
| CP3 official metric/log/trace | [18-challenge-metric.txt](evidence/18-challenge-metric.txt), [19-challenge-log.txt](evidence/19-challenge-log.txt), [20-challenge-trace.txt](evidence/20-challenge-trace.txt) |

## 3. Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| CP0 Python / dependencies | Python 3.13.13; FastAPI 0.118.0; structlog 25.4.0; Langfuse 4.15.6; PyYAML 6.0.3 |
| `validate_logs.py` | 100/100; 206 log rows; 102 correlation IDs; 0 PII hit |
| `validate_dashboard.py` | Hợp lệ 6/6 panel |
| pytest | 28 passed |
| Langfuse | 33 complete trees trong 100 observation gần nhất; 0 nonempty raw input/output; CP3 correlation evidence được lưu riêng |
| PII | 0 hit trong log; test email, điện thoại VN, CCCD, thẻ và scrub event |
| CP2 clean dashboard workload | 102/102 response; 11 minute buckets; P50 152 ms, P95 155 ms, P99 1444 ms, max 1762 ms; TTFT P95 51 ms; errors 0; retrieval success 100% |
| Baseline sạch trước CP3 practice | 21/21 response; P50 153 ms, P95 2267 ms, P99 3225 ms, max 3464 ms; TTFT P95 50 ms; 20/21 dưới 3 giây; retrieval success 100% |
| CP3 practice `tool_fail` | 10/10 lỗi request, retrieval success 0/10; metric, log và trace dùng cùng correlation ID |

Log baseline CP0 đã được chuyển ra ngoài repository thành `../logs-cp0-baseline.jsonl`; `data/logs.jsonl` hiện tại là log mới đã scrub và bị Git ignore.

## 4. CP1 — Structured logging và PII

Middleware xóa context structlog cũ đầu mỗi request, nhận `x-request-id` an toàn hoặc tạo `req-<8 ký tự hex>`, bind correlation ID và trả `x-request-id` cùng `x-response-time-ms`. `app.main` bind `user_id_hash`, `session_id`, `feature`, `model`, `env` trước `request_received`. PII scrubber xử lý event đệ quy trước khi log được ghi/render. Các pattern gồm email, điện thoại Việt Nam, CCCD 12 chữ số và số thẻ 13–19 chữ số; tests có mẫu có dấu cách/gạch nối cho thẻ.

Đã gửi request có email, số điện thoại, CCCD và thẻ giả lập; log chỉ giữ dấu redaction. `x-request-id` do client gửi được giữ nguyên nếu an toàn; ID do server sinh đúng format. Chi tiết an toàn tại [04](evidence/04-structured-log.txt) và [05](evidence/05-pii-redaction.txt).

## 5. CP2 — Trace, prompt, dashboard và alerts

Trace Langfuse có `day13-agent-request` → `lab-agent-run` → child `retrieval` và `generation`. Correlation ID được đưa vào metadata; generation ghi model, usage input/output, cost và đối tượng prompt được quản lý. Capture input/output bị tắt để không gửi câu hỏi hay câu trả lời thô.

Prompt `day13-chat` là Text prompt với ba biến `feature`, `docs`, `message`. Version 1 dùng label `baseline` và `production`, version 2 thêm chỉ dẫn trả lời ngắn gọn và dùng `candidate`. Đã kiểm tra baseline v1 rồi candidate v2 bằng cùng input; sau đó promote `production` sang v2 và rollback về v1. Traces đối chiếu:

- v1 baseline: `26305b25452288d9d7bb8f5e5db3866a`, correlation `req-c8034ec7`, 44 input / 33 output tokens.
- v2 candidate: `e1e3abe6d1cdfc7d0cc8de427039e665`, correlation `req-240f7dfe`, 50 input / 33 output tokens.
- sau rollback production v1: `00caa89a0f1c3e7dea2cacd3276e8b1b`, correlation `req-ffc1fffd`.

Dashboard đọc `data/logs.jsonl` và có sáu panel latency, traffic, errors/retrieval, cost, tokens, quality. Mỗi panel có đơn vị, cửa sổ 60 phút, threshold; trang refresh mỗi 30 giây. Retrieval success tính mọi event có boolean `tool_success`, gồm `response_sent` và `request_failed`. Runtime snapshot nằm trong [11-dashboard-overview.html](evidence/11-dashboard-overview.html); contract đạt 6/6.

SLO là 99.5% response trong 3.5 giây ở cửa sổ 28 ngày. Ngưỡng 3.5 giây bao phủ 21/21 response trong baseline nhỏ; P95 là 2267 ms và P99 là 3225 ms. Đường 3 giây trên dashboard/alert là ngưỡng cảnh báo sớm. Error budget 0.5%; với 10,000 request cho phép tối đa 50 bad request. Baseline practice không đại diện cho kỳ SLO 28 ngày. Ba alert symptom-based và Metrics → Logs → Traces runbook có tại [config/alert_rules.yaml](../config/alert_rules.yaml), [docs/alerts.md](../docs/alerts.md).

## 6. CP3 — Điều tra incident

### Practice đã chạy

Để kiểm tra quy trình, đã chạy riêng incident practice `tool_fail`, concurrency 5, 10 request. Tất cả 10 request lỗi retrieval. Log `request_received`/`request_failed`, metric 100% error rate và trace `8f59f5db0d91fcfbd4448c8712bafb08` cùng trỏ tới correlation `req-715019ff`; root `lab-agent-run` và child `retrieval` báo `ERROR` với trạng thái `Vector store timeout`. Practice đã disable sau khi đo; challenge K4 chính thức được chạy ở phần tiếp theo.

Root cause trong practice: vector store timeout ở retrieval. Fix action thực hành: khôi phục/kiểm tra vector store và retry workload sau khi health tốt; preventive measure: cảnh báo retrieval success/error rate, runbook metrics → logs → trace và kiểm tra timeout/dependency trước khi retry.

### Challenge chính thức

Đã chạy challenge K4 `day13-k4-l3b-monitoring-llmops-v1` (`rag_slow`, feature `monitoring`, threshold 2000 ms), 5 request concurrency 5. Từ log, app latency là 2653–2656 ms; cả 5/5 vượt ngưỡng challenge. Error rate là 0%, retrieval success 5/5; retrieval span mất 2.500–2.502 s, trong khi generation chỉ 0.152–0.153 s. Metric, log và trace cùng khớp correlation ID `req-38186be0`; trace `c0472a2ba3b5058d902f17251432d7fe` cho thấy child `retrieval` chậm 2.5 s trước generation. Source `app/mock_rag.py` xác nhận incident `rag_slow` chèn `time.sleep(2.5)` vào retrieval.

Load test ghi wall time client 7.99–13.32 s dưới concurrency; đây là thời gian phía client, còn SLI challenge dùng `latency_ms` từ response log. Sau khi thu evidence, incident được disable và health báo cả ba incident đều tắt. Vì đây là fault injection trong mock, mitigation là tắt incident/khôi phục retrieval; với dependency thật cần kiểm tra latency vector store, timeout, cache và concurrency. Preventive measure: alert P95 theo challenge threshold, đo span retrieval riêng và chạy lại workload sau recovery.

## 7. Ghi chú nộp bài

- Trace tree, metadata, prompt version và promote/rollback có bằng chứng text đã lọc từ API Langfuse; ảnh UI trace list và dashboard runtime cũng được lưu. Trạng thái label production sau promote/rollback nằm trong [10-prompt-rollback.txt](evidence/10-prompt-rollback.txt).
