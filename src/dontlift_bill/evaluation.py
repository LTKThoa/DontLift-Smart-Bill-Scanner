"""Evaluate all selected samples; missing predictions count as failures."""

import math
import unicodedata

from .dataset import validate_manifest
from .domain import ValidationError, array, identifier, obj, validate_receipt
from .extraction import rows, validate_document


def prediction_from_draft(manifest, draft, sample_id, run_id, pipeline_version):
    """Export observed draft values without corrections or ground-truth access."""
    summary = validate_manifest(manifest)
    draft = obj(draft, 'draft')
    document = obj(draft.get('ocrDocument'), 'ocrDocument')
    validate_document(document)
    selected = [sample for sample in manifest['samples'] if sample['sampleId'] == sample_id]
    if not selected or document['imageId'] != selected[0]['imageSha256']:
        raise ValidationError('draft image hash does not match manifest sample')
    identifier(run_id, 'runId')
    identifier(pipeline_version, 'pipelineVersion')
    if draft.get('reviewStatus') != 'NEEDS_REVIEW':
        raise ValidationError('benchmark predictions must come from uncorrected draft')
    def value(field):
        return obj(field, 'draft field').get('value')
    receipt = {'currency': draft.get('currency'), 'printedTotalVnd': value(draft.get('printedTotalVnd')),
               'items': [{key: value(item.get(key)) for key in
                          ('name', 'quantity', 'unitPriceVnd', 'lineTotalVnd')}
                         for item in array(draft.get('items'), 'draft.items')],
               'adjustments': draft.get('adjustments', [])}
    text = ' '.join(token['text'] for row in rows(document['tokens']) for token in row)
    return {'schemaVersion': 1, 'manifestSha256': summary['manifestSha256'], 'runId': run_id,
            'pipelineVersion': pipeline_version, 'samples': [{'sampleId': sample_id,
                'ocrText': text, 'receipt': receipt, 'elapsedSeconds': document.get('elapsedSeconds'),
                'engine': document.get('engine')}]}


def normalized(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', text).split())


def edit_distance(reference: str, prediction: str) -> int:
    previous = list(range(len(prediction) + 1))
    for i, ref in enumerate(reference, 1):
        current = [i]
        for j, pred in enumerate(prediction, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (ref != pred)))
        previous = current
    return previous[-1]


def number_equal(a, b):
    return type(a) is int and type(b) is int and a == b


def row_equal(ref, pred):
    if not isinstance(pred, dict) or not isinstance(pred.get('name'), str):
        return False
    quantity = pred.get('quantity')
    if not isinstance(quantity, dict):
        return False
    rq = ref['quantity']
    unit_equal = (ref['unitPriceVnd'] is None and pred.get('unitPriceVnd') is None
                  or number_equal(ref['unitPriceVnd'], pred.get('unitPriceVnd')))
    return (normalized(ref['name']) == normalized(pred['name'])
            and number_equal(rq['numerator'], quantity.get('numerator'))
            and number_equal(rq['denominator'], quantity.get('denominator'))
            and unit_equal and number_equal(ref['lineTotalVnd'], pred.get('lineTotalVnd')))


def indexed(values, label):
    result = {}
    for value in array(values, label):
        value = obj(value, label + ' item')
        sid = identifier(value.get('sampleId'), label + '.sampleId')
        if sid in result:
            raise ValidationError(f'duplicate {label} sampleId')
        result[sid] = value
    return result


def percentile(values, fraction):
    """Nearest-rank empirical percentile; no latency estimate for missing runs."""
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def evaluate(manifest, labels, predictions, split='test') -> dict:
    summary = validate_manifest(manifest)
    labels, predictions = obj(labels, 'labels'), obj(predictions, 'predictions')
    if split not in {'train', 'validation', 'test'}:
        raise ValidationError('invalid evaluation split')
    for name, bundle in (('labels', labels), ('predictions', predictions)):
        if type(bundle.get('schemaVersion')) is not int or bundle['schemaVersion'] != 1:
            raise ValidationError(f'unsupported {name} schemaVersion')
        if bundle.get('manifestSha256') != summary['manifestSha256']:
            raise ValidationError(f'{name} references a different manifest')
    identifier(predictions.get('runId'), 'runId')
    identifier(predictions.get('pipelineVersion'), 'pipelineVersion')
    refs = indexed(labels.get('samples'), 'labels')
    preds = indexed(predictions.get('samples'), 'predictions')
    all_ids = {sample['sampleId'] for sample in manifest['samples']}
    if not set(refs).issubset(all_ids) or not set(preds).issubset(all_ids):
        raise ValidationError('unknown sampleId in labels/predictions')
    selected = [sample for sample in manifest['samples'] if sample['split'] == split]
    if not selected:
        raise ValidationError('selected split is empty')
    details, latencies = [], []
    for sample in selected:
        sid = sample['sampleId']
        if sid not in refs or refs[sid].get('reviewed') is not True:
            raise ValidationError('every selected sample needs reviewed ground truth')
        ref = refs[sid]
        text = ref.get('ocrText')
        if not isinstance(text, str) or not normalized(text):
            raise ValidationError('ground truth ocrText must be non-empty')
        if len(text) > 20000:
            raise ValidationError('reference OCR text exceeds 20000 characters')
        receipt = validate_receipt(ref.get('receipt'))
        pred = preds.get(sid, {})
        predicted_text = pred.get('ocrText', '')
        if not isinstance(predicted_text, str) or len(predicted_text) > 20000:
            raise ValidationError('prediction OCR text must be string <= 20000 characters')
        predicted_receipt = pred.get('receipt')
        if predicted_receipt is not None and not isinstance(predicted_receipt, dict):
            raise ValidationError('prediction receipt must be object or null')
        predicted_receipt = predicted_receipt or {}
        items = predicted_receipt.get('items', [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValidationError('prediction items must be an array of objects')
        row_slots = max(len(receipt['items']), len(items))
        matched_rows, money_matches, money_slots = 0, 0, 0
        for index in range(row_slots):
            actual = receipt['items'][index] if index < len(receipt['items']) else None
            guess = items[index] if index < len(items) else {}
            if actual is not None:
                matched_rows += row_equal(actual, guess)
            for field in ('unitPriceVnd', 'lineTotalVnd'):
                # Unknown reference unit price is excluded, never treated as zero.
                if actual is not None and actual.get(field) is None:
                    continue
                money_slots += 1
                money_matches += actual is not None and number_equal(actual.get(field), guess.get(field))
        total_match = number_equal(receipt['printedTotalVnd'], predicted_receipt.get('printedTotalVnd'))
        predicted_adjustments = predicted_receipt.get('adjustments', [])
        adjustment_match = receipt['adjustments'] == predicted_adjustments
        if adjustment_match and receipt['adjustments']:
            adjustment_match = (isinstance(predicted_adjustments, list)
                and all(isinstance(adjustment, dict)
                        and type(adjustment.get('amountVnd')) is int
                        for adjustment in predicted_adjustments))
        # IDs are intentionally excluded from receipt semantic exact match.
        receipt_match = (matched_rows == row_slots and total_match and adjustment_match
                         and predicted_receipt.get('currency') == 'VND')
        elapsed = pred.get('elapsedSeconds')
        if elapsed is not None:
            if type(elapsed) not in (float, int) or not math.isfinite(elapsed) or elapsed < 0:
                raise ValidationError('elapsedSeconds must be finite and nonnegative')
            latencies.append(elapsed)
        reference_text = normalized(text)
        details.append({'sampleId': sid, 'qualityGroup': sample['qualityGroup'],
                        'predictionPresent': sid in preds,
                        'characterErrors': edit_distance(reference_text, normalized(predicted_text)),
                        'referenceCharacters': len(reference_text), 'matchedRows': matched_rows,
                        'rowSlots': row_slots, 'moneyMatches': int(money_matches) + int(total_match),
                        'moneySlots': money_slots + 1, 'totalExact': total_match,
                        'receiptExact': receipt_match})

    def aggregate(records):
        n = len(records)
        denominator = lambda key: sum(row[key] for row in records)
        return {'sampleCount': n, 'predictionCount': sum(row['predictionPresent'] for row in records),
                'cer': denominator('characterErrors') / denominator('referenceCharacters'),
                'itemRowExactMatch': denominator('matchedRows') / denominator('rowSlots'),
                'moneyExactMatch': denominator('moneyMatches') / denominator('moneySlots'),
                'totalExactMatch': denominator('totalExact') / n,
                'receiptExactMatch': denominator('receiptExact') / n,
                'referenceCharacters': denominator('referenceCharacters'),
                'rowSlots': denominator('rowSlots'), 'moneySlots': denominator('moneySlots')}

    groups = {sample['qualityGroup'] for sample in selected}
    return {'schemaVersion': 1, 'manifestSha256': summary['manifestSha256'],
            'datasetVersion': manifest['datasetVersion'], 'runId': predictions['runId'],
            'pipelineVersion': predictions['pipelineVersion'], 'split': split,
            'synthetic': manifest['synthetic'], 'metrics': aggregate(details),
            'latency': {'sampleCount': len(latencies), 'p50Seconds': percentile(latencies, .5),
                        'p95Seconds': percentile(latencies, .95)},
            'byQuality': {group: aggregate([row for row in details if row['qualityGroup'] == group])
                          for group in sorted(groups)}, 'samples': details,
            'warnings': (['SYNTHETIC_NOT_MODEL_ACCURACY'] if manifest['synthetic'] else [])
                        + (['SMALL_EVALUATION_SET'] if len(selected) < 30 else [])}
