# OCR baseline — CP1/CP2

## Run locally

Python 3.12+; CPU OCR runs inside the project virtualenv. Images are processed locally. First inference downloads models; later runs use the model cache. Downloaded weights and all outputs are ignored by Git.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[ocr,dev]"
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m dontlift_bill.cli scan path/to/receipt.jpg --output outputs/draft.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The scan command writes a NEEDS_REVIEW draft containing the OCR document, image hash, EXIF orientation, dimensions, polygons, token confidence, package versions and downloaded model hashes. Coordinates refer to the EXIF-oriented image, not the encoded unrotated pixels. No crop/perspective correction is implemented yet.

Pinned baseline: RapidOCR 3.10.0, ONNX Runtime 1.31.0, PP-OCRv6 small detector, legacy angle classifier and PP-OCRv5 Latin mobile recognizer. Latin is a baseline choice for Vietnamese text; charset performance remains to be evaluated. Inference timing includes initialization and model downloads on first call, not steady-state latency.

Parser supports a narrow printed layout: numbered name / unit price / integer quantity / amount columns, or a combined row with grouped VND. It can preserve a null unreadable unit price, never convert letters such as C/O to digits silently. It does not yet extract arbitrary layouts, fractional quantities, adjustments, multiline names or ungrouped total amounts. All drafts require review of adjustments even when total matches.

## Review and split

Create a correction JSON with `expectedRevision`, `confirmed: true` and a complete `receipt` using the reviewed receipt format in `examples/receipt.synthetic.json`. Keep receiptId from the draft; set receipt revision to expectedRevision + 1. Human review must cover every field, item completeness, adjustment semantics and the total. This local tool cannot authenticate a Host.

```powershell
.\.venv\Scripts\python.exe -m dontlift_bill.cli review outputs/draft.json outputs/correction.json --output outputs/reviewed.json
```

The review artifact preserves the original draft under provenance. Extract its `receipt` object to a receipt JSON for `validate` / `preview`; update the manual plan's receiptId and receiptRevision accordingly. Plan members are still entered manually; no LLM is connected. Output files must not already exist, protecting existing reviewed artifacts from overwrite.

Machine-readable draft and OCR contracts live in `schemas/`. Tests validate generated drafts using JSON Schema and verify semantic correction checks. Schemas describe baseline output, not the eventual full extraction model. Provenance currently links each field to its whole detected row, not individual words.

## Model provenance

Use the pinned RapidOCR registry and hashes recorded in the output to identify downloaded artifacts. The runtime source and models have separate attribution. See [official usage](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/), [license statement](https://rapidai.github.io/RapidOCRDocs/main/en/model_licenses/) and [PaddleOCR model list](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/model_list.md). The RapidOCR license statement explicitly scopes its artifact table; the Latin recognizer needs its own upstream record when preparing redistribution. This repo does not redistribute weights or assign a license to them.

## Checkpoint limits

This is a real local image-to-draft baseline with a correction boundary. CP1 is incomplete until a reviewed dataset, frozen split manifest and aggregate evaluator are available. CP2 remains limited to one narrow parser and CLI; no mobile, cloud, LLM, automatic settlement or fine-tuning is included.
