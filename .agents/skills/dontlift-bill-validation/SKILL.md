---
name: dontlift-bill-validation
description: Implement or review DontLift itemized money allocation, split intents, rounding and settlement boundaries. Use when changing money rules or validating receipt-to-split plans; excludes OCR model training.
---

# DontLift bill validation

Read the design at `docs/superpowers/specs/2026-10-13-smart-bill-scanner-design.md` and the current domain/allocation modules relative to this repository. Preserve the explicit distinction between ITEMIZED and the mobile PENALTY policy; inspect mobile ADR-005 when integrating that boundary.

Money is integer VND and intermediate proportions use exact fractions. Reject booleans as numbers, negative amounts, zero/negative weights, unknown/duplicate people or items, missing item allocations, mismatched totals and stale receipt revisions. Check quantity × unit price when both are known. Missing is not zero.

Included taxes/fees are not added again. Proportional adjustments use the pre-adjustment item-share basis. Require review when the basis is zero or any resulting share is negative. Round ITEMIZED once to 1 VND using largest remainder with ascending UID ties. PENALTY keeps its own approved 1,000 VND rules.

Verify conservation, non-negativity, determinism under input reordering, fractional quantities, large integer amounts, discounts and rounding ties. Include malformed-input and revision-conflict tests; run the documented suite. Do not replace semantic checks with valid-JSON checks.

LLM outputs reference existing member/item IDs and cannot calculate authoritative payment or execute settlement mutations. Ambiguous names, items or quantities require clarification. Backend authorization derives the actor from verified authentication and verifies Host, membership, lifecycle, reconciliation and revision before publication.

Local CLI output remains a preview. VietQR uses a published server bill and Host-entered settlement details. A late OCR job or LLM response cannot alter a published bill, and QR creation never marks payment as received.
