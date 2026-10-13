"""Explicit local human correction boundary; no room authorization implied."""

from copy import deepcopy

from .domain import ValidationError, integer, obj, validate_receipt


def review_draft(draft: dict, correction: dict) -> dict:
    draft, correction = obj(draft, 'draft'), obj(correction, 'correction')
    expected = integer(correction.get('expectedRevision'), 'expectedRevision', 1)
    if expected != draft.get('revision'):
        raise ValidationError('stale draft revision')
    if correction.get('confirmed') is not True:
        raise ValidationError('explicit local review confirmation required')
    receipt = deepcopy(obj(correction.get('receipt'), 'correction.receipt'))
    if receipt.get('receiptId') != draft.get('receiptId'):
        raise ValidationError('correction references another receipt')
    if receipt.get('revision') != expected + 1:
        raise ValidationError('corrected receipt revision must increment by one')
    validate_receipt(receipt)
    return {'schemaVersion': 1, 'reviewStatus': 'LOCALLY_REVIEWED', 'authoritative': False,
            'previousRevision': expected, 'receipt': receipt,
            'provenance': {'origin': 'USER', 'originalDraft': deepcopy(draft)}}
