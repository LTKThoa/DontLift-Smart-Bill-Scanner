# Dataset identity and receipt evaluation

The evaluator is deterministic and local. It measures saved outputs; it does not run models or certify that labels were reviewed. Real labels, manifests and reports belong outside Git or under ignored `data/` and `outputs/` paths. Committed benchmark examples are synthetic.

## Manifest

Use `examples/manifest.synthetic.json` as a format example. Required top-level fields are schemaVersion=1, datasetVersion, synthetic (explicit boolean) and samples.

Each sample contains sampleId, imageSha256, merchantGroup, templateGroup, familyGroup, qualityGroup, split (train/validation/test), source, rightsConfirmed=true, reviewStatus=REVIEWED and annotationVersion. `familyGroup` ties an original image to crops/augmentations. None of the three group types may span splits; the validator does not infer near-duplicates or template identity from pixels. Human grouping remains necessary. Identical hashes are rejected even within a split to prevent duplicate weighting.

Optional imagePath is relative to the manifest directory. `--verify-images` verifies bytes against the hash and rejects paths outside that directory. Without this option, metadata is checked but image existence and hashes are not verified; check imagesVerified in the result. Synthetic examples have illustrative hashes and no images.

```powershell
$env:PYTHONPATH = 'src'
python -m dontlift_bill.cli check-manifest examples/manifest.synthetic.json
python -m dontlift_bill.cli check-manifest data/manifest.json --verify-images
```

The canonical manifest hash is SHA-256 over sorted-key compact UTF-8 JSON, with samples sorted by sampleId. Every metadata change changes the identity; simple sample reordering does not. Freeze the manifest before tuning, and copy its returned manifestSha256 into label/prediction bundles. This detects identity mismatch, not whether a developer has already viewed test data.

## Labels and predictions

Label bundle: schemaVersion=1, manifestSha256 and samples. Each selected sample needs sampleId, reviewed=true, ocrText and receipt. Receipt uses the existing reviewed receipt contract. Empty OCR reference text is rejected. For CER, transcribe the complete selected input image in reading order, including non-item header/footer text; alternatively crop both OCR input and labeling scope consistently before hashing. Do not compare full-image OCR to item-only transcription.

Prediction bundle: schemaVersion=1, manifestSha256, runId, pipelineVersion and samples. Each prediction has sampleId, ocrText, receipt (object or null) and optional elapsedSeconds. Failed/missing predictions remain part of the denominator. Extra unknown IDs, duplicate IDs and missing selected labels cause an error. See `examples/labels.synthetic.json` and `examples/predictions.synthetic.json`.

Export uncorrected drafts without reading ground truth:

```powershell
python -m dontlift_bill.cli export-prediction data/manifest.json outputs/draft.json --sample-id sample-001 --run-id baseline-001 --pipeline-version rapidocr-3.10-parser-v1 --output outputs/prediction-001.json
```

The draft image hash must match the manifest. Export reads values before correction and records engine metadata. For a multi-sample run, combine exported samples arrays into a bundle sharing the same manifestSha256, runId and pipelineVersion; never mix model/parser versions. The exporter sorts tokens into rows for reading order. Annotation must use the same spatial reading convention.

```powershell
python -m dontlift_bill.cli evaluate examples/manifest.synthetic.json examples/labels.synthetic.json examples/predictions.synthetic.json --output outputs/synthetic-evaluation.json
```

Default split is test; `--split validation` supports tuning without treating validation as held-out test. Existing report files are never overwritten.

## Metric definitions

- CER: total Levenshtein edits / total reference characters after NFC Unicode normalization and collapsing whitespace. Case and accents remain significant. CER can exceed 1 because insertions count. Empty/missing OCR predictions count as deleting the reference.
- Item-row exact match: matching rows / sum of max(reference rows, predicted rows) per receipt. Rows align by printed order, not AI-generated IDs. Name, quantity numerator/denominator, unit price and amount must match; extra/missing rows are penalized. No fuzzy name matching.
- Money exact match: correct unit prices, line amounts and printed totals / all comparable slots, including extra predicted rows. Unknown reference unit prices are excluded, never changed to zero. Taxes/fees are assessed separately through receipt exact match, not this money-slot metric.
- Total exact match: receipts with exact printed total / all selected receipts. Boolean values are not integers for this comparison.
- Receipt exact match: all rows, total, currency and adjustments match. Adjustment comparison is strict including order and IDs; use the same adjustment identity convention in labels/predictions. Missing fields do not imply successful extraction except an empty adjustment list.
- Latency: nearest-rank p50/p95 over samples that provide finite nonnegative elapsedSeconds. Report latency sampleCount alongside selected sampleCount; missing durations are excluded, not zero. Model initialization/download inclusion depends on the recorded run and must be documented.

Reports include selected sample count, prediction count, per-quality metrics, per-sample error counts, manifest identity and small-set warnings. They contain no raw OCR text or bank details. Cost, detection IoU/recall, human correction time and confidence calibration are not measured yet. Different confidence thresholds or parser rules must use different pipelineVersion.

Synthetic examples should yield perfect metrics; this only verifies the evaluator. They are flagged SYNTHETIC_NOT_MODEL_ACCURACY. A real benchmark still needs reviewed images and a frozen split.
