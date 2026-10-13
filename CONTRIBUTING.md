# Contributing

Use Python 3.12+ and a virtual environment for future dependencies. Keep runtime/model version changes explicit and reproducible. Run the README verification commands before committing.

Use focused Conventional Commits, for example `feat(ocr): add recognition adapter`, `fix(allocation): reject stale plans`, `test(domain): cover included tax`. Branch examples: `feature/ocr-baseline`, `fix/receipt-validation`.

PRs explain the concrete behavior, verification and remaining limitations. Money changes need conservation/non-negativity and malformed-input tests. Model changes need held-out comparisons, data/config versions and subgroup results. Never report synthetic fixtures as real OCR accuracy.

Keep datasets, model weights and customer receipts outside Git. Inspect staged changes before pushing. No project license has been selected yet; do not assume permission for third-party redistribution or add a license on the owner's behalf.
