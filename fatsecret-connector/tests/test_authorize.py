import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qsl, urlsplit

import requests
from requests_oauthlib.oauth1_session import TokenRequestDenied

from fatsecret_connector import authorize
from fatsecret_connector.config import Settings


class AuthorizationTests(unittest.TestCase):
    def test_errors_report_codes_without_response_secrets(self):
        cases = (
            ('oauth_problem=consumer_key_unknown&oauth_token=private-token',
             'oauth_problem=consumer_key_unknown'),
            ('{"error":{"code":"5","message":"private-token"}}',
             'FatSecret code 5: Invalid consumer key'),
            ('<error xmlns="http://platform.fatsecret.com/api/1.0/">'
             '<code>8</code><message>private-token</message></error>',
             'FatSecret code 8: Invalid signature'),
            ('<error><code>6</code><message>private-token</message></error>',
             'FatSecret code 6: Invalid or expired timestamp'),
            ('oauth_problem=private-token', 'No recognized error code'),
            ('<html>private-token</html>', 'No recognized error code'),
            ('{"error":"private-token"}', 'No recognized error code'),
        )
        for body, expected in cases:
            with self.subTest(expected=expected):
                response = requests.Response()
                response.status_code = 400
                response._content = body.encode('utf-8')
                error = TokenRequestDenied('private-token', response)
                message = authorize.authorization_error(error)
                self.assertIn('HTTP 400', message)
                self.assertIn(expected, message)
                self.assertNotIn('private-token', message)

    def test_network_error_does_not_expose_signed_url(self):
        message = authorize.authorization_error(requests.ConnectionError(
            'https://example.com/?oauth_token=private-token'))
        self.assertIn('ConnectionError', message)
        self.assertNotIn('private-token', message)

    def test_signed_requests_and_saved_access_token(self):
        responses = []
        for body in (
            'oauth_token=request-token&oauth_token_secret=request-secret&oauth_callback_confirmed=true',
            'oauth_token=access-token&oauth_token_secret=access-secret',
        ):
            response = requests.Response()
            response.status_code = 200
            response._content = body.encode('ascii')
            responses.append(response)

        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / '.tokens.json'
            with patch.dict(os.environ, {
                'FATSECRET_CONSUMER_KEY': 'test-key',
                'FATSECRET_CONSUMER_SECRET': 'test-secret',
            }), \
                    patch('requests.sessions.Session.send', side_effect=responses) as send, \
                    patch('fatsecret_connector.authorize.getpass.getpass', return_value='test-verifier'), \
                    patch('builtins.print') as output:
                authorize.main(Settings('test-key', 'test-secret', token_file))

            self.assertEqual(send.call_count, 2)
            request = send.call_args_list[0].args[0]
            self.assertEqual(request.method, 'GET')
            self.assertEqual(request.url.split('?')[0],
                             'https://authentication.fatsecret.com/oauth/request_token')
            params = dict(parse_qsl(urlsplit(request.url).query))
            self.assertEqual(params['oauth_callback'], 'oob')
            self.assertEqual(params['oauth_consumer_key'], 'test-key')
            self.assertEqual(params['oauth_signature_method'], 'HMAC-SHA1')
            self.assertTrue(params['oauth_signature'])
            self.assertNotIn('Authorization', request.headers)
            self.assertNotIn('oauth_token', params)
            output.assert_any_call(
                'https://authentication.fatsecret.com/oauth/authorize?oauth_token=request-token')
            exchange = send.call_args_list[1].args[0]
            self.assertEqual(exchange.method, 'GET')
            self.assertEqual(exchange.url.split('?')[0],
                             'https://authentication.fatsecret.com/oauth/access_token')
            params = dict(parse_qsl(urlsplit(exchange.url).query))
            self.assertEqual(params['oauth_verifier'], 'test-verifier')
            self.assertEqual(params['oauth_token'], 'request-token')
            self.assertTrue(params['oauth_signature'])
            self.assertNotIn('oauth_callback', params)
            self.assertNotIn('Authorization', exchange.headers)
            self.assertEqual(json.loads(token_file.read_text()), {
                'oauth_token': 'access-token',
                'oauth_token_secret': 'access-secret',
            })


    def test_failed_token_exchange_does_not_save_or_retry(self):
        for phase in ('request', 'access'):
            for status, body in ((400, 'private-token'),
                                 (200, 'oauth_token=private-token'),
                                 (200, 'oauth_token=&oauth_token_secret=private-token')):
                with self.subTest(phase=phase, status=status, body=body), \
                        tempfile.TemporaryDirectory() as directory:
                    token_file = Path(directory) / '.tokens.json'
                    failure = requests.Response()
                    failure.status_code = status
                    failure._content = body.encode('ascii')
                    responses = [failure]
                    if phase == 'access':
                        success = requests.Response()
                        success.status_code = 200
                        success._content = b'oauth_token=request-token&oauth_token_secret=request-secret'
                        responses.insert(0, success)
                    with patch.dict(os.environ, {
                        'FATSECRET_CONSUMER_KEY': 'test-key',
                        'FATSECRET_CONSUMER_SECRET': 'test-secret',
                    }), \
                            patch('requests.sessions.Session.send', side_effect=responses) as send, \
                            patch('fatsecret_connector.authorize.getpass.getpass', return_value='test-verifier') as prompt, \
                            patch('builtins.print'):
                        with self.assertRaises((requests.HTTPError, ValueError)) as error:
                            authorize.main(Settings('test-key', 'test-secret', token_file))
                    self.assertEqual(send.call_count, len(responses))
                    self.assertFalse(token_file.exists())
                    self.assertNotIn('private-token', authorize.authorization_error(error.exception))
                    if phase == 'request':
                        prompt.assert_not_called()

    def test_existing_token_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / '.tokens.json'
            token_file.write_text('existing-token')
            with patch.object(authorize.FatSecretClient, 'session') as session:
                with self.assertRaises(SystemExit):
                    authorize.main(Settings('test-key', 'test-secret', token_file))
            session.assert_not_called()
            self.assertEqual(token_file.read_text(), 'existing-token')


if __name__ == '__main__':
    unittest.main()
