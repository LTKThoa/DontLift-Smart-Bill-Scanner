# Local smoke report — 2026-10-14

One existing local receipt image, processed locally on Windows/Python 3.12.14. Image, raw text and outputs remain ignored by Git. This is a development smoke test, not a held-out benchmark or reviewed training label.

RapidOCR 3.10.0 / ONNX Runtime 1.31.0 produced 32 line tokens. Initial cold call including model downloads took 15.38 seconds; a new-process call using cached models took 6.25 seconds including engine initialization. These two observations are not p50/p95 latency.

The first parser returned no items because OCR read one unit price with a letter and distorted the total label. The parser was then extended to handle four-column numbered rows and a conservative fuzzy total label. The image has therefore been used for development and must not be reported as unseen test data.

After the parser change: two item candidates, line amounts 59,000 and 24,000 VND, total candidate 83,000 VND, discrepancy 0. One unit price remains null (OCR contains a letter), both names need review and the total label is marked fuzzy. Adjustments always require review. No bank recipient was extracted and no payment QR was generated.

The actual generated draft passed its JSON Schema. The local suite passed 21 tests, including schema validation, provenance, ambiguous/missing totals, malformed OCR tokens, stale correction revisions, CLI overwrite protection and money invariants. Synthetic tests are separate from real OCR execution.

## Model hashes observed

| Model | SHA-256 |
|---|---|
| PP-OCRv6_det_small.onnx | 090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f |
| ch_ppocr_mobile_v2.0_cls_mobile.onnx | e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c |
| latin_PP-OCRv5_rec_mobile.onnx | b20bd37c168a570f583afbc8cd7925603890efbcdc000a59e22c269d160b5f5a |

Remaining: reviewed manifest and aggregate evaluator, broad layouts, preprocessing, full adjustment extraction, robust inference API and mobile integration. No model was fine-tuned. Disk C temporary storage was full during installation; installation succeeded using a project-local temporary directory on D without deleting unrelated files.
