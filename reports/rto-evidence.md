# Bảng chứng cứ chỉ số rto và rpo

Tất cả các con số trong bảng này đều được trỏ trực tiếp về dòng log thực tế.

## 1. Diễn tập 1 không có cơ chế khôi phục tự động

| Chỉ số | Giá trị | Cách đo | Bằng chứng log |
|---|---|---|---|
| Mốc thời gian sập mạng | 2026-08-25T09:48:33 | chaos kill | `chaos/chaos-events.jsonl:1` |
| Yêu cầu lỗi đầu tiên | +0.4s | dòng lỗi đầu tiên sau sự cố | `reports/drill-1-nodr.jsonl:28` |
| Yêu cầu thành công sau đó | không có | không có dòng thành công nào sau sự cố | `reports/drill-1-nodr.jsonl:35` |
| Chỉ số rto | NO_RECOVERY | đo từ công cụ | `reports/drill-1-nodr.jsonl:52` |

## 2. Diễn tập 2 có cơ chế khôi phục tự động

| Mốc thời gian | Số giây từ mốc sập | Cách đo | Bằng chứng log |
|---|---|---|---|
| Mốc sập mạng ban đầu | 0s | sự kiện kill | `chaos/chaos-events.jsonl:4` |
| Người dùng nhận lỗi đầu tiên | +0.4s | dòng lỗi đầu tiên | `reports/drill-2-withdr.jsonl:26` |
| Hệ thống phát hiện sập mạng | +15.1s | phát hiện vùng A sập | `reports/health-events.jsonl:3` |
| Khôi phục xong bản sao dữ liệu | +17.3s | bước khôi phục dữ liệu | `reports/failover-events.jsonl:2` |
| Vùng phụ sẵn sàng hoạt động | +17.3s | bước chờ sẵn sàng | `reports/failover-events.jsonl:4` |
| Chuyển cổng kết nối dịch vụ | +17.3s | bước đổi cổng kết nối | `reports/failover-events.jsonl:5` |
| Chỉ số rto đo được | +20.7s | dòng thành công đầu tiên ở vùng B | `reports/drill-2-withdr.jsonl:36` |

| Chỉ số đo | Kết quả đo được | Mục tiêu đề ra | Trạng thái đạt |
|---|---|---|---|
| Chỉ số rto dịch vụ | 20.7s | 300s | PASS |
| Chỉ số rpo cơ sở dữ liệu | 1.09s và 4 tài liệu | 300s | PASS |

## 3. Các thành phần đóng góp vào thời gian rto của em

| Thành phần | Số giây | Nguồn gốc con số | Cách tối ưu giảm thời gian |
|---|---|---|---|
| Thời gian phát hiện sự cố | 15.0s | thời gian kiểm tra nhân số lần thử trong `reports/health-events.jsonl:3` | Giảm thời gian giữa các lần kiểm tra |
| Thời gian nạp dữ liệu bản sao | 0.0s | từ bước khôi phục sang bước bật máy chủ trong `reports/failover-events.jsonl:2` | Tối ưu tốc độ đọc ghi đĩa |
| Thời gian làm nóng mô hình | 0.04s | thời gian chờ ở bước sẵn sàng trong `reports/failover-events.jsonl:4` | Duy trì trạng thái làm nóng sẵn |
| Thời gian lưu bộ nhớ đệm kết nối | 3.4s | thời gian thành công trừ thời gian đổi cổng trong `reports/drill-2-withdr.jsonl:36` | Giảm thời gian lưu bộ nhớ đệm |
