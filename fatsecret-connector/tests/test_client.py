import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from fatsecret_connector.client import FatSecretClient, days
from fatsecret_connector.config import Settings


class ClientTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.token_file = Path(directory.name) / '.tokens.json'
        self.token_file.write_text(json.dumps({
            'oauth_token': 'test-token', 'oauth_token_secret': 'test-token-secret',
        }), encoding='utf-8')
        self.client = FatSecretClient(Settings('test-key', 'test-secret', self.token_file))

    def test_dates(self):
        self.assertEqual(days('1970-01-01'), 0)
        with self.assertRaises(ValueError):
            days('2026-02-30')

    def test_api_request_uses_header_signature(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"foods": []}'
        with patch('requests.sessions.Session.send', return_value=response) as send:
            self.assertEqual(self.client.api('foods/search/v1', {'search_expression': 'milk'}),
                             {'foods': []})
        request = send.call_args.args[0]
        self.assertEqual(request.method, 'GET')
        self.assertIn(b'oauth_token="test-token"', request.headers['Authorization'])
        self.assertNotIn('oauth_signature=', request.url)
        self.assertIn('format=json', request.url)

    def test_uncertain_write_is_not_retried(self):
        with patch.object(self.client, 'session') as factory:
            session = factory.return_value
            session.post.side_effect = requests.Timeout('private-signed-url')
            with self.assertRaisesRegex(RuntimeError, 'outcome may be unknown') as error:
                self.client.api('food-entries/v1', {'food_id': '1'}, write=True)
            session.post.assert_called_once()
            session.get.assert_not_called()
            session.close.assert_called_once()
            self.assertNotIn('private-signed-url', str(error.exception))

    def test_error_responses_close_session_without_exposing_body(self):
        for status, payload, json_error in (
            (403, None, False),
            (200, {'error': {'code': '5', 'message': 'private-secret'}}, False),
            (200, None, True),
        ):
            with self.subTest(status=status, json_error=json_error):
                response = Mock(status_code=status)
                if json_error:
                    response.json.side_effect = ValueError('private-secret')
                else:
                    response.json.return_value = payload
                with patch.object(self.client, 'session') as factory:
                    factory.return_value.get.return_value = response
                    with self.assertRaises(RuntimeError) as error:
                        self.client.api('food/v6', {'food_id': '1'})
                    factory.return_value.close.assert_called_once()
                    self.assertNotIn('private-secret', str(error.exception))

    def test_missing_token_does_not_open_session(self):
        client = FatSecretClient(Settings('test-key', 'test-secret',
                                         self.token_file.with_name('missing.json')))
        with patch.object(client, 'session') as session:
            with self.assertRaises(RuntimeError):
                client.api('food/v6', {'food_id': '1'})
            session.assert_not_called()

    def test_delete_request_uses_header_signature_and_entry_id(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"success": {"value": "1"}}'
        with patch('requests.sessions.Session.send', return_value=response) as send:
            result = self.client.api('food-entries/v1', {'food_entry_id': '10'},
                                     method='DELETE')
        self.assertEqual(result, {'success': {'value': '1'}})
        send.assert_called_once()
        request = send.call_args.args[0]
        self.assertEqual(request.method, 'DELETE')
        self.assertIn('/rest/food-entries/v1?', request.url)
        self.assertIn('food_entry_id=10', request.url)
        self.assertIn('format=json', request.url)
        self.assertIn(b'oauth_token="test-token"', request.headers['Authorization'])
        self.assertNotIn('oauth_signature=', request.url)
        self.assertIsNone(request.body)

    def test_uncertain_delete_is_not_retried(self):
        with patch.object(self.client, 'session') as factory:
            session = factory.return_value
            session.delete.side_effect = requests.Timeout('private-signed-url')
            with self.assertRaisesRegex(RuntimeError, 'outcome may be unknown') as error:
                self.client.api('food-entries/v1', {'food_entry_id': '10'}, method='DELETE')
            session.delete.assert_called_once()
            session.post.assert_not_called()
            session.get.assert_not_called()
            session.close.assert_called_once()
            self.assertNotIn('private-signed-url', str(error.exception))

    def test_delete_api_errors_close_session(self):
        with patch.object(self.client, 'session') as factory:
            session = factory.return_value
            session.delete.return_value = Mock(status_code=200)
            session.delete.return_value.json.return_value = {
                'error': {'code': '5', 'message': 'private-secret'}}
            with self.assertRaisesRegex(RuntimeError, 'API error 5') as error:
                self.client.api('food-entries/v1', {'food_entry_id': '10'}, method='DELETE')
            session.delete.assert_called_once()
            session.close.assert_called_once()
            self.assertNotIn('private-secret', str(error.exception))
