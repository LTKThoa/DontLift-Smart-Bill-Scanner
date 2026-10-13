# Dataset bootstrap

No reviewed image benchmark is committed. The local sample is excluded by `.gitignore`; the fixture values are synthetic and must not be used as benchmark labels.

Store real data outside source control, with a manifest containing sampleId, image hash, merchant/template group, split, consent/source, annotation version and review status. Avoid phone numbers or bank information in manifest IDs.

Annotate exact visible text and polygons, then token-to-field links and item rows separately. Mark unreadable fields; missing values remain null. Preserve raw text separately from normalized VND and fractional quantities. Do not infer values and label them as observed.

Deduplicate before splitting; merchant/template groups and augmented variants stay in one split. Freeze a held-out test set before training. A 70/15/15 split is an initial target, adjusted to group counts. Document group and quality distributions.

Report sample counts, CER, money/total exact match, full-row match, receipt-level match and p50/p95 runtime separately. Bootstrap target is 300–500 diverse reviewed receipts, not a guarantee of adequate training coverage. A single sample cannot establish model accuracy.
