import unittest
from unittest.mock import Mock

from fatsecret_connector.client import FatSecretClient
from fatsecret_connector.tools.diary import DiaryTools


class DiaryTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock(spec=FatSecretClient)
        self.diary = DiaryTools(self.client)

    def test_diary_date(self):
        self.diary.get_diary('1970-01-02')
        self.client.api.assert_called_once_with('food-entries/v2', {'date': 1})

    def test_invalid_date_does_not_call_api(self):
        with self.assertRaises(ValueError):
            self.diary.get_diary('2026-02-30')
        self.client.api.assert_not_called()

    def test_reject_bad_serving_before_write(self):
        self.client.api.return_value = {
            'food': {'servings': {'serving': [{'serving_id': '2'}]}}}
        with self.assertRaises(ValueError):
            self.diary.add_food('2026-11-08', 'lunch', '1', '3', 1, 'Food')
        self.client.api.assert_called_once_with('food/v6', {'food_id': '1'})

    def test_invalid_inputs_before_api(self):
        cases = [
            ('2026-11-08', 'lunch', '1', '2', amount, 'Food')
            for amount in (0, -1, float('nan'), float('inf'))
        ]
        cases.extend([
            ('2026-02-30', 'lunch', '1', '2', 1, 'Food'),
            ('2026-11-08', 'invalid', '1', '2', 1, 'Food'),
            ('2026-11-08', 'lunch', 'abc', '2', 1, 'Food'),
            ('2026-11-08', 'lunch', '1', '2', 1, '  '),
        ])
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.diary.add_food(*args)
        self.client.api.assert_not_called()

    def test_write_once_for_single_or_multiple_servings(self):
        for serving in ({'serving_id': '2'}, [{'serving_id': '2'}]):
            with self.subTest(serving=serving):
                self.client.api.reset_mock()
                self.client.api.side_effect = [
                    {'food': {'servings': {'serving': serving}}},
                    {'food_entry_id': {'value': '10'}},
                ]
                result = self.diary.add_food('2026-11-08', 'lunch', '1', '2', 1.5, 'Food')
                self.assertEqual(result['food_entry_id']['value'], '10')
                self.assertEqual(self.client.api.call_count, 2)
                self.client.api.assert_called_with('food-entries/v1', {
                    'date': 20765, 'meal': 'lunch', 'food_id': '1',
                    'serving_id': '2', 'number_of_units': '1.5', 'food_entry_name': 'Food',
                }, write=True)

    def test_delete_invalid_inputs_before_api(self):
        for entry_id in ('', '0', '-1', '1.5', 'abc', ' 10 ', '+10', '١',
                         '9223372036854775808'):
            with self.subTest(entry_id=entry_id), self.assertRaises(ValueError):
                self.diary.delete_food('2026-11-08', entry_id)
        with self.assertRaises(ValueError):
            self.diary.delete_food('2026-02-30', '10')
        self.client.api.assert_not_called()

    def test_delete_once_for_single_or_multiple_entries(self):
        entry = {'food_entry_id': '10', 'date_int': '20765'}
        for entries in (entry, [entry, {'food_entry_id': '11', 'date_int': '20765'}]):
            with self.subTest(entries=entries):
                self.client.api.reset_mock()
                self.client.api.side_effect = [
                    {'food_entries': {'food_entry': entries}},
                    {'success': {'value': '1'}},
                ]
                result = self.diary.delete_food('2026-11-08', '10')
                self.assertEqual(result, {'success': {'value': '1'}})
                self.assertEqual(self.client.api.call_count, 2)
                self.assertEqual(self.client.api.call_args_list[0].args,
                                 ('food-entries/v2', {'date': 20765}))
                self.client.api.assert_called_with(
                    'food-entries/v1', {'food_entry_id': '10'}, method='DELETE')

    def test_delete_rejects_missing_entry_or_wrong_date(self):
        for payload in ({}, {'food_entries': None}, {'food_entries': ''},
                        {'food_entries': {}}, {'food_entries': {'food_entry': []}},
                        {'food_entries': {'food_entry': None}},
                        {'food_entries': {'food_entry': [
                            {'food_entry_id': '11', 'date_int': '20765'}]}},
                        {'food_entries': {'food_entry': [
                            {'food_entry_id': '10', 'date_int': '20764'}]}},
                        {'food_entries': {'food_entry': [{'food_entry_id': '10'}]}}):
            with self.subTest(payload=payload):
                self.client.api.reset_mock()
                self.client.api.return_value = payload
                with self.assertRaises(ValueError):
                    self.diary.delete_food('2026-11-08', '10')
                self.client.api.assert_called_once_with('food-entries/v2', {'date': 20765})

    def test_delete_stops_after_read_failure(self):
        self.client.api.side_effect = RuntimeError('Read failed')
        with self.assertRaisesRegex(RuntimeError, 'Read failed'):
            self.diary.delete_food('2026-11-08', '10')
        self.client.api.assert_called_once_with('food-entries/v2', {'date': 20765})

    def test_delete_failure_is_not_retried(self):
        self.client.api.side_effect = [
            {'food_entries': {'food_entry': [
                {'food_entry_id': '10', 'date_int': '20765'}]}},
            RuntimeError('Outcome may be unknown'),
        ]
        with self.assertRaisesRegex(RuntimeError, 'Outcome may be unknown'):
            self.diary.delete_food('2026-11-08', '10')
        self.assertEqual(self.client.api.call_count, 2)
        self.client.api.assert_called_with(
            'food-entries/v1', {'food_entry_id': '10'}, method='DELETE')
