"""Strict validation at the untrusted JSON boundary."""

from fractions import Fraction


class ValidationError(ValueError):
    """Input cannot safely represent a confirmed bill or split plan."""


def integer(value: object, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValidationError(f"{field}: expected integer >= {minimum}")
    return value


def identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field}: expected non-empty string")
    return value


def obj(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ValidationError(f"{field}: expected object")
    return value


def array(value: object, field: str, nonempty: bool = False) -> list:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValidationError(f"{field}: expected {'non-empty ' if nonempty else ''}array")
    return value


def validate_receipt(value: object) -> dict:
    receipt = obj(value, "receipt")
    if integer(receipt.get("schemaVersion"), "schemaVersion", 1) != 1:
        raise ValidationError("unsupported schemaVersion")
    identifier(receipt.get("receiptId"), "receiptId")
    integer(receipt.get("revision"), "revision", 1)
    if receipt.get("currency") != "VND":
        raise ValidationError("currency must be VND")
    seen = set()
    subtotal = 0
    for raw in array(receipt.get("items"), "items", True):
        item = obj(raw, "item")
        item_id = identifier(item.get("itemId"), "itemId")
        if item_id in seen:
            raise ValidationError("duplicate itemId")
        seen.add(item_id)
        identifier(item.get("name"), "name")
        quantity = obj(item.get("quantity"), "quantity")
        count = Fraction(integer(quantity.get("numerator"), "numerator", 1),
                         integer(quantity.get("denominator"), "denominator", 1))
        line = integer(item.get("lineTotalVnd"), "lineTotalVnd")
        unit = item.get("unitPriceVnd")
        if unit is not None and count * integer(unit, "unitPriceVnd") != line:
            raise ValidationError(f"item {item_id}: quantity/price mismatch needs review")
        subtotal += line
    total = subtotal
    adjustment_ids = set()
    for raw in array(receipt.get("adjustments"), "adjustments"):
        adjustment = obj(raw, "adjustment")
        aid = identifier(adjustment.get("adjustmentId"), "adjustmentId")
        if aid in adjustment_ids:
            raise ValidationError("duplicate adjustmentId")
        adjustment_ids.add(aid)
        if adjustment.get("kind") not in {"TAX", "SERVICE_CHARGE", "DISCOUNT", "OTHER"}:
            raise ValidationError("invalid adjustment kind")
        amount = integer(adjustment.get("amountVnd"), "amountVnd")
        effect = adjustment.get("effect")
        if effect not in {"ADD", "SUBTRACT", "INCLUDED"}:
            raise ValidationError("invalid adjustment effect")
        if adjustment.get("allocationPolicy") not in {"PROPORTIONAL", "EQUAL"}:
            raise ValidationError("invalid allocationPolicy")
        total += amount if effect == "ADD" else -amount if effect == "SUBTRACT" else 0
    if total < 1000:
        raise ValidationError("total must be >= 1000 VND")
    if integer(receipt.get("printedTotalVnd"), "printedTotalVnd") != total:
        raise ValidationError("printed total mismatch needs Host review")
    return receipt
