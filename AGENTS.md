# Repository instructions

This repository owns the AI receipt pipeline and local itemized split preview. Mobile lives in a separate repository. Python 3.12+; runtime foundation uses the standard library.

## Domain boundaries

- Read `docs/superpowers/specs/2026-10-13-smart-bill-scanner-design.md` before domain changes. It records proposed architecture; foundation implementation does not imply production approval.
- Keep OCR, receipt extraction, LLM intent, allocation and transport separate.
- AI produces drafts. Only the DontLift backend may publish authoritative room bills after Host review and score reconciliation.
- ITEMIZED uses exact fractional arithmetic and final 1 VND allocation. PENALTY remains the existing mobile 40/60 policy and 1,000 VND rounding; do not merge them implicitly.
- Do not infer payment recipient from receipt QR codes or background bank details.
- Do not commit real receipts, labels, weights, credentials or generated runs. Synthetic fixtures must be identified as synthetic.

## Skills

- For OCR, datasets, extraction, fine-tuning or model evaluation, read `.agents/skills/dontlift-receipt-pipeline/SKILL.md`.
- For money, allocations, intent validation or settlement integration, read `.agents/skills/dontlift-bill-validation/SKILL.md`.
- Skills are repository-scoped and versioned alongside the contracts they govern.

## Verification and commits

Run `python -m unittest discover -s tests -v` with `PYTHONPATH=src` and exercise the documented CLI. Add meaningful tests for money changes, malformed input and revision conflicts. Do not describe fixture parsing as OCR execution.

Use focused Conventional Commits (`chore`, `docs`, `feat`, `fix`, `test`, `ci`) with scopes. Stage explicit paths and inspect staged changes. Do not change global Git identity, force-push, or deploy infrastructure without the corresponding request.
