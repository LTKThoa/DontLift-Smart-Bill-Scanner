import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from dontlift_bill.dataset import manifest_hash, validate_manifest
from dontlift_bill.domain import ValidationError
from dontlift_bill.evaluation import edit_distance, evaluate, prediction_from_draft
from dontlift_bill.extraction import extract_draft
from test_foundation import example
from test_pipeline import document


def bundles():
    samples = []
    for sid, split in [('a', 'train'), ('b', 'validation'), ('c', 'test'), ('d', 'test')]:
        samples.append({'sampleId': sid, 'imageSha256': hashlib.sha256(sid.encode()).hexdigest(),
                        'merchantGroup': sid, 'templateGroup': sid, 'familyGroup': sid,
                        'qualityGroup': 'clear' if sid != 'd' else 'blurred', 'split': split,
                        'rightsConfirmed': True, 'source': 'synthetic',
                        'reviewStatus': 'REVIEWED', 'annotationVersion': 'v1'})
    manifest = {'schemaVersion': 1, 'datasetVersion': 'synthetic-v1', 'synthetic': True,
                'samples': samples}
    digest = manifest_hash(manifest)
    labels = {'schemaVersion': 1, 'manifestSha256': digest,
              'samples': [{'sampleId': sid, 'reviewed': True, 'ocrText': 'Trà 12.000',
                           'receipt': example('receipt')} for sid in ('c', 'd')]}
    predictions = {'schemaVersion': 1, 'manifestSha256': digest, 'runId': 'synthetic-run',
                   'pipelineVersion': 'test-v1', 'samples': [
                       {'sampleId': label['sampleId'], 'ocrText': label['ocrText'],
                        'receipt': copy.deepcopy(label['receipt']), 'elapsedSeconds': i+1}
                       for i, label in enumerate(labels['samples'])]}
    return manifest, labels, predictions


class DatasetTests(unittest.TestCase):
    def test_hash_is_order_independent(self):
        manifest, _, _ = bundles()
        digest = manifest_hash(manifest)
        manifest['samples'].reverse()
        self.assertEqual(digest, manifest_hash(manifest))
        manifest['datasetVersion'] = 'new'
        self.assertNotEqual(digest, manifest_hash(manifest))

    def test_leakage_by_each_group(self):
        for field in ('merchantGroup', 'templateGroup', 'familyGroup'):
            manifest, _, _ = bundles()
            manifest['samples'][1][field] = manifest['samples'][0][field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_manifest(manifest)

    def test_duplicate_hash_and_unreviewed_data_rejected(self):
        for field, value in [('imageSha256', hashlib.sha256(b'a').hexdigest()),
                             ('reviewStatus', 'PENDING'), ('rightsConfirmed', False)]:
            manifest, _, _ = bundles()
            manifest['samples'][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_manifest(manifest)

    def test_image_hash_and_path_boundary(self):
        manifest, _, _ = bundles()
        manifest['samples'] = manifest['samples'][:1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'sample.bin').write_bytes(b'a')
            manifest['samples'][0]['imagePath'] = 'sample.bin'
            self.assertEqual(validate_manifest(manifest, root, True)['imagesVerified'], 1)
            manifest['samples'][0]['imagePath'] = '../outside.bin'
            with self.assertRaises(ValidationError):
                validate_manifest(manifest, root, True)


class EvaluationTests(unittest.TestCase):
    def test_export_requires_matching_image_and_uncorrected_draft(self):
        manifest, _, _ = bundles()
        draft = extract_draft(document(['Trà 12.000 x 2 24.000', 'Tổng cộng 24.000']))
        draft['ocrDocument']['imageId'] = manifest['samples'][2]['imageSha256']
        result = prediction_from_draft(manifest, draft, 'c', 'run', 'v1')
        self.assertEqual(result['samples'][0]['receipt']['printedTotalVnd'], 24000)
        with self.assertRaises(ValidationError):
            prediction_from_draft(manifest, draft, 'd', 'run', 'v1')
        draft['reviewStatus'] = 'LOCALLY_REVIEWED'
        with self.assertRaises(ValidationError):
            prediction_from_draft(manifest, draft, 'c', 'run', 'v1')
    def test_perfect_metrics_and_subgroups(self):
        report = evaluate(*bundles())
        self.assertEqual(report['metrics']['cer'], 0)
        self.assertEqual(report['metrics']['receiptExactMatch'], 1)
        self.assertEqual(report['metrics']['itemRowExactMatch'], 1)
        self.assertEqual(report['byQuality']['blurred']['sampleCount'], 1)
        self.assertEqual(report['latency']['p95Seconds'], 2)
        self.assertIn('SYNTHETIC_NOT_MODEL_ACCURACY', report['warnings'])

    def test_missing_predictions_count_as_failures(self):
        manifest, labels, predictions = bundles()
        predictions['samples'].pop()
        report = evaluate(manifest, labels, predictions)
        self.assertEqual(report['metrics']['sampleCount'], 2)
        self.assertEqual(report['metrics']['predictionCount'], 1)
        self.assertEqual(report['metrics']['totalExactMatch'], .5)
        self.assertEqual(report['metrics']['cer'], .5)
        self.assertEqual(report['latency']['sampleCount'], 1)

    def test_all_predictions_missing(self):
        manifest, labels, predictions = bundles()
        predictions['samples'] = []
        report = evaluate(manifest, labels, predictions)
        self.assertEqual(report['metrics']['cer'], 1)
        self.assertEqual(report['metrics']['receiptExactMatch'], 0)
        self.assertIsNone(report['latency']['p95Seconds'])

    def test_extra_and_wrong_rows_penalized(self):
        manifest, labels, predictions = bundles()
        predictions['samples'][0]['receipt']['items'].append(example('receipt')['items'][0])
        predictions['samples'][1]['receipt']['items'][0]['lineTotalVnd'] = 1
        report = evaluate(manifest, labels, predictions)
        self.assertEqual(report['metrics']['rowSlots'], 5)
        self.assertEqual(report['metrics']['itemRowExactMatch'], 3/5)
        self.assertEqual(report['metrics']['receiptExactMatch'], 0)

    def test_boolean_money_is_not_equal_to_integer(self):
        manifest, labels, predictions = bundles()
        predictions['samples'][0]['receipt']['printedTotalVnd'] = True
        self.assertEqual(evaluate(manifest, labels, predictions)['metrics']['totalExactMatch'], .5)

    def test_mismatched_manifest_or_missing_labels_rejected(self):
        for mismatch in ('hash', 'label', 'unknown', 'duplicate'):
            manifest, labels, predictions = bundles()
            if mismatch == 'hash':
                predictions['manifestSha256'] = 'incorrect'
            elif mismatch == 'label':
                labels['samples'].pop()
            elif mismatch == 'unknown':
                predictions['samples'][0]['sampleId'] = 'unknown'
            else:
                predictions['samples'].append(predictions['samples'][0])
            with self.subTest(mismatch=mismatch), self.assertRaises(ValidationError):
                evaluate(manifest, labels, predictions)

    def test_text_normalization_is_unicode_aware_and_case_sensitive(self):
        manifest, labels, predictions = bundles()
        predictions['samples'][0]['ocrText'] = 'Tra\u0300   12.000'
        self.assertEqual(evaluate(manifest, labels, predictions)['metrics']['cer'], 0)
        self.assertEqual(edit_distance('abc', 'aBc'), 1)
