# Hướng dẫn quy trình xử lý sự cố khi vùng chính ngắt kết nối

Tài liệu hướng dẫn các bước xử lý sự cố để người vận hành có thể thực hiện dễ dàng.

| STT | Bước thực hiện | Lệnh chạy | Dấu hiệu hoàn thành | Người thực hiện |
|---|---|---|---|---|
| 1 | Xác nhận sự cố | `curl localhost:8001/readyz` | Trả về lỗi kết nối hoặc mã lỗi không phải 200 | Kỹ sư trực ca |
| 2 | Mở sự cố và ghi nhận thời gian rto | `python3 dr/runbook.py --primary a --target b --backend fs` | Ghi nhận mốc thời gian thông báo trong file log runbook | Trưởng nhóm sự cố |
| 3 | Khôi phục dữ liệu ở vùng phụ | `python3 state/snapshot.py get --region b --backend fs` | Trả về thông tin bản sao và các file dữ liệu có sẵn trên đĩa | Kỹ sư trực ca |
| 4 | Chuyển trạng thái máy chủ từ chờ sang hoạt động | `echo full > state/region-b/pool_state` | Cổng kiểm tra sức khỏe của vùng B trả về kết quả sẵn sàng | Kỹ sư trực ca |
| 5 | Chuyển cổng kết nối dịch vụ | `echo b > edge/active_region` | Đọc cổng kết nối thấy vùng hoạt động đã chuyển sang B | Kỹ sư hạ tầng |
| 6 | Kiểm tra tín hiệu hoạt động | `python3 -c "import httpx; print([httpx.get('http://127.0.0.1:8080/v1/infer').json() for _ in range(10)])"` | Các yêu cầu thử nghiệm đều thành công qua vùng B | Kỹ sư trực ca |
| 7 | Đo lại thời gian rto và viết báo cáo | `python3 tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300` | Kết quả đo trả về trạng thái hợp lệ và đạt yêu cầu | Trưởng nhóm sự cố |

**Quy trình chuyển traffic quay lại vùng A khi đã khôi phục:**
- Điều kiện chuyển lại: Chỉ thực hiện chuyển kết nối về vùng A khi vùng A đã hoạt động ổn định trở lại liên tục trong ít nhất 15 phút, dữ liệu được đồng bộ đầy đủ và các bài kiểm tra chạy thử đều thành công.
- Người quyết định: Quyết định chuyển lại phải do Trưởng nhóm sự cố phê duyệt trực tiếp để tránh việc chuyển qua chuyển lại liên tục làm gián đoạn hệ thống.
