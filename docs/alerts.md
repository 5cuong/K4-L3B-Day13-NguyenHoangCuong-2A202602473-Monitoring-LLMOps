# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `fast_successful_requests`, ngưỡng latency 3,000 ms
- Điều kiện và thời gian duy trì: P95 của `response_sent.latency_ms` > 3,000 ms liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời đến chậm và có thể vượt mục tiêu dịch vụ.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** xem P50/P95/P99 và TTFT trong dashboard 60 phút; xác định lúc P95 vượt 3,000 ms.
  2. **Logs:** lọc `response_sent` theo khoảng thời gian, sắp xếp `latency_ms` giảm dần và ghi lại `correlation_id`, `feature`, `model`.
  3. **Traces:** mở trace cùng `correlation_id`, so sánh thời lượng `retrieval` và `generation` để tìm bước chậm.
- Mitigation tạm thời: rollback prompt `production` về version ổn định; nếu retrieval là bước chậm, tắt practice incident/khôi phục cấu hình retrieval rồi theo dõi P95.
- Owner: `student-2A202602473`

## Alert 2

- Tên: `ElevatedErrorRate`
- Severity: `critical`
- Duration: `2m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: error rate tối đa 2%.
- Điều kiện và thời gian duy trì: `request_failed / request_received` > 2% trong 2 phút.
- Ảnh hưởng tới người dùng: một phần người dùng không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** xác nhận error rate, request volume và retrieval success trong cùng cửa sổ hai phút.
  2. **Logs:** nhóm `request_failed` theo `error_type`, kiểm tra `tool_success` và lấy một `correlation_id` lỗi.
  3. **Traces:** mở trace có cùng `correlation_id`; tìm observation có trạng thái lỗi và đối chiếu metadata `feature`, `model`, prompt version.
- Mitigation tạm thời: nếu retrieval timeout/fail, khôi phục dịch vụ hoặc tắt incident practice; nếu lỗi gắn với prompt mới, rollback label `production` rồi xác nhận error rate giảm.
- Owner: `student-2A202602473`

## Alert 3

- Tên: `DegradedAnswerQuality`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: quality proxy trung bình ≥ 0.75; retrieval success ≥ 90%.
- Điều kiện và thời gian duy trì: quality trung bình < 0.75 **hoặc** retrieval success < 90% liên tục 10 phút.
- Ảnh hưởng tới người dùng: câu trả lời có thể thiếu ngữ cảnh hoặc không đáp ứng yêu cầu.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** kiểm tra quality score và retrieval success theo phút; xác định chỉ số nào giảm trước.
  2. **Logs:** lọc `response_sent`/`request_failed` có `tool_success`, rồi đọc `quality_score`, `tool_name`, `error_type` và `correlation_id`.
  3. **Traces:** mở trace cùng `correlation_id`, kiểm tra kết quả retrieval và prompt version của generation; không đưa raw input/output vào trace.
- Mitigation tạm thời: rollback prompt nếu regression bắt đầu sau promotion; nếu retrieval success giảm, phục hồi nguồn tài liệu hoặc tắt practice failure rồi chạy lại workload xác nhận.
- Owner: `student-2A202602473`
