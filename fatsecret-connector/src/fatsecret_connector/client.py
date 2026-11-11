"""FatSecret HTTP transport; never logs signed URLs or credentials."""
import json
import os
from datetime import date

import requests
from requests_oauthlib import OAuth1Session

from .config import Settings

BASE = 'https://platform.fatsecret.com/rest/'


def days(value):
    return (date.fromisoformat(value) - date(1970, 1, 1)).days


class FatSecretClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def session(self, token=None, *, callback_uri=None, verifier=None, signature_type='AUTH_HEADER'):
        key = self.settings.consumer_key
        secret = self.settings.consumer_secret
        if not key or not secret:
            raise RuntimeError('Set FATSECRET_CONSUMER_KEY and FATSECRET_CONSUMER_SECRET in .env')
        token = token or {}
        return OAuth1Session(key, client_secret=secret, callback_uri=callback_uri, verifier=verifier,
                             signature_type=signature_type,
                             resource_owner_key=token.get('oauth_token'),
                             resource_owner_secret=token.get('oauth_token_secret'))

    def api(self, path, params, write=False, *, method: str | None = None):
        method = method or ('POST' if write else 'GET')
        if method not in ('GET', 'POST', 'DELETE'):
            raise ValueError('Unsupported HTTP method')
        if os.environ.get('EDA_DATABASE_URL'):
            from eda_state import load_state
            token = load_state('fatsecret_token')
            if not token:
                raise RuntimeError('FatSecret authorization is missing; import credentials or authorize first')
        else:
            if not self.settings.token_file.exists():
                raise RuntimeError('Run python authorize.py first')
            token = json.loads(self.settings.token_file.read_text(encoding='utf-8'))
        s = self.session(token)
        try:
            # No retry: a failed POST or DELETE may already have changed the diary.
            parameters = {**params, 'format': 'json'}
            if method == 'POST':
                response = s.post(BASE + path, data=parameters, timeout=30)
            elif method == 'DELETE':
                response = s.delete(BASE + path, params=parameters, timeout=30)
            else:
                response = s.get(BASE + path, params=parameters, timeout=30)
            if response.status_code >= 400:
                raise RuntimeError(f'FatSecret HTTP {response.status_code}; check API permissions and authorization')
            try:
                payload = response.json()
            except ValueError:
                raise RuntimeError('FatSecret returned a non-JSON response') from None
            if 'error' in payload:
                raise RuntimeError(f"FatSecret API error {payload['error'].get('code', 'unknown')}; consult official error codes")
            return payload
        except requests.RequestException:
            raise RuntimeError('FatSecret connection failed. For writes, read diary before retrying: outcome may be unknown.') from None
        finally:
            s.close()
