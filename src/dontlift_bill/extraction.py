"""Conservative row parser for printed name/unit-price/quantity/amount receipts."""

import re
import unicodedata
import math

from .domain import ValidationError


def folded(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
                   if unicodedata.category(c) != 'Mn')


def field(value, tokens, origin='OCR'):
    return {'value': value, 'sourceTokenIds': [t['tokenId'] for t in tokens],
            'origin': origin, 'confidence': min((t['confidence'] for t in tokens), default=None)}


def rows(tokens: list) -> list:
    grouped = []
    for token in sorted(tokens, key=lambda t: sum(p[1] for p in t['polygon']) / 4):
        ys = [p[1] for p in token['polygon']]
        center, height = sum(ys) / 4, max(ys) - min(ys)
        if grouped and abs(center - grouped[-1][0]) <= max(6, height * .65):
            grouped[-1][1].append(token)
        else:
            grouped.append((center, [token]))
    return [sorted(group, key=lambda t: min(p[0] for p in t['polygon'])) for _, group in grouped]


MONEY = r'\d{1,3}(?:[., ]\d{3})+'
ITEM = re.compile(r'^\s*(?:\d+[).]\s*)?(.+?)\s+(' + MONEY + r')\s*[xX×]?\s+(\d+)\s+(' + MONEY + r')\s*$')


def money(text):
    return int(re.sub(r'\D', '', text))


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (x != y)))
        previous = current
    return previous[-1]


def validate_document(document):
    if not isinstance(document, dict) or type(document.get('schemaVersion')) is not int or document['schemaVersion'] != 1:
        raise ValidationError('unsupported OCR document')
    if not isinstance(document.get('imageId'), str) or not document['imageId']:
        raise ValidationError('missing imageId')
    for axis in ('width', 'height'):
        if type(document.get(axis)) is not int or document[axis] <= 0:
            raise ValidationError('invalid image dimensions')
    if not isinstance(document.get('tokens'), list):
        raise ValidationError('tokens must be an array')
    ids = set()
    for token in document['tokens']:
        if not isinstance(token, dict) or not isinstance(token.get('tokenId'), str) or not token['tokenId'] or token['tokenId'] in ids:
            raise ValidationError('missing or duplicate tokenId')
        ids.add(token['tokenId'])
        if not isinstance(token.get('text'), str):
            raise ValidationError('token text must be string')
        confidence = token.get('confidence')
        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValidationError('invalid token confidence')
        polygon = token.get('polygon')
        if not isinstance(polygon, list) or len(polygon) != 4:
            raise ValidationError('token requires four polygon points')
        for point in polygon:
            if not isinstance(point, list) or len(point) != 2:
                raise ValidationError('invalid polygon point')
            if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in point):
                raise ValidationError('invalid polygon coordinate')


def extract_draft(document: dict) -> dict:
    validate_document(document)
    items, warnings = [], ['HOST_REVIEW_REQUIRED', 'ADJUSTMENTS_REQUIRE_REVIEW']
    totals = []
    for group in rows(document['tokens']):
        text = ' '.join(t['text'] for t in group)
        normal = folded(text)
        label = folded(group[0]['text']).strip(' :')
        fuzzy_total = distance(label, 'tong cong') <= 2
        if fuzzy_total or any(label in normal for label in ('tong cong', 'thanh toan', 'grand total', 'total due')):
            if fuzzy_total and label != 'tong cong':
                warnings.append('TOTAL_LABEL_FUZZY_MATCH')
            amounts = re.findall(MONEY, text)
            if amounts:
                totals.append(field(money(amounts[-1]), group))
            continue
        match = ITEM.fullmatch(text)
        columns = (len(group) == 4 and re.match(r'^\d+[).]', group[0]['text'])
                   and re.fullmatch(r'\d+', group[2]['text'])
                   and re.fullmatch(MONEY + r'|\d{4,}', group[3]['text']))
        if not match and not columns:
            continue
        if columns:
            name = re.sub(r'^\d+[).]\s*', '', group[0]['text'])
            unit = group[1]['text']
            quantity = group[2]['text']
            amount = group[3]['text']
        else:
            name, unit, quantity, amount = match.groups()
        if not name.strip() or int(quantity) <= 0:
            continue
        unit_value = money(unit) if re.fullmatch(MONEY + r'|\d{4,}', unit) else None
        item_id = f'item-{len(items)+1:03}'
        items.append({'itemId': item_id, 'name': field(name.strip(), group),
                      'quantity': field({'numerator': int(quantity), 'denominator': 1}, group),
                      'unitPriceVnd': field(unit_value, group),
                      'lineTotalVnd': field(money(amount), group)})
        if unit_value is None:
            warnings.append(f'UNIT_PRICE_UNREADABLE:{item_id}')
        elif unit_value * int(quantity) != money(amount):
            warnings.append(f'PRICE_MISMATCH:{item_id}')
    if not items:
        warnings.append('NO_ITEMS_PARSED')
    if len(totals) != 1:
        warnings.append('TOTAL_MISSING_OR_AMBIGUOUS')
    total = totals[0] if len(totals) == 1 else field(None, [])
    computed = sum(item['lineTotalVnd']['value'] for item in items) if items else None
    discrepancy = total['value'] - computed if total['value'] is not None and computed is not None else None
    if discrepancy:
        warnings.append('TOTAL_MISMATCH')
    return {'schemaVersion': 1, 'receiptId': document['imageId'], 'revision': 1,
            'currency': 'VND', 'reviewStatus': 'NEEDS_REVIEW', 'items': items,
            'adjustments': [], 'printedTotalVnd': total, 'totalCandidates': totals,
            'computedTotalVnd': computed, 'discrepancyVnd': discrepancy, 'warnings': warnings,
            'ocrDocument': document}
