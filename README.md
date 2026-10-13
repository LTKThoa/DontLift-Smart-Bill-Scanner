# DontLift-Smart-Bill-Scanner

Nền tảng scanner hóa đơn cho DontLift: OCR → trích xuất → Host sửa → kế hoạch chia → kiểm tra tiền → backend xác nhận → VietQR.

## Phạm vi hiện tại

Package Python chạy OCR CPU trên ảnh local, tạo draft có provenance, nhận correction thủ công, kiểm tra hóa đơn JSON và tạo preview chia theo món bằng phân số chính xác. Có CLI, JSON schemas, synthetic tests và GitHub Actions. Chưa fine-tune model, chưa có LLM, API server hoặc tích hợp mobile. Đầu ra local không phải bill thanh toán authoritative.

Python 3.12+. Không cần cài dependency để chạy source/tests.

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
python -m dontlift_bill.cli validate examples/receipt.synthetic.json
python -m dontlift_bill.cli preview examples/receipt.synthetic.json examples/plan.synthetic.json examples/members.synthetic.json
```

Trên bash dùng `export PYTHONPATH=src`. Có thể cài package bằng `python -m pip install -e .` và dùng `dontlift-bill` thay cho `python -m dontlift_bill.cli`.

Ví dụ synthetic trả tổng 83.000đ, a/b mỗi người 41.500đ. CLI trả exit code 2 nếu dữ liệu không hợp lệ. Các lệnh validate/preview nhận reviewed receipt tối thiểu; scan/extract tạo draft có provenance riêng.

## Quy tắc

- ITEMIZED chia toàn bộ giá trị dòng theo weights, adjustments theo tiền món trước điều chỉnh hoặc chia đều; round một lần tới 1đ, tie theo UID.
- INCLUDED không cộng lại thuế/phí. Tổng lệch, giá không khớp số lượng, kế hoạch cũ hoặc người/món lạ bị từ chối.
- PENALTY 40/60 và rounding 1.000đ của mobile không nằm trong engine này.
- Host và backend DontLift xác nhận bill cuối. Thông tin ngân hàng trong ảnh không được dùng chọn người nhận.

## Tài liệu và skills

- [Thiết kế và checkpoint](docs/superpowers/specs/2026-10-13-smart-bill-scanner-design.md)
- [Hướng dẫn đóng góp](CONTRIBUTING.md)
- [Dataset bootstrap](docs/dataset-guide.md)
- [Chạy OCR baseline và review](docs/ocr-baseline.md)
- [Manifest và đánh giá OCR/extraction](docs/evaluation.md)
- [Receipt pipeline skill](.agents/skills/dontlift-receipt-pipeline/SKILL.md)
- [Bill validation skill](.agents/skills/dontlift-bill-validation/SKILL.md)

Skills lưu tại `.agents/skills` cùng repo để review/version cùng code. AGENTS.md chỉ đường dẫn để agent đọc khi phù hợp; không cần cài bản global. Không commit ảnh thật, labels, weights hoặc secrets. Fixtures trong `examples/` hoàn toàn synthetic, không chứng minh chất lượng OCR.

## Bước tiếp theo

CP1 đã có manifest validator và evaluator (CER, món, tiền, tổng, receipt, latency, nhóm chất lượng); còn cần dữ liệu thật đã review và split đóng băng. CP2 đã có luồng CLI OCR → draft/correction → preview cho layout hẹp; cần mở rộng parser và benchmark trước tích hợp. CP3: benchmark đủ dữ liệu rồi mới fine-tune. Xem giới hạn trong hướng dẫn OCR.
