# Báo cáo sự cố và học rút kinh nghiệm

Báo cáo phân tích sự cố hệ thống sau đợt diễn tập thảm họa.

## 1. Dòng thời gian diễn ra sự cố

| Thời gian ISO | Sự kiện xảy ra | Đường dẫn log |
|---|---|---|
| 2026-08-25T10:06:43 | Sự cố ngắt kết nối vùng A bắt đầu | `chaos/chaos-events.jsonl:4` |
| +0.4s | Người dùng nhận phản hồi lỗi đầu tiên | `reports/drill-2-withdr.jsonl:26` |
| +15.1s | Hệ thống giám sát phát hiện vùng A bị sập | `reports/health-events.jsonl:3` |
| +17.3s | Người vận hành xác nhận và kích hoạt chuyển vùng | `reports/failover-events.jsonl:5` |
| +20.7s | Xử lý xong và phục hồi request thành công ở vùng B | `reports/drill-2-withdr.jsonl:36` |

## 2. Kết quả chỉ số rto rpo và khoảng chênh lệch gap

- Chỉ số rto đạt 20.7s so với mục tiêu 300s, tạo ra gap khoảng chênh lệch là 279.3s đạt yêu cầu.
- Chỉ số rpo đạt 1.09s với 4 tài liệu bị thất thoát, tạo ra gap khoảng chênh lệch 298.91s nằm trong giới hạn an toàn.
- Phần tốn nhiều thời gian nhất là bước chờ hệ thống kiểm tra sức khỏe phát hiện sự cố mất khoảng 15 giây, vì em cần hệ thống xác nhận lỗi liên tiếp 3 lần để tránh chuyển vùng nhầm khi mạng chỉ bị lag nhẹ.

## 3. Phân tích nguyên nhân gốc rễ

1. Người dùng thấy lỗi là do em đã tiến hành ngắt kết nối mạng của vùng A trong lúc đang gửi yêu cầu.
2. Hệ thống mất 15 giây mới phát hiện vì em cài đặt kiểm tra 3 lần liên tiếp, mỗi lần cách nhau 5 giây để tránh báo động giả.
3. Vùng B lúc đầu chưa xử lý được yêu cầu vì đây là máy chủ dự phòng chưa nạp dữ liệu và trọng số mô hình.
4. Vùng B chạy lại bình thường là nhờ kịch bản tự động đã khôi phục bản lưu dữ liệu, làm nóng mô hình và đổi cổng kết nối.
5. Dữ liệu không bị mất toàn bộ vì tiến trình sao lưu đã tự động chụp bản sao liên tục trước đó.

## 4. Bảng công việc cần cải thiện action item

| STT | Công việc cải thiện action item | Người phụ trách | Hạn hoàn thành | Kết quả cải thiện |
|---|---|---|---|---|
| 1 | Tăng tần suất sao lưu dữ liệu sang máy chủ phụ | Nhóm dữ liệu | 2026-08-30 | Giảm thời gian mất dữ liệu xuống thấp hơn |
| 2 | Cải tiến cơ chế kiểm tra sức khỏe thông minh hơn | Nhóm vận hành | 2026-09-05 | Phát hiện sự cố nhanh hơn |

## 5. Trả lời các câu hỏi tổng kết

1. Khoảng thời gian chờ kiểm tra là 15 giây và phần này chiếm phần lớn tổng thời gian phục hồi rto của em.
2. Nếu em giảm thời gian kiểm tra xuống còn 1 giây thì thời gian rto sẽ nhanh hơn đáng kể, nhưng em sẽ phải đối mặt với rủi ro hệ thống bị nhầm lẫn và chuyển vùng qua lại liên tục khi mạng chỉ bị chập chập chờn.
3. Số lượng 4 tài liệu bị mất trong đợt thử nghiệm này là dữ liệu vừa được tải lên ngay trước lúc sập mạng nên chưa kịp chép sang vùng B và khách hàng chỉ cần gửi lại các yêu cầu vừa thực hiện ở vài giây cuối là xong.
