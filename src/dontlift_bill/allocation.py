"""Deterministic ITEMIZED preview; this module never publishes settlement."""

from fractions import Fraction

from .domain import ValidationError, array, identifier, integer, obj, validate_receipt


def preview(receipt: object, plan: object, members: object) -> dict:
    receipt = validate_receipt(receipt)
    plan = obj(plan, "plan")
    member_ids = [identifier(uid, "memberUid") for uid in array(members, "members", True)]
    if len(set(member_ids)) != len(member_ids):
        raise ValidationError("duplicate memberUid")
    if integer(plan.get("schemaVersion"), "plan.schemaVersion", 1) != 1:
        raise ValidationError("unsupported plan schemaVersion")
    integer(plan.get("receiptRevision"), "receiptRevision", 1)
    integer(plan.get("revision"), "plan.revision", 1)
    if plan.get("receiptId") != receipt["receiptId"] or plan["receiptRevision"] != receipt["revision"]:
        raise ValidationError("plan references a different receipt or stale revision")
    if plan.get("mode") != "ITEMIZED":
        raise ValidationError("only ITEMIZED preview is supported")
    items = {item["itemId"]: item for item in receipt["items"]}
    raw = {uid: Fraction(0) for uid in sorted(member_ids)}
    allocated = set()
    for value in array(plan.get("allocations"), "allocations", True):
        allocation = obj(value, "allocation")
        item_id = identifier(allocation.get("itemId"), "allocation.itemId")
        if item_id not in items or item_id in allocated:
            raise ValidationError("unknown or duplicate allocated item")
        allocated.add(item_id)
        weights = {}
        for value in array(allocation.get("members"), "allocation.members", True):
            member = obj(value, "allocation member")
            uid = identifier(member.get("memberUid"), "memberUid")
            if uid not in raw or uid in weights:
                raise ValidationError("unknown or duplicate allocation member")
            weights[uid] = integer(member.get("weight"), "weight", 1)
        weight_total = sum(weights.values())
        for uid, weight in weights.items():
            raw[uid] += Fraction(items[item_id]["lineTotalVnd"] * weight, weight_total)
    if allocated != set(items):
        raise ValidationError("every item must be allocated exactly once")
    base = raw.copy()
    subtotal = sum(base.values())
    for adjustment in receipt["adjustments"]:
        if adjustment["effect"] == "INCLUDED":
            continue
        amount = adjustment["amountVnd"] * (1 if adjustment["effect"] == "ADD" else -1)
        if adjustment["allocationPolicy"] == "PROPORTIONAL" and not subtotal:
            raise ValidationError("proportional adjustment has zero basis")
        for uid in raw:
            raw[uid] += (Fraction(amount, len(raw)) if adjustment["allocationPolicy"] == "EQUAL"
                         else amount * base[uid] / subtotal)
    if any(share < 0 for share in raw.values()):
        raise ValidationError("adjustments produce negative share")
    shares = {uid: share.numerator // share.denominator for uid, share in raw.items()}
    remaining = receipt["printedTotalVnd"] - sum(shares.values())
    rank = sorted(raw, key=lambda uid: (-(raw[uid] - shares[uid]), uid))
    for uid in rank[:remaining]:
        shares[uid] += 1
    if sum(shares.values()) != receipt["printedTotalVnd"]:
        raise ValidationError("allocation invariant failed")
    return {"schemaVersion": 1, "authoritative": False, "mode": "ITEMIZED",
            "receiptId": receipt["receiptId"], "receiptRevision": receipt["revision"],
            "planRevision": plan["revision"], "policyVersion": "itemized-v1",
            "totalVnd": receipt["printedTotalVnd"],
            "shares": [{"memberUid": uid, "shareVnd": shares[uid]} for uid in sorted(shares)]}
