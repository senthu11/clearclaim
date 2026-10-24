"""Opt-in encrypted snapshots. No uploaded documents, raw text, or chat are saved."""
import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parents[1] / '.local-reviews'

def cipher(password, salt):
    if len(password) < 12:
        raise ValueError('Use a passphrase of at least 12 characters. It cannot be recovered.')
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=1200000).derive(password.encode())
    return Fernet(base64.urlsafe_b64encode(key))

def path_for(identifier, root=ROOT):
    if not re.fullmatch(r'[a-f0-9]{32}', identifier):
        raise ValueError('Invalid review identifier.')
    return root / (identifier + '.json')

def save(data, password, days=30, root=ROOT):
    if days not in (1, 7, 30, 90):
        raise ValueError('Invalid retention.')
    salt = os.urandom(16)
    now = datetime.now(timezone.utc)
    payload = {'snapshot': data, 'expires': (now + timedelta(days=days)).isoformat()}
    token = cipher(password, salt).encrypt(json.dumps(payload).encode()).decode()
    identifier = uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    document = {'salt': base64.b64encode(salt).decode(), 'token': token,
                'created': now.isoformat(), 'expires': payload['expires']}
    target = path_for(identifier, root)
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(document), encoding='utf-8')
    temp.replace(target)
    return identifier

def list_saved(root=ROOT):
    items = []
    for path in root.glob('*.json'):
        if not re.fullmatch(r'[a-f0-9]{32}', path.stem):
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if datetime.fromisoformat(data['expires']) <= datetime.now(timezone.utc):
                path.unlink()
            else:
                items.append({'id': path.stem, 'created': data['created'], 'expires': data['expires']})
        except (ValueError, KeyError, OSError):
            continue
    return sorted(items, key=lambda x: x['created'], reverse=True)

def load(identifier, password, root=ROOT):
    try:
        data = json.loads(path_for(identifier, root).read_text(encoding='utf-8'))
        payload = json.loads(cipher(password, base64.b64decode(data['salt'])).decrypt(data['token'].encode()))
        if datetime.fromisoformat(payload['expires']) <= datetime.now(timezone.utc):
            raise ValueError('This review has expired.')
        return payload['snapshot']
    except (InvalidToken, KeyError, json.JSONDecodeError):
        raise ValueError('Unable to unlock: incorrect passphrase or damaged review.') from None

def delete(identifier, root=ROOT):
    path_for(identifier, root).unlink(missing_ok=True)
