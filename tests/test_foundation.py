import copy
import json
import random
import subprocess
import sys
import unittest
from pathlib import Path

from dontlift_bill.allocation import preview
from dontlift_bill.domain import ValidationError, validate_receipt

ROOT = Path(__file__).resolve().parents[1]


def example(name):
    return json.loads((ROOT / 'examples' / f'{name}.synthetic.json').read_text(encoding='utf-8'))


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.receipt = example('receipt')
        self.plan = example('plan')
        self.members = example('members')

    def test_shared_example(self):
        result = preview(self.receipt, self.plan, self.members)
        self.assertEqual([s['shareVnd'] for s in result['shares']], [41500, 41500])
        self.assertFalse(result['authoritative'])

    def test_person_drinks_both_teas(self):
        self.plan['allocations'][1]['members'] = [{'memberUid': 'a', 'weight': 1}]
        self.assertEqual([s['shareVnd'] for s in preview(self.receipt, self.plan, self.members)['shares']],
                         [53500, 29500])

    def test_fractional_quantity(self):
        self.receipt['items'][0]['quantity'] = {'numerator': 1, 'denominator': 2}
        self.receipt['items'][0]['unitPriceVnd'] = 118000
        validate_receipt(self.receipt)

    def test_malformed_inputs(self):
        for field, value in [('revision', True), ('currency', 'USD'), ('printedTotalVnd', 85000),
                             ('items', []), ('adjustments', None)]:
            with self.subTest(field=field):
                receipt = copy.deepcopy(self.receipt)
                receipt[field] = value
                with self.assertRaises(ValidationError):
                    validate_receipt(receipt)

    def test_price_mismatch(self):
        self.receipt['items'][0]['unitPriceVnd'] = 58000
        with self.assertRaises(ValidationError):
            validate_receipt(self.receipt)

    def test_invalid_plans(self):
        cases = []
        stale = copy.deepcopy(self.plan)
        stale['receiptRevision'] = 2
        cases.append(stale)
        missing = copy.deepcopy(self.plan)
        missing['allocations'].pop()
        cases.append(missing)
        duplicate = copy.deepcopy(self.plan)
        duplicate['allocations'].append(copy.deepcopy(duplicate['allocations'][0]))
        cases.append(duplicate)
        for uid, weight in [('unknown', 1), ('a', True), ('a', 0), ('a', -1)]:
            invalid = copy.deepcopy(self.plan)
            invalid['allocations'][0]['members'] = [{'memberUid': uid, 'weight': weight}]
            cases.append(invalid)
        for plan in cases:
            with self.subTest(plan=plan), self.assertRaises(ValidationError):
                preview(self.receipt, plan, self.members)

    def test_duplicate_members(self):
        with self.assertRaises(ValidationError):
            preview(self.receipt, self.plan, ['a', 'a'])

    def test_included_tax_not_added_twice(self):
        self.receipt['adjustments'] = [{'adjustmentId': 'tax', 'kind': 'TAX', 'amountVnd': 8300,
                                       'effect': 'INCLUDED', 'allocationPolicy': 'PROPORTIONAL'}]
        self.assertEqual(preview(self.receipt, self.plan, self.members)['totalVnd'], 83000)

    def test_discount_and_fee(self):
        self.receipt['adjustments'] = [
            {'adjustmentId': 'discount', 'kind': 'DISCOUNT', 'amountVnd': 10000,
             'effect': 'SUBTRACT', 'allocationPolicy': 'PROPORTIONAL'},
            {'adjustmentId': 'fee', 'kind': 'SERVICE_CHARGE', 'amountVnd': 3001,
             'effect': 'ADD', 'allocationPolicy': 'EQUAL'}]
        self.receipt['printedTotalVnd'] = 76001
        self.assertEqual([s['shareVnd'] for s in preview(self.receipt, self.plan, self.members)['shares']],
                         [38001, 38000])

    def test_negative_share_rejected(self):
        for allocation in self.plan['allocations']:
            allocation['members'] = [{'memberUid': 'a', 'weight': 1}]
        self.receipt['adjustments'] = [{'adjustmentId': 'discount', 'kind': 'DISCOUNT',
                                       'amountVnd': 1000, 'effect': 'SUBTRACT', 'allocationPolicy': 'EQUAL'}]
        self.receipt['printedTotalVnd'] = 82000
        with self.assertRaises(ValidationError):
            preview(self.receipt, self.plan, self.members)

    def test_generated_conservation_and_order_independence(self):
        rng = random.Random(20261014)
        for _ in range(200):
            total = rng.randint(1000, 10**16)
            members = [f'user-{i:02}' for i in range(rng.randint(1, 20))]
            receipt = copy.deepcopy(self.receipt)
            receipt['items'] = [{'itemId': 'x', 'name': 'Synthetic', 'quantity': {'numerator': 1, 'denominator': 1},
                                 'unitPriceVnd': total, 'lineTotalVnd': total}]
            receipt['printedTotalVnd'] = total
            plan = copy.deepcopy(self.plan)
            allocations = [{'memberUid': uid, 'weight': rng.randint(1, 100)} for uid in members]
            plan['allocations'] = [{'itemId': 'x', 'members': allocations}]
            result = preview(receipt, plan, members)
            self.assertEqual(sum(s['shareVnd'] for s in result['shares']), total)
            self.assertTrue(all(s['shareVnd'] >= 0 for s in result['shares']))
            rng.shuffle(members)
            rng.shuffle(allocations)
            self.assertEqual(result, preview(receipt, plan, members))

    def test_cli_success_and_failure(self):
        result = subprocess.run([sys.executable, '-m', 'dontlift_bill.cli', 'preview',
                                 str(ROOT / 'examples/receipt.synthetic.json'),
                                 str(ROOT / 'examples/plan.synthetic.json'),
                                 str(ROOT / 'examples/members.synthetic.json')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['totalVnd'], 83000)
        result = subprocess.run([sys.executable, '-m', 'dontlift_bill.cli', 'validate',
                                 str(ROOT / 'examples/members.synthetic.json')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('error', json.loads(result.stderr))


if __name__ == '__main__':
    unittest.main()
