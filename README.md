# DontLift-Smart-Bill-Scanner

Nền tảng scanner hóa đơn cho DontLift: OCR → trích xuất → Host sửa → kế hoạch chia → kiểm tra tiền → backend xác nhận → VietQR.

## Phạm vi hiện tại

Package Python kiểm tra hóa đơn JSON và tạo preview chia theo món với số học phân số chính xác. Có CLI, synthetic fixtures, tests và GitHub Actions. Chưa có OCR runtime, model fine-tune, LLM, API server hoặc tích hợp mobile. Đầu ra local không phải bill thanh toán authoritative.

Python 3.12+. Không cần cài dependency để chạy source/tests.

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
python -m dontlift_bill.cli validate examples/receipt.synthetic.json
python -m dontlift_bill.cli preview examples/receipt.synthetic.json examples/plan.synthetic.json examples/members.synthetic.json
```

Trên bash dùng `export PYTHONPATH=src`. Có thể cài package bằng `python -m pip install -e .` và dùng `dontlift-bill` thay cho `python -m dontlift_bill.cli`.

Ví dụ synthetic trả tổng 83.000đ, a/b mỗi người 41.500đ. CLI trả exit code 2 nếu dữ liệu không hợp lệ. Input là hợp đồng reviewed receipt tối thiểu; provenance và draft OCR chưa được triển khai.

## Quy tắc

- ITEMIZED chia toàn bộ giá trị dòng theo weights, adjustments theo tiền món trước điều chỉnh hoặc chia đều; round một lần tới 1đ, tie theo UID.
- INCLUDED không cộng lại thuế/phí. Tổng lệch, giá không khớp số lượng, kế hoạch cũ hoặc người/món lạ bị từ chối.
- PENALTY 40/60 và rounding 1.000đ của mobile không nằm trong engine này.
- Host và backend DontLift xác nhận bill cuối. Thông tin ngân hàng trong ảnh không được dùng chọn người nhận.

## Tài liệu và skills

- [Thiết kế và checkpoint](docs/superpowers/specs/2026-10-13-smart-bill-scanner-design.md)
- [Hướng dẫn đóng góp](CONTRIBUTING.md)
- [Dataset bootstrap](docs/dataset-guide.md)
- [Receipt pipeline skill](.agents/skills/dontlift-receipt-pipeline/SKILL.md)
- [Bill validation skill](.agents/skills/dontlift-bill-validation/SKILL.md)

Skills lưu tại `.agents/skills` cùng repo để review/version cùng code. AGENTS.md chỉ đường dẫn để agent đọc khi phù hợp; không cần cài bản global. Không commit ảnh thật, labels, weights hoặc secrets. Fixtures trong `examples/` hoàn toàn synthetic, không chứng minh chất lượng OCR.

## Bước tiếp theo

CP1: schema draft đầy đủ, manifest/gán nhãn và evaluator. CP2: OCR adapter thật → parser → draft/correction → preview. CP3: benchmark đủ dữ liệu rồi mới fine-tune. Base hiện tại chưa hoàn thành CP1/CP2.
