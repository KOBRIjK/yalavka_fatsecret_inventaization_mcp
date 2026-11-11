"""Run once on your own computer. Secrets stay in .env / .tokens.json."""
import argparse
import getpass
import json
import os
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl
from pathlib import Path

from .client import FatSecretClient
from .config import Settings, load_settings


ERROR_CODES = {
    '2': 'Missing required OAuth parameter',
    '3': 'Unsupported OAuth parameter',
    '4': 'Invalid signature method',
    '5': 'Invalid consumer key; check your OAuth 1.0 credentials',
    '6': 'Invalid or expired timestamp; synchronize the computer clock',
    '7': 'Invalid or reused nonce',
    '8': 'Invalid signature; check the matching Consumer Key and Consumer Secret',
    '9': 'Invalid access token',
    '11': 'Application request limit reached',
    '20': 'FatSecret temporarily unavailable',
    '21': 'Invalid IP address; check application IP restrictions',
    '22': 'Invalid request',
}
OAUTH_PROBLEMS = {
    'parameter_absent', 'parameter_rejected', 'signature_invalid',
    'signature_method_rejected', 'consumer_key_unknown', 'consumer_key_rejected',
    'timestamp_refused', 'nonce_used', 'permission_unknown', 'permission_denied',
    'version_rejected', 'token_rejected', 'token_expired',
}


def authorization_error(exc):
    """Report allowlisted error codes, never raw responses or exception messages."""
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None)
    detail = type(exc).__name__
    if isinstance(status, int):
        detail += f', HTTP {status}'
    reasons = []
    if isinstance(getattr(response, 'text', None), str):
        body = response.text[:16384]
        problem = dict(parse_qsl(body)).get('oauth_problem')
        if problem in OAUTH_PROBLEMS:
            reasons.append(f'oauth_problem={problem}')
        code = None
        try:
            payload = json.loads(body)
            if isinstance(payload, dict) and isinstance(payload.get('error'), dict):
                code = str(payload['error'].get('code'))
        except ValueError:
            pass
        if code is None and '<!DOCTYPE' not in body.upper():
            try:
                root = ET.fromstring(body)
                node = root.find('{*}code')
                if node is not None:
                    code = (node.text or '').strip()
            except ET.ParseError:
                pass
        if code in ERROR_CODES:
            reasons.append(f'FatSecret code {code}: {ERROR_CODES[code]}')
    reason = '; '.join(reasons) or 'No recognized error code returned; verify OAuth 1.0 credentials and application access'
    return f'Authorization failed ({detail}). {reason}. No secrets printed.'


def token_response(response):
    """Validate a token response without including secrets in errors."""
    response.raise_for_status()
    token = dict(parse_qsl(response.text))
    if not all(token.get(key) for key in ('oauth_token', 'oauth_token_secret')):
        raise ValueError('FatSecret did not return a complete OAuth token')
    return token


def main(settings: Settings | None = None):
    settings = settings if settings is not None else load_settings()
    client = FatSecretClient(settings)
    token_file = settings.token_file
    if os.environ.get('EDA_DATABASE_URL'):
        from eda_state import load_state
        exists = bool(load_state('fatsecret_token'))
    else:
        exists = token_file.exists()
    if exists:
        raise SystemExit('Already authorized. Remove .tokens.json explicitly if you want to reconnect.')
    # FatSecret's token endpoints require GET with query-string OAuth signing.
    # fetch_request_token() always sends POST, which this endpoint rejects.
    with client.session(callback_uri='oob', signature_type='QUERY') as s:
        response = s.get('https://authentication.fatsecret.com/oauth/request_token',
                         timeout=30, allow_redirects=False)
        request = token_response(response)
        url = s.authorization_url('https://authentication.fatsecret.com/oauth/authorize',
                                  request_token=request['oauth_token'])
    print('Open this URL and approve access to your existing account:')
    print(url)
    verifier = getpass.getpass('Enter the verifier shown by FatSecret: ').strip()
    if not verifier:
        raise SystemExit('Empty verifier; authorization cancelled')
    with client.session(request, verifier=verifier, signature_type='QUERY') as s:
        response = s.get('https://authentication.fatsecret.com/oauth/access_token',
                         timeout=30, allow_redirects=False)
        token = token_response(response)
    saved = {key: token[key] for key in ('oauth_token', 'oauth_token_secret')}
    if os.environ.get('EDA_DATABASE_URL'):
        from eda_state import save_state
        save_state('fatsecret_token', saved, only_if_absent=True)
        print('Authorization saved in PostgreSQL.')
        return
    fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(saved, output)
    print('Authorization saved. Start server.py next.')


def cli(argv=None, *, default_config_dir: Path | None = None):
    parser = argparse.ArgumentParser(description='Authorize a FatSecret account')
    parser.add_argument('--config-dir', type=Path,
                        default=os.getenv('FATSECRET_CONFIG_DIR') or default_config_dir,
                        help='Directory containing .env and .tokens.json; defaults to cwd.')
    args = parser.parse_args(argv)
    try:
        main(load_settings(args.config_dir))
    except Exception as exc:
        raise SystemExit(authorization_error(exc)) from None


if __name__ == '__main__':
    cli()
