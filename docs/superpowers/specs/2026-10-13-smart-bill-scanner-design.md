# DontLift Smart Bill Scanner — thiết kế giai đoạn đầu

Ngày: 2026-10-13. Trạng thái: đề xuất cụ thể, chờ review trước triển khai.

## 1. Phạm vi và quyết định đề xuất

Xây baseline độc lập trong `ai-dontlift`, sau đó tích hợp mobile. Giai đoạn đầu hỗ trợ ảnh hóa đơn in tiếng Việt, một hóa đơn/ảnh, VND. Hóa đơn viết tay, nhiều trang, nhiều người nhận tiền và kết hợp món + phạt nằm ngoài baseline.

Hai chế độ độc lập: PENALTY dùng hợp đồng DontLift hiện có; ITEMIZED chia theo món. Scanner có thể cung cấp tổng đã xác nhận cho PENALTY. ITEMIZED không áp dụng tỷ trọng 40/60 và không thay đổi Penalty Score. Chỉ Host xác nhận hóa đơn/kế hoạch và xuất bản bill trong room COMPLETED, sau reconciliation FINALIZED.

So sánh lựa chọn: (a) OCR + parser theo bố cục dễ đo lỗi và fine-tune; (b) vision LLM trực tiếp nhanh để thử nhưng khó tách nguyên nhân lỗi; (c) OCR + mô hình hiểu tài liệu cần nhiều nhãn. Chọn (a) cho baseline, giữ interface để benchmark (b)/(c) sau.

## 2. Luồng và ranh giới

Ảnh → kiểm tra/crop/xoay → OCR → tokens có tọa độ → parser bố cục → ReceiptDraft → Host sửa/xác nhận → SplitPlan → validator → engine tính tiền → Host xác nhận → backend khóa bill version → VietQR.

OCR adapter trả dữ liệu trung lập với thư viện. Parser không phụ thuộc Firebase/UI. Engine chia không phụ thuộc OCR/LLM. LLM chỉ đề xuất SplitPlan, không tự gọi mutation settlement. Kết quả baseline local là preview, không phải bill authoritative.

Mobile hiện là prototype; scanner không giả định các adapter Firebase đã tồn tại. Service inference Python là mở rộng kiến trúc cần ADR khi tích hợp. Cloud Functions tiếp tục authorization và tính bill cuối; ảnh lưu object storage riêng khi triển khai cloud, không nhét ảnh vào Firestore.

## 3. Hợp đồng dữ liệu

Mọi object có schemaVersion. Tiền là integer VND không âm; missing là null, không chuyển thành 0. Số lượng dùng numerator/denominator nguyên dương để hỗ trợ phần lẻ. ID món ổn định trong receipt revision.

OCRDocument: imageId, width, height, engineVersion, tokens[]. Token gồm tokenId, text, polygon theo pixel ảnh xử lý, confidence nullable; giữ transform về ảnh gốc.

ReceiptDraft: receiptId, revision, currency=VND, items[], adjustments[], printedSubtotalVnd, printedTotalVnd, computedTotalVnd, discrepancyVnd, warnings[], reviewStatus.

Item: itemId, name, quantity, unitPriceVnd, lineTotalVnd. Mỗi field kèm sourceTokenIds, origin (OCR/DERIVED/USER), confidence nullable. Giá in ở dòng là giá trị đối soát chính; bất đồng quantity × unitPrice sinh warning. Thiếu trường không chặn sửa tay nhưng chặn xác nhận nếu không đủ dữ liệu tính tổng.

Adjustment: adjustmentId, kind (TAX/SERVICE_CHARGE/DISCOUNT/OTHER), amountVnd không âm, effect (ADD/SUBTRACT/INCLUDED), allocationPolicy (PROPORTIONAL/EQUAL), sourceTokenIds. INCLUDED không cộng/trừ lần nữa. Không phân biệt được INCLUDED và ADD thì yêu cầu Host chọn. Phần trăm lưu basis points nguyên; Host xác nhận cơ sở tính rồi materialize amountVnd trước chia.

SplitPlan: receiptId, receiptRevision, mode=ITEMIZED, allocations[]. Mỗi allocation tham chiếu itemId và danh sách memberUid + weight nguyên dương. Weight biểu diễn tỷ lệ chia toàn bộ giá trị dòng, không tự suy ra số phần đã ăn. Mỗi item xuất hiện đúng một allocation, không có người/món ngoài danh sách. LLM trả status READY hoặc NEEDS_CLARIFICATION với câu hỏi khi thiếu thông tin.

BillPreview: receiptRevision, planRevision, policyVersion, shares[] gồm memberUid và các thành phần tiền; totalVnd. Server publication bổ sung billVersion, actorUid, timestamp và idempotency receipt.

## 4. Quy tắc tiền và ví dụ

computedTotal = tổng lineTotal + ADD - SUBTRACT; INCLUDED không đổi tổng. Nếu khác printedTotal, chặn confirm đến khi Host sửa hoặc xác nhận tổng thay thế có lý do. Không sửa giá tự động để khớp tổng.

Phân bổ giá dòng theo weights bằng phân số chính xác; không làm tròn trung gian. Thuế/phí/giảm giá mặc định phân bổ theo tiền món trước điều chỉnh; có thể chọn chia đều. Trường hợp cơ sở tỷ lệ bằng 0 hoặc giảm giá tạo share âm phải yêu cầu sửa quy tắc.

ITEMIZED đề xuất làm tròn một lần ở cuối tới 1 VND bằng largest remainder, tie theo memberUid tăng dần. Đây là chính sách mới, cần review; không thay chính sách 1.000 VND của PENALTY. Tổng shares luôn bằng tổng bill đã xác nhận, shares không âm.

Ví dụ độc lập: món chung 59.000, hai trà 24.000; A/B chia món chung đều và mỗi người một trà → A=41.500, B=41.500. Nếu A dùng cả hai trà → A=53.500, B=29.500.

Ví dụ làm tròn: 10.001 chia ba người weights bằng nhau, UID a/b/c → 3.334/3.334/3.333. Ví dụ tổng lệch: các dòng 83.000 nhưng printedTotal 85.000 → chặn xác nhận, hiển thị lệch 2.000.

## 5. Review, concurrency và lỗi

UI hiển thị vùng ảnh tương ứng trường được chọn; giữ raw OCR và lịch sử sửa. Sửa hóa đơn tăng revision và vô hiệu SplitPlan/BillPreview cũ. Job cũ không ghi đè revision người dùng đã sửa.

Scan job: QUEUED → RUNNING → SUCCEEDED/FAILED/CANCELLED. Retry dùng cùng idempotency key và hash input; khác hash bị từ chối. File lỗi, ảnh quá mờ, timeout và OCR không có chữ là lỗi riêng; luôn có nhập tay.

Offline lưu ảnh/draft local; không queue lệnh xuất bản settlement. Backend kiểm tra Host, membership, lifecycle, revision và idempotency. Khi đã xuất bản QR, không âm thầm tính lại bill. Baseline chặn sửa bill đã publish; quy trình thay thế bill phải thiết kế riêng trước release.

## 6. Dữ liệu và benchmark

Ảnh hiện có `17dc65bff7b477ea2ea5.jpg` là mẫu bootstrap, chưa phải ground truth và không đủ benchmark. Có nền chứa thông tin tài khoản; không giải mã QR và không dùng thông tin thanh toán trong ảnh để chọn người nhận tiền.

Ground truth phải do người review: polygon + text cho OCR, liên kết token/dòng và field cho extraction. Label không rõ phải đánh dấu unreadable; không đoán. Lưu raw transcription riêng normalized value. Synthetic fixtures dùng kiểm thử nghiệp vụ, không báo cáo như chất lượng ảnh thật.

Mục tiêu bootstrap 300–500 ảnh có quyền sử dụng, đa dạng cửa hàng/template/chất lượng. Chia theo cửa hàng/template thành train/validation/test khoảng 70/15/15; ảnh trùng/augmentation ở cùng split. Test khóa trước tuning, bao gồm nhóm cửa hàng chưa thấy và nhóm ảnh khó. Dữ liệu sửa của người dùng chỉ dùng train khi có đồng ý và kiểm duyệt; production không tự gửi vào dataset.

Đo: detection precision/recall, CER toàn văn và vùng số tiền, money exact match, total exact match, item-row exact match (tất cả field bắt buộc), receipt exact match, tỷ lệ cần sửa, thời gian review, p50/p95 latency và chi phí/bill. Báo cáo số mẫu và kết quả từng nhóm; không gộp thành một accuracy.

Fine-tune recognizer khi lỗi đọc chiếm ưu thế; detector khi bỏ/cắt sai vùng. Lưu dataset manifest/hash, seed, config, checkpoint, charset, package versions và hardware. Kiểm tra charset tiếng Việt, pretrained weights và license trước chọn model. Không train từ đầu.

## 7. Checkpoint và đầu ra

CP0: review spec này, đặc biệt ITEMIZED, điều chỉnh bill và làm tròn 1 VND. Đầu ra: quyết định được chấp thuận; cập nhật scope/ADR khi tích hợp mobile.

CP1: schema máy đọc được, label guide, manifest, fixtures nghiệp vụ và evaluator. Chỉ hoàn thành benchmark data khi đủ ảnh đã review và split không rò rỉ; một ảnh hiện tại chỉ đủ bootstrap.

CP2: CLI local nhận ảnh → OCR adapter thật → parser → draft JSON; hỗ trợ correction JSON → SplitPlan thủ công → preview. README có lệnh tái lập và báo cáo trên mẫu thật. Không gọi transcript thủ công là kết quả OCR. LLM/Firebase/VietQR production chưa thuộc CP2.

CP3: fine-tune và so sánh held-out test; CP4: cải thiện extraction; CP5: harden engine; CP6: LLM intents; CP7: mobile/backend; CP8: pilot. CP2 có engine tối thiểu, CP5 kiểm chứng rộng trước production.

Ngưỡng CP4 đề xuất: total exact match ≥98%, item-row exact match ≥90% trên tập test đã công bố; không áp dụng cho một ảnh. CP6 đề xuất plan exact match ≥95% trên yêu cầu rõ nghĩa, ca mơ hồ có nhãn phải hỏi lại. Invariant tiền bắt buộc ở mọi checkpoint có chia tiền.

## 8. Kiểm chứng và vận hành

Test bắt buộc cho số tiền/giảm giá/thuế included, phân số, residual, UID tie, người/món lạ, revision cũ và duplicate publish. OCR cần chạy ảnh thật; runtime/model tải về được ghi version, không bịa kết quả. Quota và giới hạn tài nguyên phải có trước public inference.

Ảnh cloud chỉ tồn tại tạm phục vụ review, đề xuất tự xóa sau 24 giờ; xóa ảnh local sau xác nhận theo lựa chọn người dùng. Training dataset có consent/retention riêng. Không ghi ảnh, raw OCR, thông tin ngân hàng vào logs. Bank recipient chỉ lấy settlement details Host đã nhập.

Ngân sách OCR/LLM đo trên pilot; Premium lifetime không mặc nhiên cấp scan không giới hạn. CP2 chưa gọi dịch vụ trả phí.

## 9. Foundation update — 2026-10-14

Theo yêu cầu khởi tạo base và skills, repository riêng được chuẩn bị cho GitHub `LTKThoa/DontLift-Smart-Bill-Scanner`. Git/Python dùng runtime đi kèm Codex. Foundation triển khai reviewed receipt tối thiểu, CLI và ITEMIZED preview, không coi đây là hoàn thành CP1/CP2. Provenance/draft OCR, benchmark ảnh thật, model và cloud settlement chưa triển khai. Quy tắc production vẫn cần review trước tích hợp; foundation local là bước có thể kiểm chứng độc lập.
