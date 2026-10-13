import copy
import unittest
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from dontlift_bill.domain import ValidationError
from dontlift_bill.extraction import extract_draft
from dontlift_bill.review import review_draft
from test_foundation import example


def document(lines):
    return {'schemaVersion': 1, 'imageId': 'synthetic-receipt-001', 'width': 1000, 'height': 1000,
            'coordinates': 'exif-oriented-image-pixels',
            'sourceTransform': {'exifOrientation': 1, 'originalSize': [1000, 1000]},
            'engine': {'name': 'synthetic', 'version': '1', 'runtimeVersion': '1', 'language': 'latin', 'modelHashes': []},
            'elapsedSeconds': 0,
            'tokens': [{'tokenId': f't{i}', 'text': text, 'confidence': .9,
                        'polygon': [[0, i*40], [900, i*40], [900, i*40+20], [0, i*40+20]]}
                       for i, text in enumerate(lines)]}


class PipelineTests(unittest.TestCase):
    def test_row_parse_and_provenance(self):
        draft = extract_draft(document(['1) Món chung 59.000 x 1 59.000',
                                        '2) Trà 12,000 x 2 24,000', 'Tổng Cộng: 83,000']))
        self.assertEqual(len(draft['items']), 2)
        self.assertEqual(draft['printedTotalVnd']['value'], 83000)
        self.assertEqual(draft['discrepancyVnd'], 0)
        self.assertEqual(draft['items'][1]['quantity']['value']['numerator'], 2)
        self.assertEqual(draft['items'][1]['name']['sourceTokenIds'], ['t1'])
        self.assertEqual(draft['reviewStatus'], 'NEEDS_REVIEW')

    def test_ambiguous_total_is_not_selected(self):
        draft = extract_draft(document(['Tổng cộng 83.000', 'Tổng cộng 85.000']))
        self.assertIsNone(draft['printedTotalVnd']['value'])
        self.assertIn('TOTAL_MISSING_OR_AMBIGUOUS', draft['warnings'])

    def test_unparsed_receipt_does_not_invent_items(self):
        draft = extract_draft(document(['Tài khoản 123456789', 'Trà bị mờ']))
        self.assertEqual(draft['items'], [])
        self.assertIsNone(draft['computedTotalVnd'])

    def test_invalid_ocr_tokens_rejected(self):
        for change in ('duplicate', 'nan', 'polygon'):
            invalid = document(['A', 'B'])
            if change == 'duplicate':
                invalid['tokens'][1]['tokenId'] = 't0'
            elif change == 'nan':
                invalid['tokens'][0]['confidence'] = float('nan')
            else:
                invalid['tokens'][0]['polygon'] = []
            with self.subTest(change=change), self.assertRaises(ValidationError):
                extract_draft(invalid)

    def test_split_columns_preserve_unreadable_price(self):
        doc = document([])
        for i, text in enumerate(['1) Món chung', '590C0', '1', '59,000']):
            doc['tokens'].append({'tokenId': f't{i}', 'text': text, 'confidence': .8,
                                  'polygon': [[i*200, 0], [i*200+100, 0], [i*200+100, 20], [i*200, 20]]})
        draft = extract_draft(doc)
        self.assertEqual(len(draft['items']), 1)
        self.assertIsNone(draft['items'][0]['unitPriceVnd']['value'])
        self.assertEqual(draft['items'][0]['lineTotalVnd']['value'], 59000)
        self.assertIn('UNIT_PRICE_UNREADABLE:item-001', draft['warnings'])

    def test_mismatches_require_review(self):
        draft = extract_draft(document(['Trà 12.000 x 2 25.000', 'Tổng cộng 30.000']))
        self.assertIn('PRICE_MISMATCH:item-001', draft['warnings'])
        self.assertIn('TOTAL_MISMATCH', draft['warnings'])

    def test_explicit_correction_and_stale_revision(self):
        draft = extract_draft(document([]))
        receipt = example('receipt')
        receipt['revision'] = 2
        correction = {'expectedRevision': 1, 'confirmed': True, 'receipt': receipt}
        result = review_draft(draft, correction)
        self.assertEqual(result['receipt']['revision'], 2)
        self.assertFalse(result['authoritative'])
        self.assertEqual(result['provenance']['originalDraft'], draft)
        for key, value in [('expectedRevision', 2), ('confirmed', False)]:
            invalid = copy.deepcopy(correction)
            invalid[key] = value
            with self.assertRaises(ValidationError):
                review_draft(draft, invalid)

    def test_schemas_accept_generated_draft(self):
        try:
            import jsonschema
            from referencing import Registry, Resource
        except ImportError:
            self.skipTest('install dev extra to validate JSON schemas')
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / 'schemas'
        schema = json.loads((root / 'receipt-draft.schema.json').read_text())
        ocr = json.loads((root / 'ocr-document.schema.json').read_text())
        registry = Registry().with_resource('ocr-document.schema.json', Resource.from_contents(ocr))
        validator = jsonschema.Draft202012Validator(schema, registry=registry)
        validator.validate(extract_draft(document(['Trà 12.000 x 2 24.000', 'Tổng cộng 24.000'])))
        invalid = extract_draft(document([]))
        invalid['revision'] = True
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(invalid)

    def test_review_cli_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = extract_draft(document([]))
            receipt = example('receipt')
            receipt['revision'] = 2
            correction = {'expectedRevision': 1, 'confirmed': True, 'receipt': receipt}
            (root / 'draft.json').write_text(json.dumps(draft), encoding='utf-8')
            (root / 'correction.json').write_text(json.dumps(correction), encoding='utf-8')
            command = [sys.executable, '-m', 'dontlift_bill.cli', 'review', str(root / 'draft.json'),
                       str(root / 'correction.json'), '--output', str(root / 'reviewed.json')]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = (root / 'reviewed.json').read_bytes()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual((root / 'reviewed.json').read_bytes(), original)
